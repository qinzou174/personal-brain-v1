# Trilium integration setup (US12)

Status: **proposed, not activated**. The human-knowledge interface is removable;
disabling it leaves core Brain behavior intact. Real Trilium connection evidence
is an EXTERNAL_VERIFICATION_PENDING item pending owner-provided endpoint details.

## Required contract

- One-way paged idempotent import through ordinary intake/lineage policy.
- Every note keeps its source revision, checkpoint, conflict handling, secret
  filtering and backup coverage.
- No core-health dependency: the Brain serves normally while Trilium is down.
- Optional: source health and last-import status; automatic digests stay OPTIONAL.

## Activation gate

1. Owner provides a reachable Trilium endpoint and read credential through the
   dedicated secret file path (never env/Compose/Git).
2. The import job runs under the durable job lease/fencing contract.
3. Real-account import evidence is recorded before any production data write.
