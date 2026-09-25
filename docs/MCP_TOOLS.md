# Personal Brain V1 - MCP Tools

All tools are exposed through the authenticated protocol adapters (remote
Streamable HTTP with OAuth, or local stdio bridge). Every mutation requires an
idempotency key; reads are side-effect free.

## Life records

- `save_note` (knowledge.write) - raw-first note capture
- `add_expense` (finance.write) - exact money record
- `get_expense_summary` (finance.read) - exact per-currency totals
- `add_todo` (todo.write), `list_todos` (todo.read), `complete_todo` (todo.write)

## Projects

- `start_task`, `checkpoint_task`, `finalize_task`, `record_decision`,
  `record_constraint` (project.write:\<id\>)
- `get_project_context`, `get_module_context`, `get_active_task`,
  `get_recent_changes`, `check_freshness` (project.read:\<id\>)

## Retrieval

- `get_brain_context`, `search_brain` (context.read / search.read)
- `answer_brain` (knowledge.read) - permission-filtered retrieval followed by a
  grounded model answer with returned source links
- `get_entry_content` (search.read on the *entry's own scope*) - fetch-after-
  search: returns the full source text of one retrieval card. Absence (unknown
  entry, sensitivity above the ceiling, tombstoned source) is an honest
  `NOT_FOUND`. Search excerpts are additionally re-centered on the matched
  region for the top hits.
- `get_self_context` (self.read)

`search.read` / `context.read` grants are per scope: a client can search or
compile context for exactly the content scopes it holds (knowledge, finance,
todo, self, asset, and each granted `project:<id>`). Search never widens a
client's scope set, and a denied scope returns `SCOPE_DENIED` before any index
access.

## Assets

- `upload_asset` (asset.write)

## Operations

- `get_operation_status` - lookup the lifecycle of an accepted mutation
- `health` - per-component status without masking failures

Denied scopes produce no search/index access. See `contracts/tool-contracts.md`
for the authoritative contract.
