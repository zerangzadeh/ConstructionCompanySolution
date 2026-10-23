"""Read an existing local DPAPI credential into a caller's memory; never save it."""
import re
import subprocess
import sys
alias = sys.argv[1]
assert re.fullmatch(r"[A-Za-z0-9.-]+", alias)
program = "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/" + alias + ".clixml'); [Console]::Write($c.GetNetworkCredential().Password)"
result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, check=True)
sys.stdout.write(result.stdout)
