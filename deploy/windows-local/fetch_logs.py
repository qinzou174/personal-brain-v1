import sys
import paramiko

from _ssh import open_client

cmd = sys.argv[1] if len(sys.argv) > 1 else "echo no-cmd"

cli = open_client()
stdin, stdout, stderr = cli.exec_command(cmd, timeout=120)
out = stdout.read().decode("utf-8", "replace")
err = stderr.read().decode("utf-8", "replace")
print(out)
if err:
    print("--- STDERR ---")
    print(err)
cli.close()
