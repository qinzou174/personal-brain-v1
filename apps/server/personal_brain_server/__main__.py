"""Server entrypoint: ``python -m personal_brain_server`` runs the ASGI app.

FR-098: the process binds only after configuration preflight passes and reports
readiness honestly; no route, worker, or admin surface is exposed before the
owner-approved LAN endpoint decision (see docs/deployment-decision.md).
"""

from __future__ import annotations

import argparse
import json
import sys

import sqlalchemy as sa
import uvicorn
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
from personal_brain_infra.security.authority import PersistedAuthority
from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore
from personal_brain_infra.search.repository import PostgresSearchRepository
from personal_brain_infra.storage.local import LocalStorage
from personal_brain_infra.models.gateway import ModelCard, ModelGateway
from personal_brain_infra.models.volcengine import AnthropicCompatibleProvider, VolcengineEmbeddingProvider
from personal_brain_server.api.authorized_tools import AuthorizedToolService
from personal_brain_server.bootstrap.settings import Settings, read_secret_file
from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
from personal_brain_server.protocols.remote import create_mcp_router
from personal_brain_server.protocols.tools import tool_definitions
from personal_brain_server.runtime import build_doctor_probe, build_readiness_probe, create_app
from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority
from personal_brain_domain.common.errors import BrainError
from personal_brain_server.admin import (
    list_clients, provision_client, rebuild_index, revoke_client, rotate_client_credential,
    set_project_access, set_review_access,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="personal-brain-server")
    commands = parser.add_subparsers(dest="command")
    doctor = commands.add_parser("doctor", help="validate configuration and runtime dependencies")
    doctor.add_argument("--preflight", action="store_true", help="run the deployment preflight")
    doctor.add_argument("--json", action="store_true", help="emit a machine-readable report")
    provision = commands.add_parser("provision-client", help="create the owner if needed and provision a client")
    provision.add_argument("--name", required=True)
    provision.add_argument("--client-type", required=True)
    provision.add_argument("--credential-file", required=True)
    rotate = commands.add_parser("rotate-client", help="replace a client credential and revoke its predecessors")
    rotate.add_argument("--client-id", required=True)
    rotate.add_argument("--credential-file", required=True)
    revoke = commands.add_parser("revoke-client", help="revoke a client and all of its credentials")
    revoke.add_argument("--client-id", required=True)
    revoke.add_argument("--confirm-client-id", required=True)
    project = commands.add_parser("project-access", help="grant or revoke exact project access")
    project.add_argument("--client-id", required=True)
    project.add_argument("--project-id", required=True)
    project.add_argument("--access", required=True, choices=("read", "write", "none"))
    project.add_argument("--confirm-client-id", required=True)
    project.add_argument("--confirm-project-id", required=True)
    review = commands.add_parser(
        "review-access", help="grant or revoke governance (review) access on one content scope",
    )
    review.add_argument("--client-id", required=True)
    review.add_argument("--scope", required=True)
    review.add_argument("--access", required=True, choices=("read", "write", "none"))
    review.add_argument("--confirm-client-id", required=True)
    review.add_argument("--confirm-scope", required=True)
    clients = commands.add_parser("list-clients", help="list client status and effective configured scopes")
    clients.add_argument("--json", action="store_true")
    rebuild = commands.add_parser(
        "rebuild-index", help="enqueue one re-index job per canonical record (safe to repeat)",
    )
    rebuild.add_argument("--limit", type=int, default=5000, help="max records per table")
    return parser.parse_args(argv)


def _configuration_failure(error: ValueError) -> dict[str, object]:
    missing: list[str] = []
    errors = getattr(error, "errors", None)
    if callable(errors):
        for item in errors():
            if item.get("type") == "missing" and item.get("loc"):
                missing.append(str(item["loc"][0]))
    return {
        "ready": False,
        "configuration": "failed",
        "missing_fields": sorted(set(missing)),
        "error": "VALIDATION_FAILED",
    }


def _doctor(settings: Settings) -> dict[str, object]:
    dsn = read_secret_file(settings.database_dsn_file).get_secret_value()
    read_secret_file(settings.token_pepper_file)
    engine = sa.create_engine(dsn, pool_pre_ping=True)
    try:
        report = build_readiness_probe(engine, settings.data_root)()
        return {**settings.safe_summary(), **report}
    finally:
        engine.dispose()


