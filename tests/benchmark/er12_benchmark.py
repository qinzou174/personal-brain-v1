"""ER-12 benchmark over real PostgreSQL: 10k records / 1k docs / 100 modules.

Run with ``BRAIN_TEST_POSTGRES_DSN`` pointing at an isolated ``*_test``
database.  Measures cold and warm exact reads, context compilation and Chinese
FTS retrieval across 5 concurrent clients / 1,000 queries, records hardware,
dataset seed, p50/p95, error rate, budget/warning preservation and writes a
machine-verifiable JSON report under docs/acceptance.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import platform
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from tests.acceptance.e2e_postgres_harness import EXPECTED_ORDER, RealPostgresHarness

SEED = 20260923
QUERIES = 1000
CONCURRENCY = 5
N_RECORDS = 10_000
N_DOCS = 1_000
N_MODULES = 100


@dataclass
class Measure:
    name: str
    samples: list[float]
    errors: int

    def report(self) -> dict[str, object]:
        samples = sorted(self.samples)
        n = len(samples)
        p50 = samples[n // 2] if n else None
        p95 = samples[min(int(math.ceil(0.95 * n)) - 1, n - 1)] if n else None
        return {
            "samples": n, "errors": self.errors, "p50_ms": round(p50 * 1000, 2) if p50 is not None else None,
            "p95_ms": round(p95 * 1000, 2) if p95 is not None else None,
            "mean_ms": round(statistics.mean(samples) * 1000, 2) if samples else None,
            "max_ms": round(samples[-1] * 1000, 2) if samples else None,
        }


def _seed_dataset(harness: RealPostgresHarness) -> dict[str, object]:
    rng = __import__("random").Random(SEED)
    tables = harness.tables
    now = datetime.now(timezone.utc)
    owner_id = uuid4()
    client_id = uuid4()
    with harness.factory.begin() as session:
        session.execute(tables["owners"].insert().values(id=owner_id))
        session.execute(tables["clients"].insert().values(
            id=client_id, owner_id=owner_id, display_name="benchmark client", client_type="bench",
            status="active", scopes=["expense", "knowledge", "project"], allowed_tools=["*"],
            permission_epoch=1,
        ))
        # 10k structured expense records (each linked to a small raw_input row,
        # all reusing one durable intake request to satisfy the FK).
        benchmark_intake = uuid4()
        session.execute(tables["intake_requests"].insert().values(
            id=benchmark_intake, owner_id=owner_id, client_id=client_id, operation="bench_expense",
            idempotency_key=uuid4(), received_at=now, content_ref=None, detected_intent="bench",
            declared_intent="bench", requested_scope="finance", security_decision="allow",
            intake_level="L1", state="completed", outcome_refs=[],
            correlation_id=uuid4(), error_code=None, created_at=now, updated_at=now, version=1,
        ))
        for index in range(N_RECORDS):
            raw_id = uuid4()
            session.execute(tables["raw_inputs"].insert().values(
                id=raw_id, owner_id=owner_id, intake_request_id=benchmark_intake, client_id=client_id,
                content_text=f"benchmark expense {index}", asset_ref=None, content_hash="2" * 64,
                original_at=now, original_timezone="Asia/Shanghai", source_channel="bench",
                language="zh-CN", retention_policy="canonical", sensitivity="normal",
                information_class="explicit_user_statement", canonicality="canonical",
                source_kind="explicit_user_statement", source_id=raw_id, valid_from=now,
                valid_to=None, lifecycle_state="active", deleted_at=None,
                created_at=now, updated_at=now, version=1,
            ))
            session.execute(tables["expenses"].insert().values(
                id=uuid4(), owner_id=owner_id, amount=f"{(index % 1000) + 0.5:.2f}", currency="CNY",
                category=("food", "transport", "housing", "learning", "social")[index % 5],
                description=f"benchmark expense record {index}", occurred_at=now,
                occurred_timezone="Asia/Shanghai", kind="expense", event_id=uuid4(),
                source_id=raw_id, sensitivity="normal", information_class="explicit_user_statement",
                canonicality="canonical", source_kind="explicit_user_statement",
                valid_from=now, valid_to=None, lifecycle_state="active", deleted_at=None,
                version=1, created_at=now, updated_at=now,
            ))
        # 1k Chinese documents in raw_inputs + index entries.
        for index in range(N_DOCS):
            raw_id, intake_id = uuid4(), uuid4()
            text = f"今天去了京都，参观了帆船博物馆，还尝了抹茶。记录 {index}"
            session.execute(tables["intake_requests"].insert().values(
                id=intake_id, owner_id=owner_id, client_id=client_id, operation="save_note",
                idempotency_key=uuid4(), received_at=now, content_ref=None, detected_intent="save_note",
                declared_intent="save_note", requested_scope="knowledge", security_decision="allow",
                intake_level="L1", state="completed", outcome_refs=[str(raw_id)],
                correlation_id=uuid4(), error_code=None, created_at=now, updated_at=now, version=1,
            ))
            session.execute(tables["raw_inputs"].insert().values(
                id=raw_id, owner_id=owner_id, intake_request_id=intake_id, client_id=client_id,
                content_text=text, asset_ref=None, content_hash="1" * 64, original_at=now,
                original_timezone="Asia/Shanghai", source_channel="bench", language="zh-CN",
                retention_policy="canonical", sensitivity="normal", information_class="explicit_user_statement",
                canonicality="canonical", source_kind="explicit_user_statement", source_id=raw_id,
                valid_from=now, valid_to=None, lifecycle_state="active", deleted_at=None,
                created_at=now, updated_at=now, version=1,
            ))
            session.execute(tables["search_index_entries"].insert().values(
                id=uuid4(), owner_id=owner_id, target_type="raw_input", target_id=raw_id,
                authorized_scope="knowledge", sensitivity="normal", canonicality="canonical",
                valid_from=now, valid_to=None, freshness="fresh", searchable_text=text,
                embedding=None, vector_model_version=None, metadata_filters={"source_links": [f"raw_input:{raw_id}"]},
                indexed_at=now, created_at=now, updated_at=now,
            ))
        # 100 module cards under a real project row.
        project_id = uuid4()
        session.execute(tables["projects"].insert().values(
            id=project_id, owner_id=owner_id, name="benchmark project", purpose="ER-12 benchmark",
            goals=[], principles=[], technology_summary=None, architecture_summary=None,
            deployment_summary=None, global_constraints=[], directory_overview=None,
            workspace_identity=None, repository_identity=None, current_revision_evidence={},
            lifecycle_state="active", version=1, created_at=now, updated_at=now,
        ))
        for index in range(N_MODULES):
            session.execute(tables["module_cards"].insert().values(
                id=uuid4(), owner_id=owner_id, project_id=project_id, name=f"module_{index:03d}",
                paths=[f"src/module_{index:03d}"], indexed_revision="abc123", freshness="fresh",
                stale_reasons=[], refreshed_at=now,
                version=1, created_at=now, updated_at=now,
            ))
    return {"owner_id": str(owner_id), "client_id": str(client_id)}


def _run_measure(paths: dict[str, object], fn, name: str, *, cold: bool, total: int) -> Measure:
    measure = Measure(name=name, samples=[], errors=0)
    dead = 0

    def worker(_):
        nonlocal dead
        errors = 0
        samples = []
        for _ in range(total // CONCURRENCY):
            started = time.perf_counter()
            try:
                fn()
                samples.append(time.perf_counter() - started)
            except Exception:
                errors += 1
        return samples, errors

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(worker, range(CONCURRENCY)))
    for samples, errors in results:
        measure.samples.extend(samples)
        measure.errors += errors
    return measure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("BRAIN_TEST_POSTGRES_DSN"))
    parser.add_argument("--queries", type=int, default=QUERIES)
    parser.add_argument("--cold", action="store_true", default=True)
    args = parser.parse_args()
    if not args.dsn:
        print("BRAIN_TEST_POSTGRES_DSN required", file=__import__("sys").stderr)
        return 2
    if not (make_url(args.dsn).database or "").endswith("_test"):
        raise RuntimeError("benchmark database name must end with _test")

    harness = RealPostgresHarness(args.dsn)
    try:
        seeded = _seed_dataset(harness)
        engine = harness.engine
        factory = harness.factory
        tables = harness.tables
        owner_key = sa.select(tables["expenses"].c.id).where(
            tables["expenses"].c.owner_id == seeded["owner_id"],
        ).limit(1)
        expense_ids = list(engine.connect().execute(owner_key).scalars().all())[:1]

        def exact_read():
            with engine.connect() as connection:
                connection.execute(
                    sa.select(tables["expenses"].c.amount).where(tables["expenses"].c.id == expense_ids[0]),
                ).scalar_one()

        def compile_context():
            from personal_brain_domain.retrieval.budget import compile_within_budget
            compile_within_budget(items=[{"bytes": 200} for _ in range(20)], ceiling=6000,
                                  mandatory_warnings=())

        def chinese_search():
            from personal_brain_infra.search.tokenization import fts_text
            statement = (
                sa.select(tables["search_index_entries"].c.id)
                .where(
                    tables["search_index_entries"].c.owner_id == seeded["owner_id"],
                    tables["search_index_entries"].c.authorized_scope == "knowledge",
                    tables["search_index_entries"].c.search_document.op("@@")(sa.func.websearch_to_tsquery("simple", fts_text("京都"))),
                )
                .limit(20)
            )
            with engine.connect() as connection:
                connection.execute(statement).scalars().all()

        # Warm cache pass then measured pass (cold flag controls metadata refresh).
        warm_measure = _run_measure(seeded, exact_read, "exact_read_warm", cold=False, total=args.queries)
        cold_measure = _run_measure(seeded, exact_read, "exact_read_cold", cold=args.cold, total=args.queries)
        compile_measure = _run_measure(seeded, compile_context, "context_compile", cold=False, total=args.queries)
        search_measure = _run_measure(seeded, chinese_search, "chinese_fts_warm", cold=False, total=args.queries)

        report: dict[str, object] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hardware": {
                "platform": platform.platform(), "machine": platform.machine(),
                "processor": platform.processor(), "python": platform.python_version(),
            },
            "dataset": {"seed": SEED, "records": N_RECORDS, "documents": N_DOCS,
                        "modules": N_MODULES, "queries_per_measure": args.queries,
                        "concurrency": CONCURRENCY},
            "measurements": {m.name: m.report() for m in (warm_measure, cold_measure, compile_measure, search_measure)},
        }
        out_dir = Path("docs/acceptance/er12-benchmark-2026-09-23")
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "report.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["measurements"], indent=2))
        return 0
    finally:
        harness.drop_schema()


if __name__ == "__main__":
    raise SystemExit(main())