# Cursor Setup (draft)

Same contract as TRAE: point Cursor at the bridge or remote endpoint. Status:
EXTERNAL_VERIFICATION_PENDING until real-account evidence exists.

1. Add the Brain as an MCP server (stdio bridge or remote HTTPS+OAuth).
2. Follow the tool surface in `docs/MCP_TOOLS.md`; unknown tools are denied.
3. Project tasks require the `project.write:<id>` grant; recovery works from a
   fresh session with no chat history.

Real Cursor version verification, cross-IDE reads/decisions and revocation are
Release-phase acceptance items.
