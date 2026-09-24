# Client Matrix (Release acceptance)

Real-client evidence. Overall status: **EXTERNAL_VERIFICATION_PENDING** until
all client rows are complete; partial TRAE bridge evidence does not substitute
for visible IDE discovery.

| Client | Transport | Evidence needed | Status |
|---|---|---|---|
| TRAE CN | stdio bridge / HTTP | actual user config installed; initialize/discovery, Chinese workspace launch, note/expense/todo writes, exact read, indexing/search, pre-grant denial, grant/recovery/revoke and restart persistence passed through the configured bridge; visible IDE reload/discovery still required | PARTIAL / PENDING |
| Cursor | stdio/HTTP | tool discovery, cross-IDE read/decisions, revocation | PENDING |
| ChatGPT | HTTPS MCP + OAuth | discovery, login, scope calls, revocation, reachability | PENDING |
| Synthetic A/B | same business contract | MVP cross-client exact read | implemented (synthetic) |

`tests/acceptance/test_real_clients.py` keeps the real-client cases as skips so
they can never be marked passed without live evidence.

Current TRAE evidence is recorded in
`docs/acceptance/production-runtime-2026-09-23.md`. No credential value is
present in this matrix or in the TRAE MCP configuration.
