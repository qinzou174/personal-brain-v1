# Project Brain Rules (FR-103, project side)

- Start tasks with the current revision and known dirty state; never guess.
- Checkpoints are append-only: progress, problems, decisions, next step,
  verification evidence.
- Module freshness: `fresh` only when indexed revision == current revision;
  `stale` when evidence differs; `unknown` when no evidence. A racing refresh
  never clears a stale warning without successful evidence.
- Finalize compares start/end evidence and records change events; decisions and
  constraints deduplicate by a stable key.
- A fresh client with no chat history receives the recovery package (purpose,
  active task, checkpoints, relevant modules, recent changes, revision/dirty
  state, next step) and is told to inspect current source before modifying.
- The Brain answers "why" with evidence, source class, confidence basis and
  time/context — never unqualified inference.
