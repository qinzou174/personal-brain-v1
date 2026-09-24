# F1 fix — per-scope search/context read authorization (2026-09-24)

## Defect

`search_brain` authorized every requested scope with `tool="knowledge.read"`.
A client holding only its domain read grants (`todo.read`, `finance.read`, …) was
therefore denied fuzzy retrieval outside the `knowledge` scope, and the code
disagreed with the authoritative contract, which names `search.read` for
`search_brain` and `context.read` for `get_brain_context`.

Observed before the fix (live local instance, real credential):

| scope | query | result |
|---|---|---|
| todo | 取快递 | `SCOPE_DENIED` |
| finance | 午饭 | `SCOPE_DENIED` |
| self | 我的偏好 | `SCOPE_DENIED` |

## Change

- `apps/server/personal_brain_server/api/authorized_tools.py`
  - Extracted `_search_core(context, …)`: performs routing and retrieval for an
    already-authorized scope and performs no additional grant check.
  - `search_brain` → `search.read` + requested scope (rechecked before response).
  - `get_brain_context` → `context.read` + requested scope.
  - `search_project` → `project.read` + `project:<id>` (was implicitly `knowledge.read`).
  - `answer_brain` keeps `knowledge.read` and now rechecks before the source read,
    before the external model call and before the response (ER-06).
  - Exact routes (expense totals, todo lists) read canonical records through
    `_expense_summary` / `_todo_records` inside the caller's authorized scope, so
    the operation is governed by exactly the contract-named tool.
- `apps/server/personal_brain_server/admin.py`
  - `DEFAULT_TOOLS` gains `search.read` and `context.read`.
  - `_TOOL_SCOPES` maps a tool to the scopes it may cover; provisioning inserts one
    grant per (tool, scope) over the content scopes (`knowledge`, `finance`, `todo`,
    `self`, `asset`, `projects`).
- `migrations/versions/0012_search_read_grants.py` (new)
  - Backfills `search.read`/`context.read` grants and `allowed_tools` for existing
    active clients on exactly the content scopes they already hold; never widens a
    client's scope set; creates no tables; issuer `migration_0012_search_read`.
  - Symmetric downgrade removes only the rows this revision inserted.
- `specs/001-personal-brain-v1/contracts/tool-contracts.md`, `docs/MCP_TOOLS.md`
  - Document the per-scope grant model and that exact routing stays inside the
    already-authorized scope.

## Evidence

- `tests/security/test_search_read_authorization.py` (new, 11 tests): pins the
  governing tool per read operation, proves non-knowledge scopes are searchable,
  proves a denied read never touches the index, proves `answer_brain` rechecks
  around the model call, and proves provisioning grants both tools per scope.
- Full local suite: **429 passed, 23 skipped, 0 failed**.
- Full suite against isolated PostgreSQL 16.15: **440 passed, 12 skipped, 0 failed**;
  physical migration suite **20 passed** (0001..0012 upgrade and reverse downgrade).
- Migration applied to the local trial database (0011 → 0012); preflight `True`,
  post-validation `True`; 6 content scopes now carry `search.read`/`context.read`.
- Live re-verification after restart:

| scope | query | before | after |
|---|---|---|---|
| todo | 取快递 | SCOPE_DENIED | hybrid hits |
| finance | 午饭 | SCOPE_DENIED | hybrid hits |
| self | 我的偏好 | SCOPE_DENIED | hybrid hits |
| diary | 今天 | SCOPE_DENIED | SCOPE_DENIED (client holds no diary scope — correct) |

- Live MCP acceptance 16/16, stdio bridge 9/9, reliability round 12/12 after the change.

## Not yet applied

The LAN deployment on `192.168.10.7` runs Compose services
(`personal-brain-v1-api-1`, `-worker-1`, `-db-1`, `-model-proxy-1`) from the
pre-fix revision. Its database still reports `0011_notifications`. Applying the
code change and migration there is a deployment action and was not performed
without approval.
