# OAuth and provider hardening — T182 evidence (2026-09-23)

## Task marker

T182 is checked complete in `specs/001-personal-brain-v1/tasks.md`. This
document records machine-verifiable evidence produced by the current run only;
no synthetic or static-file substitution is admitted per Constitution VI.

## What T182 required

Harden OAuth and provider execution: registered exact redirect URIs,
authorization-code/token expiry, persisted grants and permission epochs, token
revocation, bounded provider call counting, enforced timeout, declared
context/sensitivity budgets and value-free failure/audit behavior (FR-004,
FR-006, FR-066..FR-075, FR-084, FR-086, ER-06, ER-12).

## OAuth surface (already present and now wired at runtime)

The OAuth authorization-code + PKCE S256 core already existed and is unchanged:
- `OAuthServer` (`apps/server/personal_brain_server/security/oauth.py`):
  exact redirect-URI registry, code/token expiry bounds, resource binding,
  single-use codes, monotonic permission-epoch revocation, PKCE S256 challenge.
- `PersistedOAuthGrantStore` (`packages/infrastructure/personal_brain_infra/
  security/oauth_grants.py`): owner-scoped bearer grants stored in the
  migration-owned `oauth_grants` table; the token value is never persisted
  (Argon2-derived verifier only); revocation stamps `revoked_at` and bumps the
  client `permission_epoch`.

New this pass — runtime identity mapping (ER-06: the protocol adapter maps a
verified remote credential into the same owner-bound context used by opaque
credentials):
- `oauth_grants.py::resolve_identity` returns
  `(owner_id, client_id, permission_epoch, scopes)` from a bearer grant after
  the same fail-closed checks as `verify` (revoked/status/audience/expiry/
  epoch/verifier), giving the adapter everything needed to build a context
  without a second query path.
- `apps/server/personal_brain_server/security/oauth_runtime.py::OAuthBearerAuthority`
  is a drop-in authority: a grant-shaped bearer token resolves through the
  grant store; anything else falls through to the opaque `PersistedAuthority`.
  Grant-shaped tokens that fail verification are rejected outright — they never
  fall back to the opaque branch.
- The production entrypoint now assembles
  `OAuthBearerAuthority(grant_store=PersistedOAuthGrantStore(...), opaque=...,
  resource=f"http://{bind}:{port}/mcp")` so remote Streamable-HTTP bearers are
  accepted on the same `/mcp` route as opaque local credentials (FR-075).

## Provider execution boundary (ER-12)

`ModelGateway`/`ModelCard`/`ProviderCallBudget` already existed and enforce:
- fail-closed when no provider is configured (`TOOL_DENIED` before any call);
- sensitivity ceiling and declared context-key budgets;
- secret rejection before the external call;
- a per-job bounded call count (default 2);
- an enforced thread-pool timeout (default 60 s);
- value-free errors (payload never reflected).

New this pass — the worker pipeline consumes the gateway with the same
fail-closed posture:
- `build_job_handlers(session_factory, tables, storage, gateway=None)` gains an
  optional `gateway` and always registers `provider_derive`.
- Without a gateway the handler refuses with `TOOL_DENIED` before reading a
  row or dialing out; with one, it executes through `gateway.execute` with a
  fresh bounded budget and translates policy/timeout failures into durable
  `JobExecutionError` outcomes (retryable only for transient provider
  availability), so FR-084 "no silent completion claim" holds and the call
  count stays inside the Job retry budget (ER-12).

## Evidence

- `tests/security/test_oauth_runtime_authority.py` (5 passing on the current run):
  1. `test_oauth_bearer_maps_to_authority_and_authorizes_against_grants` —
     bearer → owner/client/epoch context, then persisted-grant authorization.
  2. `test_oauth_bearer_fails_after_client_revocation_and_epoch_bump` —
     `revoke_client` invalidates the outstanding grant at runtime.
  3. `test_oauth_bearer_rejects_wrong_resource_and_expired_grants`.
  4. `test_oauth_shaped_token_never_falls_back_to_opaque` — grant-shaped
     garbage is rejected outright (no opaque fallback).
  5. `test_oauth_bearer_accepted_by_streamable_http_and_audit_is_value_free` —
     real TestClient `/mcp` initialize + tools/call with a persisted OAuth
     bearer; the resolved context never surfaces the token and `audit_repr`
     drops it from `request_body`/`credential`.
- `tests/security/test_provider_boundary.py` (5 passing incl. 2 new on this run):
  - `test_worker_provider_derive_fails_closed_without_gateway` → `TOOL_DENIED`.
  - `test_worker_provider_derive_enforces_bounded_calls_and_timeout` → one
    bounded call succeeds; a slow provider becomes a retryable
    `BRAIN_UNAVAILABLE` job outcome.
- Local full regression (current run): **405 passed, 13 skipped, 0 failed**.
  No real PostgreSQL run was repeated for this pass; the runtime OAuth tests use
  the same reflected schema/factory pattern proven against authoritative
  PostgreSQL in `test_authoritative_store.py` and
  `migration-postgresql-2026-09-23.md`.

## Honest state

- No real remote client (ChatGPT/TRAE/Cursor external accounts) was touched;
  real-client acceptance remains `EXTERNAL_VERIFICATION_PENDING` under T186.
- Provider execution is wired and fail-closed; no external model traffic was
  sent (no provider is configured).
- No real personal data was imported.