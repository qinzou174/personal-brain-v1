# MCP protocol negotiation fix (2026-09-24)

## Defect

Two handshake behaviours contradicted the MCP 2025-11-25 transport rules and
blocked standard clients (notably mobile terminals) before any tool call:

- **A — version header required on `initialize`.** `protocols/remote.py` rejected
  any request whose `MCP-Protocol-Version` header was absent, including the
  `initialize` request. The specification requires the header only on requests
  *after* initialization; `initialize` negotiates the version through
  `params.protocolVersion`.
- **B — version mismatch rejected instead of negotiated.** `MCPDispatcher.handle`
  raised `VALIDATION_FAILED` when `params.protocolVersion` differed from
  `2025-11-25`. The specification requires the server to answer with a version it
  supports; the client decides whether it can continue.

Neither behaviour is a security control — authentication and authorization are
unaffected — so the fix only relaxes handshake strictness.

## Change

- `apps/server/personal_brain_server/protocols/remote.py`
  - A supplied `MCP-Protocol-Version` must still equal `2025-11-25` (invalid or
    unsupported version → `400`), but the header is now optional on `initialize`.
  - Requests after initialization still require the matching header.
- `apps/server/personal_brain_server/protocols/mcp_dispatcher.py`
  - `initialize` now negotiates: a non-empty string `protocolVersion` is accepted
    and the response carries the supported version `2025-11-25`. A missing or
    non-string `protocolVersion` is still rejected (`VALIDATION_FAILED`).

## Evidence

- `tests/contract/test_mcp_dispatcher.py` (+2 tests): negotiate an unsupported
  version (`2024-11-05` → `2025-11-25`), reject a missing `protocolVersion`, and
  prove the header is optional on `initialize` but required (and matching) after.
- `tests/contract tests/security tests/integration`: **145 passed**.
- Live verification on the LAN endpoint `http://192.168.10.7:18081/mcp`
  (real `Mobile Terminal` credential, image `92627dd3869d`):

| request | headers | result |
|---|---|---|
| `initialize` (`protocolVersion=2025-06-18`) | Authorization only | `200`, result `protocolVersion=2025-11-25`, session issued |
| `tools/list` (with session) | no version header | `400 VALIDATION_FAILED` |
| `tools/list` (with session) | `MCP-Protocol-Version: 2025-11-25` | `200`, 30 tools |

- Container logs confirm both an access line and a body-free rejection warning
  (`mcp rejected status=400 code=VALIDATION_FAILED method=POST`); no request body,
  credential or client identity is logged (FR-070/FR-073).

## Notes

- `GET /mcp` still returns `405`; the specification permits this for servers that
  do not offer an SSE stream, so it was left unchanged.
- `docs/dependency-baseline.md` already states "Do not force its newest revision
  on a client without an interoperability test"; this fix aligns the code with
  that boundary. No documentation change was required.
