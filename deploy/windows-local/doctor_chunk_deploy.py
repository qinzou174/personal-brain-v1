"""Post-deploy doctor check via api container (ops token from model-proxy bind)."""
from _ssh import open_client

cli = open_client()
cmd = r"""
docker exec personal-brain-v1-prod-api-1 python -c "
import urllib.request
token = open('/run/model-proxy/doctor_token').read().strip()
req = urllib.request.Request('http://127.0.0.1:18083/doctor', headers={'Authorization': 'Bearer ' + token})
print(urllib.request.urlopen(req, timeout=10).read().decode()[:900])
"
"""
_, out, err = cli.exec_command(cmd, timeout=120)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:500])
cli.close()
