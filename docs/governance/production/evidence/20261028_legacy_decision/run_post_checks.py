"""New isolated test clone and native backup/restore; no existing DB mutation."""

import subprocess
from pathlib import Path

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

REMOTE = r"""
from pathlib import Path
from time import monotonic
import subprocess,json
b=Path('/srv/bonira');out=b/'legacy-decision-evidence'
assert all(json.loads((out/(phase+'_RESULT.json')).read_text())['result']=='PASS' for phase in ['empty','populated'])
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,check=False)
 if p.returncode:
  (b/'private-logs/legacy-post-failure.txt').write_text(p.stdout+p.stderr)
  raise RuntimeError('Owned post-check failed; private diagnostics retained')
 return p.stdout
base=dict(line.split('=',1) for line in (b/'secrets/legacy-pre.env').read_text().splitlines() if line)
def probe(database,action,label=''):
 values=dict(base,DB_NAME=database)
 env=b/'secrets'/('legacy-post-'+database+'.env')
 env.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n');env.chmod(0o600)
 args=['docker','run','--rm','--network','bonira-pe','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=67108864','--env-file',str(env),'-v',str(b/'source-legacy-decision')+':/app:ro','-v',str(b/'shared')+':/state','-v',str(b/'public')+':/static','-v',str(b/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(b/'tools')+':/tools:ro','-v',str(out)+':/evidence','bonira-pe-np-runtime:20261027','python','/tools/legacy_post_probe.py',action]
 if label:args.append(label)
 run(args)
start=monotonic()
populated=json.loads((out/'populated_RESULT.json').read_text())['database']
probe(populated,'fingerprint','RECOVERY_SOURCE')
run(['docker','exec','bonira-db','install','-d','-m','700','/tmp/bonira-legacy-retired'])
run(['docker','exec','-e','PGSERVICEFILE=/tmp/bonira-service.conf','bonira-db','pg_dump','--dbname=service=bonira_shared dbname='+populated,'--format=custom','--file=/tmp/bonira-legacy-retired/database.dump'])
run(['docker','exec','bonira-db','createdb','-U','bonira_admin','-O','bonira_app','-T','template0','pe_legacy_20261028_restored'])
run(['docker','exec','bonira-db','pg_restore','-U','bonira_admin','--role','bonira_app','--exit-on-error','--no-owner','--no-privileges','-d','pe_legacy_20261028_restored','/tmp/bonira-legacy-retired/database.dump'])
probe('pe_legacy_20261028_restored','fingerprint','RECOVERY_RESTORED')
before=json.loads((out/'RECOVERY_SOURCE_FINGERPRINT.json').read_text())
after=json.loads((out/'RECOVERY_RESTORED_FINGERPRINT.json').read_text())
assert before==after,'Full restored state differs'
(out/'RECOVERY_RESULT.json').write_text(json.dumps({'result':'PASS','tables':len(before['tables']),'rows':sum(v['rows'] for v in before['tables'].values()),'constraints':before['constraints_count'],'sequences':len(before['sequences']),'all_rows_constraints_sequences_equal':True,'seconds':monotonic()-start,'scope':'Native TLS backup/complete changed-schema restore integrity only; no new RPO/RTO/capacity/Production claim','production_action':False},indent=2))
run(['docker','exec','bonira-db','createdb','-U','bonira_admin','-O','bonira_app','-T','pe_legacy_20261028_empty','test_pe_legacy_20261028_regression'])
probe('pe_legacy_20261028_empty','regression')
print('PASS: complete restore and affected regressions',flush=True)
"""


def main():
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
            str(OUT / "post_probe.py"),
            "root@127.0.0.1:/srv/bonira/tools/legacy_post_probe.py",
        ],
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        SSH + ["python3 -"], input=REMOTE, capture_output=True, text=True, check=False
    )
    (OUT / "POST_HOST.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    print("Post-check exit", result.returncode, result.stdout)


if __name__ == "__main__":
    main()
