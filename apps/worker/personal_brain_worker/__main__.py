"""Worker entrypoint: ``python -m personal_brain_worker`` claims durable jobs.

FR-083/FR-084: the worker starts only after the shared DB/job preflight and
respects lease fencing; see packages/infrastructure/personal_brain_infra/jobs.
"""

from __future__ import annotations

import signal
import sys
import threading

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_server.bootstrap.settings import Settings, read_secret_file
from personal_brain_worker.runtime import DurableJobPoller, WorkerLoop
from personal_brain_worker.job_handlers import build_job_handlers, build_job_recheck
from personal_brain_worker.scheduler import PeriodicScheduler
from personal_brain_infra.storage.local import LocalStorage
from personal_brain_infra.models.gateway import ModelCard, ModelGateway
from personal_brain_infra.models.volcengine import AnthropicCompatibleProvider, VolcengineEmbeddingProvider


def main() -> int:
    stop = threading.Event()
    try:
        settings = Settings()
        dsn = read_secret_file(settings.database_dsn_file).get_secret_value()
        engine = sa.create_engine(dsn, pool_pre_ping=True)
        metadata = sa.MetaData()
        metadata.reflect(engine)
        from pgvector.sqlalchemy import VECTOR
        metadata.tables["search_index_entries"].c.embedding.type = VECTOR()
        jobs = metadata.tables["jobs"]

        factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
        gateway = embedder = None
        if settings.external_models_enabled:
            if settings.model_api_key_file is None:
                raise ValueError("model API key file is required")
            api_key = read_secret_file(settings.model_api_key_file)
            gateway = ModelGateway(
                provider=AnthropicCompatibleProvider(
                    settings.chat_model_base_url, api_key, settings.chat_model_name,
                    uds=str(settings.model_proxy_socket) if settings.model_proxy_socket else None,
                ),
                card=ModelCard(
                    name=settings.chat_model_name, version=settings.chat_model_name,
                    dimensions=0, tokenizer="ark-anthropic-compatible",
                    sensitivity="private", max_input_tokens=32768,
                    provider_id="volcengine-ark", allowed_context_keys=("sources", "payload_ref", "target_type", "kind"),
                ),
                timeout_seconds=60, max_calls=1,
            )
            embedder = VolcengineEmbeddingProvider(
                settings.embedding_base_url, api_key, settings.embedding_model_name,
                dimensions=settings.embedding_dimensions,
                uds=str(settings.model_proxy_socket) if settings.model_proxy_socket else None,
            )
        handlers = build_job_handlers(
            factory, metadata.tables, LocalStorage(settings.data_root / "assets"),
            gateway=gateway, embedder=embedder,
            llm_daily_quota=settings.llm_daily_quota,
        )
        poller = DurableJobPoller(
            factory, jobs, worker_id="personal-brain-worker", handlers=handlers,
            recheck=build_job_recheck(factory, metadata.tables),
        )
        scheduler = PeriodicScheduler(
            factory, metadata.tables, timezone_name=settings.default_timezone,
        )

        def poll_and_schedule() -> None:
            poller.poll()
            scheduler.tick()

        for event in (signal.SIGINT, signal.SIGTERM):
            signal.signal(event, lambda *_: stop.set())
        WorkerLoop(poll=poll_and_schedule).run(stop_requested=stop.is_set)
        engine.dispose()
        return 0
    except (ValueError, sa.exc.SQLAlchemyError) as error:
        print(f"personal-brain-worker: startup failed ({type(error).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
