"""Owned qualification transport; private credentials never enter repository outputs."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
PRIVATE = Path("E:/BONIRA_Operations/ApprovedLinux/6e55fd45b4c04ce0")
COMMON = ["-i", str(PRIVATE / "guest_key"), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", "-o", "UserKnownHostsFile=" + str(PRIVATE / "known_hosts")]
SSH = ["ssh.exe", *COMMON, "-p", "22270", "root@127.0.0.1"]


def remote(code):
    return subprocess.run(SSH + ["python3 -"], input=code, capture_output=True, text=True, encoding="utf-8", check=False)


def copy(source, destination):
    subprocess.run(["scp.exe", *COMMON, "-P", "22270", str(source), "root@127.0.0.1:" + destination], capture_output=True, check=True)


def sync():
    names = set(json.loads((OUT.parent / "20261028_legacy_decision/SOURCE_FREEZE_FINAL.json").read_text()))
    names.update([
        "apps/payroll/test_production_governance.py", "core/production_operations.py",
        "scripts/production_recovery.py", "tests/test_production_operations.py", "config/gunicorn_production.py",
        "docs/governance/production/PRODUCTION_SCOPED_DISPOSITIONS_20261028.md",
        "docs/governance/production/PRODUCTION_STATUTORY_ENVELOPES.json",
    ])
    freeze = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(names)}
    archive = PRIVATE / "production-disposition-source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in freeze:
            tar.add(ROOT / name, arcname="source-production-disposition/" + name, recursive=False)
        data = json.dumps(freeze, indent=2).encode()
        member = tarfile.TarInfo("source-production-disposition/SOURCE_FREEZE.json")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
        for path in OUT.glob("guest_*.py"):
            tar.add(path, arcname="tools/" + path.name, recursive=False)
    copy(archive, "/srv/bonira/production-disposition-source.tar.gz")
    result = remote("import subprocess\nsubprocess.run(['tar','-xzf','/srv/bonira/production-disposition-source.tar.gz','-C','/srv/bonira'],check=True)\n")
    assert result.returncode == 0
    (OUT / "SOURCE_FREEZE.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    print("Source synchronized:", len(freeze))


if __name__ == "__main__":
    if sys.argv[1] == "sync":
        sync()
    else:
        script = sys.argv[1]
        copy(OUT / script, "/srv/bonira/tools/" + script)
        result = remote((OUT / script).read_text("utf-8"))
        (OUT / (script + "_HOST.txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
        print("Owned command exit", result.returncode, result.stdout)
