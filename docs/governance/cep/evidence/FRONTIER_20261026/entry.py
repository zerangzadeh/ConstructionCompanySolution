"""Read-only entry grounding and official image evidence; no pin changes."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys
import urllib.request
import urllib.error

sys.path.insert(0, str(Path('.pytest_cache/cep_tools').resolve()))
import yaml

OUT = Path(__file__).parent
def sha(data):
    return hashlib.sha256(data).hexdigest()
def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()
def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, default=str)+'\n', encoding='utf8')

registry = yaml.safe_load(Path('CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf8'))
manifest = yaml.safe_load(Path('docs/governance/cep/CEP_PROMPT_MANIFEST.yaml').read_text(encoding='utf8'))
entry = {
    'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'head': git('rev-parse', 'HEAD'), 'origin_main': git('rev-parse', 'origin/main'),
    'branch': git('branch', '--show-current'), 'status': git('status', '--short'),
    'prior_registry_head': registry['repository_state']['last_reconciled_head'],
    'authority': 'Current direct Human frontier continuation and attributable Development fixes; no Production or Git writes',
    'canonical_prompts': {},
    'prerequisites': {k: registry['ceps'][k]['execution'] for k in ['CEP-003','CEP-013','CEP-017']},
    'before_records': {k: v for k,v in registry['ceps'].items() if 69 <= int(k[4:]) <= 79},
    'protected_hashes': {},
    'touch_set': ['CEP_EXECUTION_REGISTRY.yaml', str(OUT), 'docs/governance/cep/reports/CEP-077_COMPLETION_REPORT.md', 'docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md'],
    'source_identity': {},
    'remote_freshness': 'Local origin/main only; no fetch/push',
}
for n in range(69,79):
    key=f'CEP-{n:03d}'; row=manifest['prompts'][key]; actual=sha(Path(row['path']).read_bytes())
    assert actual == row['sha256'], key
    entry['canonical_prompts'][key]={'sha256': actual, 'verified': True}
for name in ['docs/governance/uiux/UIUX_FINDING_CLOSURE_MASTER.yaml','security/supply_chain/build_image.json','scripts/supply_chain.py']:
    entry['protected_hashes'][name]=sha(Path(name).read_bytes())
for name in git('ls-files','apps','core','config','templates','security','requirements-prod-linux.lock','requirements-dev-linux.lock').splitlines():
    if Path(name).is_file(): entry['source_identity'][name]=sha(Path(name).read_bytes())
save('ENTRY.json', entry)

image=json.loads(Path('security/supply_chain/build_image.json').read_text())
token=json.load(urllib.request.urlopen('https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull',timeout=30))['token']
headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'}
review={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'expected':image,'official_source':'https://registry-1.docker.io/v2/library/python/','artifacts':{},'pin_mutation':False,'review_approval_or_security_clearance':'NOT_ISSUED'}
def fetch(kind, reference):
    req=urllib.request.Request(review['official_source']+kind+'/'+reference,headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw=response.read(); value=json.loads(raw)
            review['artifacts'][reference]={'status':response.status,'sha256':sha(raw),'content_digest':response.headers.get('Docker-Content-Digest'),'content_type':response.headers.get('Content-Type')}
            save('IMAGE_'+reference.replace(':','_')+'.json',value)
            return value
    except urllib.error.HTTPError as err:
        review['artifacts'][reference]={'status':err.code,'reason':err.reason}
        return None
current=fetch('manifests',image['tag'])
old=fetch('manifests',image['index_digest'])
old_platform=fetch('manifests',image['platform_digest'])
if current:
    matches=[v for v in current.get('manifests',[]) if v.get('platform',{}).get('os')=='linux' and v.get('platform',{}).get('architecture')=='amd64']
    review['current_linux_amd64']=matches
    if len(matches)==1:
        new_platform=fetch('manifests',matches[0]['digest'])
        if new_platform and new_platform.get('config'): fetch('blobs',new_platform['config']['digest'])
if old_platform and old_platform.get('config'): fetch('blobs',old_platform['config']['digest'])
save('IMAGE_REVIEW.json',review)
print(json.dumps({'head':entry['head'],'canonical_prompts_verified':len(entry['canonical_prompts']),'image_artifacts':review['artifacts']},indent=2))
