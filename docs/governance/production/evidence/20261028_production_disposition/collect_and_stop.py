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
b=Path('/srv/bonira');out=b/'production-disposition-evidence'
for name in ['PITR_RESULT.json','CADENCE_CUSTODY_RESULT.json','WEB_OPERATIONS_RESULT.json','FINAL_RELEASE_IDENTITY.json','CURRENT_AUDIT_RECOVERY.json']:
 assert json.loads((out/name).read_text())['result']=='PASS'
assert json.loads((out/'FINAL_APP_TESTS.json').read_text())['failed']==0
assert json.loads((out/'OPS_ACCESS_TESTS.json').read_text())['failed']==0
freeze=json.loads((b/'source-production-disposition/SOURCE_FREEZE.json').read_text())
for root in [b/'source-production-disposition',b/'releases/production-disposition-current']:
 assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in freeze.items())
tools={}
for p in sorted((b/'tools').glob('guest_*.py')):
 shutil.copyfile(p,out/('EXECUTED_'+p.name));tools[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
values=set()
for p in (b/'secrets').glob('*.env'):
 for line in p.read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1)
   if ('PASSWORD' in k or 'SECRET' in k) and len(v)>=12:values.add(v.encode())
for name in ['admin-password','app-password']:
 values.add((b/'pitr-production'/name).read_bytes())
values.add((b/'pitr-production/repl.pgpass').read_text().strip().split(':')[-1].encode())
files=[p for p in out.rglob('*') if p.is_file()]
for p in files:
 assert not p.is_symlink()
 data=p.read_bytes()
 assert not any(v in data for v in values), 'Generated secret in '+p.name
 assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{100,}',data), 'Private key in '+p.name
running=set(subprocess.run(['docker','ps','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.splitlines())
assert running=={'bonira-db','bonira-pitr-source','bonira-pitr-restored'},running
assert subprocess.run(['systemctl','is-active','bonira-gate11-capture.timer'],capture_output=True,text=True).stdout.strip()!='active'
check={'result':'PASS','source_files_verified':len(freeze),'release_mount_source_verified':True,'executed_tools_sha256':tools,'files_screened':len(files),'generated_secrets_absent':True,'private_key_blocks_absent':True,'timer_stopped':True,'second_filesystem':Path('/srv/bonira-production-vault').stat().st_dev != (b/'pitr-production').stat().st_dev,'production':False}
(out/'FINAL_TARGET_CHECK.json').write_text(json.dumps(check,indent=2)+'\n')
with tarfile.open(b/'production-disposition-public-20261028.tar.gz','w:gz') as tar:
 for p in sorted(out.rglob('*')):
  if p.is_file():tar.add(p,arcname=p.relative_to(out).as_posix(),recursive=False)
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
    local = PRIVATE / "production-disposition-public-20261028.tar.gz"
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
            "root@127.0.0.1:/srv/bonira/production-disposition-public-20261028.tar.gz",
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
r=subprocess.run(['nginx','-s','quit','-c',str(b/'nginx.conf')],capture_output=True,check=False)
assert r.returncode==0
for name in ['bonira-pitr-source','bonira-pitr-restored']:
 subprocess.run(['docker','stop','--time','30',name],capture_output=True,check=True)
subprocess.run(['docker','stop','--time','30','bonira-db'],capture_output=True,check=True)
assert not subprocess.run(['docker','ps','-q'],capture_output=True,text=True,check=True).stdout.strip()
subprocess.run(['sync'],check=True)
subprocess.run(['umount','/srv/bonira-production-vault'],check=True)
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
                "nginx_quit": True, "pitr_services_stopped": True, "backup_vault_unmounted": True, "backup_timer_stopped": True,
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
