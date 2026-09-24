# Foundation acceptance evidence (T043)

Date: 2026-09-23 Asia/Shanghai. Command line (selective, environment- and
story-independent):

```text
pytest tests/integration/test_transactional_foundation.py
       tests/integration/test_idempotency_claim.py
       tests/integration/test_job_store.py
       tests/security/test_authority_boundary.py
       tests/security/test_provider_boundary.py
       tests/security/test_logging_privacy.py
       tests/security/test_scoped_repository.py
       tests/security/test_client_credentials.py
       tests/security/test_policy.py
       tests/unit/test_settings.py tests/unit/test_errors.py
       tests/unit/test_secret_filter.py tests/unit/test_security_pipeline.py
       tests/unit/test_source_policy.py tests/unit/test_inbox_proposals.py
       tests/unit/test_preflight.py
       tests/contract/test_transport_auth.py test_protocol_contracts.py
       test_protocol_adapters.py test_deployment_boundary.py
       tests/migration/test_0001_authority_core.py
```

Result: **66 passed, 1 environment-gated** (migration round-trip needs
`BRAIN_TEST_POSTGRES_DSN`; the isolated PostgreSQL round-trip previously passed
on the target host per implementation-handoff.md T020). No skipped safety case
was marked passing.

## What this run verifies

| Area | Evidence |
|---|---|
| Idempotency claim/replay/tombstone | `test_idempotency_claim.py`, `test_transactional_foundation.py` property tests: `(client_id, operation, key)` uniqueness, same-digest replay returns stored outcome, different-digest conflict, tombstone erases digest/outcome and never recreates deleted content. |
| Durable job semantics | `test_job_store.py`, `test_transactional_foundation.py`: claim/heartbeat/reclaim fencing (`may_commit_result`), retry-wait and dead-letter transitions under lease60s/heartbeat20s/max5/5-30-120-600+jitter policy. |
| Authority before repository | `test_authority_boundary.py`, `test_scoped_repository.py`: deny-first tool/scope/sensitivity, revoked/stale-epoch rejection before any SQL read, SQL-level owner/scope/sensitivity predicates. |
| Body-free audit + safe errors | `test_authority_boundary.py`: `build_audit_event` drops `request_body`/`credential`; `safe_error` maps arbitrary exceptions to value-free stable envelopes. |
| Secret filtering | `test_secret_filter.py`, `test_security_pipeline.py`: filename/type/content secret detection with value-free results; pre-persistence gate for project/document/archive/log/search sinks. |
| Provider privacy boundary | `test_provider_boundary.py`: external models disabled by default, model card identity/dimensions/tokenizer/sensitivity/budget declared. |
| Logging/rotation | `test_logging_privacy.py`: redaction filter, correlation-ID formatter, bounded rotation settings. |
| OAuth/PKCE + transports | `test_transport_auth.py`, `test_protocol_adapters.py`: S256 discovery/code exchange/exact redirect/resource binding/revocation; remote Origin validation; stdio JSON-RPC stdout-only. |
| Protocol envelopes | `test_protocol_contracts.py`: request payload rejects credentials; success distinguishes `accepted`/`completed` (+`canonical_committed`); `get_operation_status` lifecycle lookup. |
| Proposals/Inbox | `test_inbox_proposals.py`: 15-minute expiry, single-use, version-bound approve/reject. |
| Preflight | `test_preflight.py`: readiness only with evidence; component failures never collapse into ready. |
| Deployment boundary | `test_deployment_boundary.py`: compose publishes only the approved LAN port, never embeds secrets. |
| Migration | `test_0001_authority_core.py`: 13 core tables created once; round-trip/post-validation gated on test PostgreSQL. |

## Remaining risks

- Story modules (records/memory/intake/service) are later phases; their red-first
  tests intentionally still fail on missing modules, not as regression.
- Real-client acceptance, backup/restore verification, and real-data deployment
  remain gated (see deployment-decision.md); this document authorizes nothing
  beyond synthetic foundation evidence.