def _admin_command(settings: Settings, args: argparse.Namespace) -> dict[str, object] | list[dict[str, object]]:
    dsn = read_secret_file(settings.database_dsn_file).get_secret_value()
    read_secret_file(settings.token_pepper_file)
    engine = sa.create_engine(dsn, pool_pre_ping=True)
    try:
        metadata = sa.MetaData()
        metadata.reflect(engine)
        from pgvector.sqlalchemy import VECTOR
        metadata.tables["search_index_entries"].c.embedding.type = VECTOR()
        factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
        if args.command == "provision-client":
            return provision_client(
                factory, metadata.tables, display_name=args.name,
                client_type=args.client_type, credential_file=args.credential_file,
            )
        if args.command == "rotate-client":
            return rotate_client_credential(
                factory, metadata.tables, client_id=args.client_id,
                credential_file=args.credential_file,
            )
        if args.command == "revoke-client":
            return revoke_client(
                factory, metadata.tables, client_id=args.client_id,
                confirmed_client_id=args.confirm_client_id,
            )
        if args.command == "project-access":
            return set_project_access(
                factory, metadata.tables, client_id=args.client_id,
                project_id=args.project_id, access=args.access,
                confirmed_client_id=args.confirm_client_id,
                confirmed_project_id=args.confirm_project_id,
            )
        if args.command == "review-access":
            return set_review_access(
                factory, metadata.tables, client_id=args.client_id, scope=args.scope,
                access=args.access, confirmed_client_id=args.confirm_client_id,
                confirmed_scope=args.confirm_scope,
            )
        if args.command == "list-clients":
            return list_clients(factory, metadata.tables)
        if args.command == "rebuild-index":
            return rebuild_index(factory, metadata.tables, batch_limit=args.limit)
        raise ValueError("unsupported operator command")
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    from personal_brain_server.bootstrap.logging import configure_logging

    configure_logging()
    args = _arguments(argv)
    try:
        settings = Settings()
        if args.command == "doctor":
            report = _doctor(settings)
            output = json.dumps(report, ensure_ascii=False) if args.json else str(report)
            print(output)
            return 0 if report.get("ready") else 2
        if args.command in {
            "provision-client", "rotate-client", "revoke-client", "project-access", "list-clients",
            "review-access", "rebuild-index",
        }:
            result = _admin_command(settings, args)
            print(json.dumps(result, ensure_ascii=False, default=str))
            return 0
        dsn = read_secret_file(settings.database_dsn_file).get_secret_value()
        read_secret_file(settings.token_pepper_file)
        engine = sa.create_engine(dsn, pool_pre_ping=True)
        readiness = build_readiness_probe(engine, settings.data_root)
        initial = readiness()
        if not initial["ready"]:
            print("personal-brain-server: dependency preflight failed", file=sys.stderr)
            engine.dispose()
            return 2
        metadata = sa.MetaData()
        metadata.reflect(engine)
        from pgvector.sqlalchemy import VECTOR
        metadata.tables["search_index_entries"].c.embedding.type = VECTOR()
        factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
        opaque_authority = PersistedAuthority(factory, metadata.tables)
        public_host = settings.published_host or settings.bind_host
        # OAuth discovery/audience must match the URL clients actually use: an
        # HTTPS tunnel or reverse proxy is configured explicitly instead of being
        # mis-advertised as the LAN http endpoint.
        base = settings.public_base_url or f"http://{public_host}:{settings.bind_port}"
        resource = f"{base}/mcp"
        authority = OAuthBearerAuthority(
            grant_store=PersistedOAuthGrantStore(factory, metadata.tables),
            opaque=opaque_authority,
            resource=resource,
        )
        model_gateway = embedding_provider = None
        if settings.external_models_enabled:
            if settings.model_api_key_file is None:
                raise ValueError("model API key file is required")
            model_api_key = read_secret_file(settings.model_api_key_file)
            model_gateway = ModelGateway(
                provider=AnthropicCompatibleProvider(
                    settings.chat_model_base_url, model_api_key, settings.chat_model_name,
                    uds=str(settings.model_proxy_socket) if settings.model_proxy_socket else None,
                ),
                card=ModelCard(
                    name=settings.chat_model_name, version=settings.chat_model_name,
                    dimensions=0, tokenizer="ark-anthropic-compatible",
                    sensitivity="private", max_input_tokens=32768,
                    provider_id="volcengine-ark", allowed_context_keys=("sources",),
                ), timeout_seconds=60, max_calls=1,
            )
            embedding_provider = VolcengineEmbeddingProvider(
                settings.embedding_base_url, model_api_key, settings.embedding_model_name,
                dimensions=settings.embedding_dimensions,
                uds=str(settings.model_proxy_socket) if settings.model_proxy_socket else None,
            )
        service = AuthorizedToolService(
            authority,
            lambda *, owner_id, client_id: AuthoritativeStore(
                factory, owner_id=owner_id, client_id=client_id,
            ),
            storage=LocalStorage(settings.data_root / "assets"),
            search_factory=lambda *, owner_id: PostgresSearchRepository(
                factory, metadata.tables["search_index_entries"], owner_id=owner_id,
            ),
            model_gateway=model_gateway, embedding_provider=embedding_provider,
        )
        implemented = {
            "save_note", "add_expense", "add_todo", "get_operation_status",
            "create_project", "start_task", "checkpoint_task", "propose_self_claim",
            "create_review_item", "sync_workspace", "get_project_context",
            "get_module_context", "get_active_task", "get_recent_changes",
            "check_freshness", "record_decision", "record_constraint", "finalize_task",
            "list_todos", "complete_todo", "list_expense_records", "get_expense_summary",
            "get_self_context",
            "search_brain", "search_project", "get_brain_context", "answer_brain",
            "upload_asset", "create_deletion_plan", "get_deletion_plan",
            "list_review_items", "resolve_review_item", "list_projects",
        }

        def invoke(name: str, arguments: dict, identity: tuple[object, str]) -> dict:
            _context, credential = identity
            operation = getattr(service, name)
            converted = dict(arguments)
            from personal_brain_domain.common.errors import BrainError
            try:
                if "idempotency_key" in converted:
                    import uuid
                    converted["idempotency_key"] = uuid.UUID(converted["idempotency_key"])
                if "operation_id" in converted:
                    import uuid
                    converted["operation_id"] = uuid.UUID(converted["operation_id"])
                if name == "upload_asset" and "content_base64" in converted:
                    import base64
                    converted["content"] = base64.b64decode(
                        converted.pop("content_base64"), validate=True,
                    )
                    if len(converted["content"]) > 100 * 1024 * 1024:
                        raise BrainError("PAYLOAD_TOO_LARGE")
                for field in ("project_id", "task_id", "todo_id", "item_id", "source_id", "plan_id"):
                    if field in converted:
                        import uuid
                        converted[field] = uuid.UUID(converted[field])
            except (ValueError, TypeError) as error:
                # Malformed field values (bad UUID/base64) are client
                # validation failures, not transport parse errors.
                raise BrainError("VALIDATION_FAILED") from error
            return operation(credential=credential, **converted)

        dispatcher = MCPDispatcher(
            tool_definitions=[item for item in tool_definitions() if item["name"] in implemented],
            invoke=invoke,
            resolve_identity=lambda credential: (authority.authenticate(credential), credential),
        )
        protocol_router = create_mcp_router(
            dispatcher=dispatcher, resource=resource, authorization_server=base,
            allowed_origins=settings.origin_allowlist(),
        )
        app = create_app(
            readiness_probe=readiness,
            protocol_router=protocol_router,
            doctor_probe=build_doctor_probe(engine, settings.data_root),
        )
        uvicorn.run(app, host=str(settings.bind_host), port=settings.bind_port, access_log=True)
        engine.dispose()
        return 0
    except (ValueError, BrainError, sa.exc.SQLAlchemyError) as error:
        if args.command == "doctor":
            report = _configuration_failure(error) if isinstance(error, ValueError) else {
                "ready": False, "database": "failed", "error": "DEPENDENCY_FAILED",
            }
            output = json.dumps(report, ensure_ascii=False) if args.json else str(report)
            print(output)
            return 2
        if args.command is not None:
            code = error.code if isinstance(error, BrainError) else "OPERATOR_COMMAND_FAILED"
            print(json.dumps({"status": "failed", "error": code}), file=sys.stderr)
            return 2
        print(f"personal-brain-server: startup failed ({type(error).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
