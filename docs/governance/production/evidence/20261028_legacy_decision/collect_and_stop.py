"""Screen/collect minimized evidence and cleanly stop only the owned guest."""

import ctypes
import hashlib
import json
import shutil
import socket
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

OUT = Path(__file__).resolve().parent
PRIVATE = Path("E:/BONIRA_Operations/ApprovedLinux/6e55fd45b4c04ce0")
SSH = [
    "ssh.exe",
    "-i",
    str(PRIVATE / "guest_key"),
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=6",
    "-o",
    "UserKnownHostsFile=" + str(PRIVATE / "known_hosts"),
    "-p",
    "22270",
    "root@127.0.0.1",
]

GUEST = r"""
import hashlib,json,re,shutil,subprocess,tarfile
from pathlib import Path
b=Path('/srv/bonira');out=b/'legacy-decision-evidence'
assert all(json.loads((out/(phase+'_RESULT.json')).read_text())['result']=='PASS' for phase in ['empty','populated'])
assert json.loads((out/'RECOVERY_RESULT.json').read_text())['result']=='PASS'
assert json.loads((out/'REGRESSION.json').read_text())['failed']==0
freeze=json.loads((b/'source-legacy-decision/SOURCE_FREEZE.json').read_text())
assert all(hashlib.sha256((b/'source-legacy-decision'/p).read_bytes()).hexdigest()==h for p,h in freeze.items())
tools={}
for n in ['bootstrap_legacy_probe.py','legacy_post_probe.py']:
 p=b/'tools'/n
 shutil.copyfile(p,out/('EXECUTED_'+n))
 tools[n]=hashlib.sha256(p.read_bytes()).hexdigest()
values=set()
for p in (b/'secrets').glob('*.env'):
 for line in p.read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1)
   if ('PASSWORD' in k or 'SECRET' in k) and len(v)>=12:values.add(v.encode())
files=[p for p in out.iterdir() if p.is_file()]
for p in files:
 data=p.read_bytes()
 assert not any(v in data for v in values), 'Generated secret in '+p.name
 assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{100,}',data), 'Private key in '+p.name
assert subprocess.run(['docker','ps','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.strip()=='bonira-db'
modes={}
for n in ['secrets','pki','shared/document_media','shared/configuration_metadata','shared/audit_operational']:
 modes[n]=oct((b/n).stat().st_mode & 0o777)
 assert modes[n]=='0o700'
for name in ['readiness-current','readiness-previous']:
 assert ((b/'public'/name).stat().st_mode & 0o777)==0o755
check={'result':'PASS','source_files_verified':len(freeze),'executed_tools_sha256':tools,'files_screened':len(files),'generated_secrets_absent':True,'private_key_blocks_absent':True,'protected_modes':modes,'public_static_modes':'0755 only dedicated public-static roots','production':False}
(out/'FINAL_TARGET_CHECK.json').write_text(json.dumps(check,indent=2)+'\n')
with tarfile.open(b/'legacy-decision-public-20261028.tar.gz','w:gz') as tar:
 for p in sorted(out.iterdir()):
  assert p.is_file() and not p.is_symlink()
  tar.add(p,arcname=p.name,recursive=False)
print(json.dumps(check))
"""


def main():
    process = subprocess.run(
        SSH + ["python3 -"],
        input=GUEST,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert process.returncode == 0, "Owned guest evidence screening failed"
    check = json.loads(process.stdout)
    local = PRIVATE / "legacy-decision-public-20261028.tar.gz"
    subprocess.run(
        [
            "scp.exe",
            "-i",
            str(PRIVATE / "guest_key"),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "UserKnownHostsFile=" + str(PRIVATE / "known_hosts"),
            "-P",
            "22270",
            "root@127.0.0.1:/srv/bonira/legacy-decision-public-20261028.tar.gz",
            str(local),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    target = OUT / "runtime"
    target.mkdir(exist_ok=False)
    with tarfile.open(local) as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and ".." not in name.parts
            destination = target.joinpath(*name.parts)
            assert destination.resolve().is_relative_to(target.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            with (
                archive.extractfile(member) as source,
                destination.open("wb") as output,
            ):
                shutil.copyfileobj(source, output)
    (OUT / "COLLECTION.json").write_text(
        json.dumps(
            {
                "at": datetime.now(UTC).isoformat(),
                "result": "PASS",
                "target_check": check,
                "archive_sha256": hashlib.sha256(local.read_bytes()).hexdigest(),
                "public_files": len(list(target.iterdir())),
                "private_resources": "retained outside Git",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    code = """
from pathlib import Path
import subprocess
b=Path('/srv/bonira')
assert not (b/'nginx.pid').exists(), 'Unexpected owned web process'
subprocess.run(['docker','stop','--time','30','bonira-db'],capture_output=True,check=True)
assert not subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip()
subprocess.run(['sync'],check=True)
subprocess.Popen(['shutdown','-h','now'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('OWNED_TARGET_CLEAN_SHUTDOWN')
"""
    stopped = subprocess.run(
        SSH + ["python3 -"],
        input=code,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "OWNED_TARGET_CLEAN_SHUTDOWN" in stopped.stdout
    pid = json.loads((OUT / "TARGET_START.json").read_text())["owned_pid"]
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if handle:
        try:
            assert kernel.WaitForSingleObject(handle, 45000) == 0
        finally:
            kernel.CloseHandle(handle)
    for port in (22270, 24470):
        with socket.socket() as connection:
            connection.settimeout(0.2)
            assert connection.connect_ex(("127.0.0.1", port)) != 0
    (OUT / "SHUTDOWN.json").write_text(
        json.dumps(
            {
                "at": datetime.now(UTC).isoformat(),
                "result": "PASS",
                "web_service_not_started_in_this_run": True,
                "database_stopped": True,
                "no_running_containers": True,
                "sync_complete": True,
                "owned_guest_process_exited": True,
                "owned_listeners_closed": [22270, 24470],
                "private_disk_bundles_secrets_retained": True,
                "production": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: screened evidence collected; owned services/guest stopped; listeners closed"
    )


if __name__ == "__main__":
    main()
