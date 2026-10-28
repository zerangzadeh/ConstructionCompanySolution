"""Retain a failed synthetic fixture attempt and retry its atomic clean clone."""

import subprocess
from pathlib import Path

from run_post_checks import PRIVATE, SSH

OUT = Path(__file__).resolve().parent


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
            str(OUT / "bootstrap_probe.py"),
            "root@127.0.0.1:/srv/bonira/tools/bootstrap_legacy_probe.py",
        ],
        capture_output=True,
        check=True,
    )
    code = r"""
from pathlib import Path
import subprocess,json
b=Path('/srv/bonira');out=b/'legacy-decision-evidence'
n=1
while (out/('populated_ATTEMPT_'+str(n).zfill(2)+'_COMMAND.txt')).exists():n+=1
for name in ['populated_COMMAND.txt','populated_EXIT.json']:
 (out/name).rename(out/('populated_ATTEMPT_'+str(n).zfill(2)+'_'+name.split('_',1)[1]))
args=['docker','run','--rm','--network','bonira-pe','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=67108864','--env-file',str(b/'secrets/legacy-populated-retry1.env'),'-v',str(b/'source-legacy-decision')+':/app:ro','-v',str(b/'shared')+':/state','-v',str(b/'public')+':/static','-v',str(b/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(b/'tools')+':/tools:ro','-v',str(out)+':/evidence','bonira-pe-np-runtime:20261027','python','/tools/bootstrap_legacy_probe.py','finish','populated']
with (out/'populated_COMMAND.txt').open('w') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=False)
(out/'populated_EXIT.json').write_text(json.dumps({'exit_code':r.returncode,'phase':'populated','fixture':'Atomic test setup; original failed dataset preserved'}))
print('Populated qualification exit',r.returncode)
if r.returncode:print((out/'populated_COMMAND.txt').read_text()[-1800:])
"""
    result = subprocess.run(
        SSH + ["python3 -"], input=code, capture_output=True, text=True, check=False
    )
    (OUT / "POPULATED_RETRY_LATEST_HOST.txt").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    print(result.stdout)


if __name__ == "__main__":
    main()
