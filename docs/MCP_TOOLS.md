# Personal Brain V1 - MCP Tools

All tools are exposed through the authenticated protocol adapters (remote
Streamable HTTP with OAuth, or local stdio bridge). Every mutation requires an
idempotency key; reads are side-effect free.

## Life records

- `save_note` (knowledge.write) - raw-first note capture
- `update_note` (knowledge.write) - correct a note by superseding it: the
  corrected content becomes the live record (new `record_id`), the old raw row
  is tombstoned and its retrieval card removed in the same transaction, and the
  response names the replaced record as `superseded_id`. Unknown or already
  superseded source → `NOT_FOUND`.
- `add_expense` (finance.write) - exact money record
- `correct_expense` (finance.write) - "更正为 X" semantics: the old expense row
  is tombstoned, a corrected canonical row enters with a 更正-prefixed
  description and `version = old + 1`; the summary counts active rows only, so
  it is correct immediately. Response carries `corrected_from`.
- `get_expense_summary` (finance.read) - exact per-currency totals
- `add_todo` (todo.write), `list_todos` (todo.read), `complete_todo` (todo.write)
- `delete_todo` (todo.write) - direct terminal state for a low-risk record,
  version-bound (`VERSION_CONFLICT` on a stale version), single-use (double
  delete → `NOT_FOUND`); the retrieval card leaves the search view in the same
  transaction.

## Projects

- `start_task`, `checkpoint_task`, `finalize_task`, `record_decision`,
  `record_constraint` (project.write:\<id\>)
- `get_project_context`, `get_module_context`, `get_active_task`,
  `get_recent_changes`, `check_freshness` (project.read:\<id\>)

## Retrieval

- `get_brain_context`, `search_brain` (context.read / search.read)
- `search_brain` / `search_project` / `get_brain_context` accept optional
  `time_from` / `time_to` (ISO date or datetime): results are filtered by the
  record's own content time (`content_time` card metadata). A bare date means
  the whole day; **date boundaries are interpreted as UTC** (cards store their
  content time in UTC). Cards without a content time are honestly excluded
  when a range is given. Older cards gain `content_time` via the
  `rebuild-index` admin command.
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

## Response hints (advisory, never blocking)

- `index_state: "pending"` on every card-producing write: the retrieval card is
  built by a durable job seconds later — search immediately after a write may
  not see it yet.
- `conflict_warning` on `propose_self_claim`: a same-category, opposite-polarity
  claim already exists (same rule as the nightly `conflict_scan`). The write
  still succeeds.
- `duplicate_name_hint` on `create_project`: a live project with the same name
  exists. Creation still succeeds.
- `ALREADY_RESOLVED` error code: the review item was already decided — an
  idempotent state, not a missing confirmation.

Denied scopes produce no search/index access. See `contracts/tool-contracts.md`
for the authoritative contract.
