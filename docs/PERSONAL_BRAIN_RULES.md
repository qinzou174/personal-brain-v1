# Personal Brain V1 - Client Behavior Rules (FR-103)

These rules govern how any client (IDE, chat product, or custom tool) should use
the Brain. The Brain's own authority boundaries and freshness rules are the
contract; clients never bypass them.

## Memory and capture

- Capture is **raw-first**: the exact user statement is persisted first; derived
  extraction never rewrites it.
- Idempotency: mutations require a UUIDv4 key. Replays return the original
  outcome; a different payload under the same key is `IDEMPOTENCY_CONFLICT`.
- Intake levels: L0 ignored, L1 explicit (class A active), L2 ordinary
  (class B candidate), L3 confirmation-required (class C). Security/secret
  rejection always outranks every level.

## Task checkpoints and project freshness

- Start a task only with the current revision and a known dirty state.
- Checkpoints are append-only; capture progress, problems, decisions, next step
  and verification evidence.
- A module is `fresh` only when the indexed revision equals the current one;
  `stale` when evidence differs; `unknown` when no evidence exists. Never claim
  fresh without evidence.

## Source authority

- Exact finance/todo/project questions use deterministic lookup, never semantic
  estimation.
- Explicit user statements outrank inference; prior claims stay historical.
- Provenance ("why do you believe this?") reports evidence, source class,
  confidence basis, generator version, and time/context.

## Structured queries

- Use the documented tool surface (`get_expense_summary`, `list_todos`,
  `get_project_context`, `search_brain`, `get_self_context`, …). Do not invent
  tool names; unknown tools are denied.
- Reads require the correct `tool.read` grant and scope; writes require the
  corresponding write grant. Out-of-grant reads are denied before any search.
