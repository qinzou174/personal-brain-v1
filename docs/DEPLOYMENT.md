# Deployment (V1)

Phase 0 layout decision: `docs/deployment-decision.md`.

- Target: `kms@192.168.10.7`, LAN-only first stage. Bind `192.168.10.7:18081`
  only; DB/worker stay on an internal Compose network with no published port.
- Project dirs: `/home/kms/personal-brain-v1` (code), `-data` (runtime),
  `-backups` (staging). Never under `/home/kms/A/projects`.
- Compose: `deploy/compose.yaml` (deployed; API published only on the approved
  LAN address; DB and worker remain internal).
- Dockerfile: `deploy/Dockerfile` (non-root, reproducible).
- Secrets: mounted files only; never embedded in Compose/images/Git.
- Target `deploy/.env` is mode 0600 and contains only the three absolute secret
  file paths required for repeatable `docker compose` operations; it is ignored
  by Git and contains no secret value.
- Real personal data import is gated on verified backup + isolated restore
  (US10). External ChatGPT web access requires a separately approved HTTPS route.

## Current state

- Production-shaped Compose starts PostgreSQL, runs migration 0001..0011, then
  starts API and worker.
- `/ready` reports database, worker and storage healthy from both server and the
  Windows LAN client.
- Secrets are file-backed. The API/worker run non-root and no credential value
  is stored in Compose, the image or Git.

## Pending gates

1. Independent backup medium verified.
2. ChatGPT reachable HTTPS/OAuth route approved.
3. LAN TLS/transport decision before sensitive real-data use.
