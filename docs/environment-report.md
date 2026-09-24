# Phase 0 target-host environment report

Observed: 2026-09-23 02:37 Asia/Shanghai. Target: `kms@192.168.10.7` (SSH host already present in local known_hosts; existing key authentication succeeded). Scope: read-only inventory for Personal Brain V1. No process, container, network, firewall, Nginx or data was changed.

## Observed facts and evidence

| Area | Observation | Read-only evidence |
|---|---|---|
| Host/OS | Hostname `kms`; Ubuntu 24.04.4 LTS; Linux 6.8.0-139-generic; x86-64; local timezone Asia/Shanghai, clock synchronized | `uname -a`, `hostnamectl status`, `timedatectl`, `date --iso-8601=seconds` |
| CPU/RAM | Intel Xeon E5-2680 v2; 10 cores / 20 threads; 15 GiB RAM, ~13 GiB available; 4 GiB swap | `lscpu`, `free -h` |
| Disk | Root ext4 `/dev/sda2`, 468 GiB usable filesystem, 73 GiB used, 371 GiB available; no separate data or backup mount observed | `df -hT`, `lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS` |
| Container runtime | Docker 29.7.1; Compose v5.3.1; current user can run Docker read commands | `docker --version`, `docker info`, `docker compose version`, `docker ps -a` |
| Existing containers | `shiguang-douyin` healthy; `openlist`, `nas-imgproxy`, `natfrp-service` running; one stopped OpenList backup container. No PostgreSQL or Trilium container in this listing | `docker ps -a` |
| Docker networks/volumes | Networks include `baota_net`, `douyin-parser-web_default`, `hiclaw-net`, standard bridge/host/none. `docker volume ls` returned no named volumes; existing services may use bind mounts | `docker network ls`, `docker volume ls` |
| Nginx | Nginx 1.24.0 active. `/etc/nginx/conf.d/nas.conf` owns `nas.h2d954063.nyat.app` on 8443 and 53054 TLS; `/etc/nginx/conf.d/wangzhan1.conf` owns `www.h2d954063.nyat.app` on 80/443. Other site configs own loopback ports 8087/8089/8093/8095/8097. Existing upstreams use 4173, 8109, 5244, 8101, 1337 and others. `/etc/nginx/sites-enabled` is empty; configs are under `conf.d` | `systemctl is-active nginx`, `nginx -v`, `ls -l /etc/nginx/conf.d`, targeted `grep -H` for `server_name`, `listen`, `proxy_pass` in active `*.conf` |
| Listening ports | 80, 443, 8443, 53054, 5244, 22 and others in use; loopback 4173, 8101, 8102, 8087/8089/8093/8095/8097, 9090/9091, etc. 192.168.10.7:53 and :7890 are in use; must preserve them | `ss -lnt`, `ss -lntp` |
| Network | LAN address 192.168.10.7/24, default gateway 192.168.10.1; IPv6 global address present; DNS resolver 192.168.10.1. `natfrp-service` is running; Tailscale and cloudflared systemd units inactive, `tailscale` binary not found | `ip -brief address`, `ip route`, `resolvectl dns`, `systemctl is-active`, `command -v tailscale` |
| Database/Git | `psql` client not installed and host `postgresql` service inactive; Git 2.43.0. This does not rule out an external database | `psql --version`, `systemctl is-active postgresql`, `git --version` |
| Paths and ownership | `/home/kms/A/projects` exists, owned by kms; `/home/kms/nas` exists as a sibling of `A`, owned by kms; `/opt` and `/var/backups` are root owned; `/srv` root owned. An unrelated `/home/kms/disabled-services-backup-20260906` exists; it is not a Personal Brain backup destination | `ls -ld` on those exact paths, bounded `find /home/kms -maxdepth 2 -type d -iname '*backup*'` |
| Human note tool | No Trilium container observed in `docker ps -a`; host or remote instance status remains unknown | `docker ps -a` |
| DNS/TLS | Existing Nginx SSL blocks observed for NAS and main site. Personal Brain hostname, certificate issuance route, public/private access policy and exact certificate ownership remain unknown. `/etc/letsencrypt/live` was absent; existing TLS may use another location | Nginx targeted config lines, bounded path check |

## Conflicts, unknowns and risks

1. This host already serves multiple websites and NAS/proxy services. Do not change existing Nginx blocks or bind 80/443/8443/53054, 7890/53, or any observed occupied port without a separate exact routing and rollback decision.
2. No Personal Brain deployment path, dedicated volume, backup destination, domain, TLS certificate method or network exposure choice is approved yet. The existing `/home/kms/A/projects` is a candidate parent, not permission to create there.
3. Docker named-volume list is empty, but bind mounts of existing containers were not inspected; no conclusion about their data storage or backup coverage is made.
4. Personal Brain PostgreSQL/pgvector and Trilium will need separate installation or verified existing instances. Their version, security boundary, storage and backups are unselected.
5. The root filesystem has ample current space, but ER-10 retention capacity and restore time cannot be accepted until a backup target and representative backup size are measured.
6. Existing SSL endpoint configuration was inspected by directive names only; certificate paths, renewal and tunnel/public reachability need a dedicated later read-only check before a route is selected.

## Phase 0 disposition

Read-only environment inventory complete with observed values and explicit unknowns. T003 deployment decision remains open: choose and confirm the exact application path, DB/asset/backup paths, Brain hostname and route, internal ports, ownership and rollback plan. No target-host mutation is authorized by this report.
