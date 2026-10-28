"""Run isolated empty and populated migration cases after pre-graph preparation."""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
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


def main():
    previous = json.loads((OUT / "SOURCE_FREEZE.json").read_text("utf-8"))
    freeze = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in previous
    }
    archive = PRIVATE / "legacy-decision-final-source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in freeze:
            tar.add(
                ROOT / name, arcname="source-legacy-decision/" + name, recursive=False
            )
        data = json.dumps(freeze, indent=2).encode()
        member = tarfile.TarInfo("source-legacy-decision/SOURCE_FREEZE.json")
        member.size, member.mode = len(data), 0o644
        tar.addfile(member, io.BytesIO(data))
        tar.add(OUT / "bootstrap_probe.py", arcname="tools/bootstrap_legacy_probe.py")
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
            str(archive),
            "root@127.0.0.1:/srv/bonira/legacy-decision-final-source.tar.gz",
        ],
        capture_output=True,
        check=True,
    )
    remote = r"""
import subprocess,json
from pathlib import Path
b=Path('/srv/bonira');out=b/'legacy-decision-evidence'
assert json.loads((out/'PREPARED.json').read_text())['result']=='PASS'
subprocess.run(['tar','-xzf',str(b/'legacy-decision-final-source.tar.gz'),'-C',str(b)],check=True)
base=dict(line.split('=',1) for line in (b/'secrets/legacy-pre.env').read_text().splitlines() if line)
for phase in ['empty','populated']:
 name='pe_legacy_20261028_'+phase
 subprocess.run(['docker','exec','bonira-db','createdb','-U','bonira_admin','-O','bonira_app','-T','pe_legacy_20261028_pre',name],check=True,capture_output=True)
 values=dict(base,DB_NAME=name)
 p=b/'secrets'/('legacy-'+phase+'.env')
 p.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n');p.chmod(0o600)
 command=['docker','run','--rm','--network','bonira-pe','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=67108864','--env-file',str(p),'-v',str(b/'source-legacy-decision')+':/app:ro','-v',str(b/'shared')+':/state','-v',str(b/'public')+':/static','-v',str(b/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(b/'tools')+':/tools:ro','-v',str(out)+':/evidence','bonira-pe-np-runtime:20261027','python','/tools/bootstrap_legacy_probe.py','finish',phase]
 with (out/(phase+'_COMMAND.txt')).open('w') as log:
  process=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
 (out/(phase+'_EXIT.json')).write_text(json.dumps({'exit_code':process.returncode,'phase':phase}))
 if process.returncode:raise SystemExit('Bounded '+phase+' qualification failed; inspect retained output')
 print(phase+' PASS',flush=True)
"""
    (OUT / "SOURCE_FREEZE_FINAL.json").write_text(
        json.dumps(freeze, indent=2) + "\n", encoding="utf-8"
    )
    result = subprocess.run(
        SSH + ["python3 -"], input=remote, capture_output=True, text=True, check=False
    )
    (OUT / "CASES_HOST.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    print("Qualification cases exit", result.returncode, result.stdout)


if __name__ == "__main__":
    main()
