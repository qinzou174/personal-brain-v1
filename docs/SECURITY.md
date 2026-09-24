# Security (V1)

- **Credentials**: internal opaque tokens verified via Argon2id; token values are
  never persisted or logged. Remote clients use OAuth authorization-code + PKCE
  S256 with exact redirects, resource binding and revocation.
- **Permission before retrieval**: tool/scope/sensitivity grants are evaluated
  before any repository or search access; explicit deny wins.
- **Secrets**: secret-like filenames/types/content are rejected before ordinary
  persistence with value-free records; never in logs, search, or audit.
- **Workspace**: bridge resolves paths against the approved root (symlink/reparse
  escapes rejected before read).
- **Audit**: body-free structured events only; private bodies never recorded.
- **Lifecycle**: deletion previews first, confirms version-bound, then purges with
  a value-free ledger; backups disclose purge windows.
- **Jobs**: durable lease/fencing; stale workers cannot commit results.
