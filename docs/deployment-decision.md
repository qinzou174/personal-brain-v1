# Personal Brain V1 deployment decision (Phase 0)

Decision date: 2026-09-23 Asia/Shanghai. Target: `kms@192.168.10.7`. This is a layout and ownership decision, **not** a deployment record. Evidence: [environment report](environment-report.md), owner replies on 2026-09-23, and a subsequent read-only `/home/kms` sibling-directory and port check.

## Approved access boundary and phasing

- Initial V1 stage is LAN-only. The owner accepted core service and local-client verification first. ChatGPT web direct connection is deferred until a separately approved, authenticated HTTPS reachability path exists; do not claim its acceptance or overall V1 completion in this stage.
- Do not modify the existing Nginx sites, certificates, NAT/FRP, firewall, soft-router, NAS, ports 53/7890, or other running services for this stage.
- A future public/remote route is **not approved** by this decision. It requires a fresh read-only SNI/port/certificate/owner check, threat review, rollback plan and explicit owner approval.

## Exact project layout and ownership

| Purpose | Selected location / endpoint | Basis and boundary |
|---|---|---|
| Independent project code/config | `/home/kms/personal-brain-v1` | Owner corrected the proposed `/home/kms/A/projects/...` location and instructed placing a new project beside `/home/kms/A`, `/home/kms/nas`, and `/home/kms/soft-router`. This new name is selected under that instruction. No existing path is moved or reused. |
| Persistent Brain runtime data | `/home/kms/personal-brain-v1-data` | Separate new sibling directory for database and asset bind mounts. Not the pre-existing `/home/kms/data` and not an existing NAS directory. Application paths must be explicit subdirectories, owned only by the dedicated service identity/authorized operator. |
| LAN API/MCP candidate bind | `192.168.10.7:18081` | Read-only `ss` check found no listener on 18081 at decision time. Bind IPv4 LAN address only, not `0.0.0.0`, `[::]`, port 80/443, or an existing Nginx upstream. Recheck immediately before bind. This is an implementation choice under the owner's LAN-only directive, not proof that network ACLs are safe. |
| DB, worker, maintenance | Docker internal network only; no host-published port | Maintain strict service boundaries and authentication. |
| Backup staging | `/home/kms/personal-brain-v1-backups` (new sibling, if created) | Same root filesystem as data: useful for local restore rehearsal, **not** an independent disaster backup. Do not import real personal data until an off-host/independent backup destination, encryption/retention, capacity and isolated restore test are decided and verified. |

All selected project directories are new; the read-only directory listing showed none of these names in `/home/kms` on 2026-09-23. `/home/kms` has `kms`-owned siblings, but creation and service permissions still require preflight. No directory or listener was created by this decision.

## Unresolved gates before real data or remote access

1. Select and verify an independent backup medium/destination. Local sibling backup alone cannot meet ER-10 or the restore contract.
2. Establish actual service identity, exact directory permissions, secret provisioning and rollback before any remote mutation. Never embed secrets in Compose, images, Git or this document.
3. Recheck host IP, port occupancy, storage, existing site routes and service health immediately before deployment. Any conflict returns this decision to review.
4. ChatGPT browser integration needs a separately approved reachable HTTPS/OAuth route. LAN-only synthetic/local transport tests do not substitute for real ChatGPT account acceptance.
5. TLS is not assumed on the LAN endpoint; sensitive real-data use requires a reviewed transport/authentication arrangement even inside LAN.

Status: **Phase 0 layout selected; deployment and real-data gates remain pending.**
