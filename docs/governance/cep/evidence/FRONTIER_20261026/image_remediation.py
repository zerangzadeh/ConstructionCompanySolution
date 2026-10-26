"""Bounded same-target immutable image refresh, authorized by current Human task."""
import datetime
import hashlib
import json
import re
from pathlib import Path
import subprocess

OUT=Path(__file__).parent
load=lambda name:json.loads((OUT/name).read_text(encoding='utf8'))
review=load('IMAGE_REVIEW.json')
old=review['expected']; new=review['current_linux_amd64'][0]
index=review['artifacts'][old['tag']]['content_digest']
old_manifest=load('IMAGE_'+old['platform_digest'].replace(':','_')+'.json')
new_manifest=load('IMAGE_'+new['digest'].replace(':','_')+'.json')
old_config=load('IMAGE_'+old_manifest['config']['digest'].replace(':','_')+'.json')
new_config=load('IMAGE_'+new_manifest['config']['digest'].replace(':','_')+'.json')
assert old_config['architecture']==new_config['architecture']=='amd64'
assert old_config['os']==new_config['os']=='linux'
assert old_config['config']==new_config['config']
assert [x.get('created_by') for x in old_config['history'][1:]]==[x.get('created_by') for x in new_config['history'][1:]]
for config in [old_config,new_config]:
    assert re.fullmatch(r"# debian.sh --arch 'amd64' out/ 'bookworm' '@[0-9]+'",config['history'][0]['created_by'])
assert new['annotations']['org.opencontainers.image.version']==old['tag']
assert new['annotations']['org.opencontainers.image.base.name']=='debian:bookworm-slim'
assert new['annotations']['org.opencontainers.image.source'].startswith('https://github.com/docker-library/python.git#')
for reference,row in review['artifacts'].items():
    assert row['status']==200
    if reference.startswith('sha256:'): assert row['sha256']==reference[7:]
assert review['artifacts'][old['tag']]['sha256']==index[7:]
entry=load('ENTRY.json')
paths=['security/supply_chain/build_image.json','.github/workflows/supply-chain.yml','.github/workflows/cep013-pure-psycopg-verify.yml']
entry['touch_set']+=paths
(OUT/'ENTRY.json').write_text(json.dumps(entry,indent=2)+'\n',encoding='utf8')
# Reconcile the independently observed Human checkpoints before configuration mutation.
p=Path('CEP_EXECUTION_REGISTRY.yaml'); text=p.read_text(encoding='utf8')
start=text.index('repository_state:\n'); end=text.index('execution_frontier:\n',start)
section=text[start:end]
section=section.replace('last_reconciled_head: '+entry['prior_registry_head'],'last_reconciled_head: '+entry['head'])
section=section.replace('origin_main: '+entry['prior_registry_head'],'origin_main: '+entry['origin_main'])
section=section.replace("last_reconciled_at: '2026-10-25'","last_reconciled_at: '2026-10-26'")
section=section.replace('pending_checkpoint_scope: UNCOMMITTED_CEP069_078_FRONTIER_EVIDENCE_AND_CEP072_TELEMETRY_FOUNDATION','pending_checkpoint_scope: CURRENT_FRONTIER_20261026_UNCOMMITTED_CHANGES_ONLY')
section=section[:section.index('  metadata_boundary:')]+('  metadata_boundary: Human checkpoints325b32f and961e3fd inspected read-only; local main and origin/main agree at current HEAD. Prior frontier foundation and UIUX changes committed by Human; current session uncommitted. No remote freshness query or Git writes.\n')
p.write_text(text[:start]+section+text[end:],encoding='utf8')
mutations={}
for name in paths:
    p=Path(name); before=p.read_bytes(); text=before.decode('utf8')
    text=text.replace(old['platform_digest'],new['digest'])
    if name.endswith('build_image.json'):text=text.replace(old['index_digest'],index)
    after=text.encode('utf8'); assert before!=after
    p.write_bytes(after)
    mutations[name]={'before':hashlib.sha256(before).hexdigest(),'after':hashlib.sha256(after).hexdigest()}
record={
    'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'authority':'Current direct Human request prioritizes CEP077 image identity blocker and authorizes safely attributable Development configuration defects; separate bounded implementation action before verification, per canonical CEP077 section7',
    'technical_review':'Official HTTPS registry index/platform/config content hashes all verified. Same approved source/tag/OS/architecture/Python source hash/environment/config and identical Python build instructions. Debian bookworm base snapshot timestamp changed from1791158400 to1792531975; initial full-history equality assertion caught this expected base rebuild and stopped before mutation. Official rebuild created2026-10-21; old artifact remains retrievable. No target, application dependency, license, vulnerability, CI-permission, signing or fail-closed policy changes.',
    'old':old,'new_index':index,'new_platform':new['digest'],'upstream_annotations':new['annotations'],
    'checks':{'all_fetched_content_addresses_match':True,'same_runtime_config':True,'same_build_instructions':True,'same_approved_target':True},
    'mutations':mutations,'remaining_validation':'Fresh existing gate and focused fail-closed tests required; prior supply-chain PASS invalid for refreshed image',
    'production_attestation_certification':'NOT_EXECUTED; no Security Reviewer impersonation, waiver or residual risk acceptance',
}
(OUT/'IMAGE_REMEDIATION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print('Reviewed same-target image pins refreshed in3 existing references; gate unchanged')
