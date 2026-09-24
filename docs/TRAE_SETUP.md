# TRAE CN Setup

Local integration uses the stdio bridge (`personal_brain_bridge`). The actual
TRAE CN user configuration now contains a `personal-brain` server entry.

1. Open `%APPDATA%\Trae CN\User\mcp.json` and configure the bridge command as
   `uv --directory E:\新建文件夹\Personal-Brain-V1 run python -m personal_brain_bridge`.
2. Set only `BRAIN_BRIDGE_CLIENT_ID`, `BRAIN_REMOTE_MCP_URL` and
   `BRAIN_CREDENTIAL_FILE`; the last value is a file path, never a bearer value.
3. Reload the TRAE window after changing `mcp.json`, then confirm
   `personal-brain` appears in MCP tools.
4. stdout carries JSON-RPC only; logs go to stderr.
5. Mutations require an idempotency key; reads require the matching grant scope.

The same configured bridge has passed initialize, discovery, note/expense/todo,
exact summary, background indexing/search and project denial/grant/recovery
against the live LAN deployment. Visible discovery inside the already-running
TRAE window remains pending until the user reloads it; see the client matrix.
