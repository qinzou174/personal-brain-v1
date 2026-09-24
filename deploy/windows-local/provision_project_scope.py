"""Grant a dynamically created project scope to the Windows-Local-Trial client.

Usage: python provision_project_scope.py <project_id>
Mirrors the LAN deployment provisioning: adds project:<uuid> to the client's
scopes, ensures project.read in allowed_tools, and inserts allow grants.
"""
import json
import os
import subprocess
import sys
from urllib.parse import urlparse

CLIENT_ID = "91914bb7-461b-481d-8993-8970251e0cc7"
PSQL = r"E:\Personal-Brain-V1-local\postgres\Library\bin\psql.exe"
_DSN = urlparse(open(r"E:\Personal-Brain-V1-local\secrets\db-dsn").read().strip()
                .replace("postgresql+psycopg://", "postgresql://"))
ENV = dict(os.environ, PGPASSWORD=_DSN.password or "")


def psql(sql: str) -> str:
    r = subprocess.run(
        [PSQL, "-h", _DSN.hostname, "-p", str(_DSN.port or 5432), "-U", _DSN.username,
         "-d", _DSN.path.lstrip("/"), "-At", "-c", sql],
        capture_output=True, text=True, timeout=30, env=ENV)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()


def provision(project_id: str) -> None:
    scope = f"project:{project_id}"
    scopes = json.loads(psql(f"select scopes from clients where id='{CLIENT_ID}'"))
    if scope not in scopes:
        scopes.append(scope)
    tools = json.loads(psql(f"select allowed_tools from clients where id='{CLIENT_ID}'"))
    if "project.read" not in tools:
        tools.append("project.read")
    psql(f"update clients set scopes='{json.dumps(scopes)}', allowed_tools='{json.dumps(tools)}', "
         f"updated_at=now(), version=version+1 where id='{CLIENT_ID}'")
    for tool in ("project.read", "project.write"):
        psql(f"insert into permission_grants (id, client_id, effect, scope_pattern, tool_pattern, "
             f"sensitivity_ceiling, effective_from, issuer, reason, created_at, updated_at, version) "
             f"values (gen_random_uuid(), '{CLIENT_ID}', 'allow', '{scope}', '{tool}', 'private', "
             f"now(), 'owner_local_operator', 'smoke-test provisioning', now(), now(), 1) "
             f"on conflict do nothing")
    print(f"provisioned {scope} (+project.read)")


if __name__ == "__main__":
    provision(sys.argv[1])
