"""Current Development-only identity/preservation snapshot; no fixture writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
sys.path.insert(0, str(ROOT / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard, snapshot, REAL_NOW
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.authorization import membership_permission_codes, effective_role_assignments, effective_scope_grants, is_platform_admin

def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()

guard()
assert not (OUT / 'ENTRY.json').exists()
old = json.loads((OUT.parent / 'CEP-078_REENTRY_02/ENTRY.json').read_text(encoding='utf-8'))
assert all(sha(ROOT / p) == v for p, v in old['product_hashes'].items())
assert git('rev-parse', 'HEAD') == old['head']
assert git('diff', '--cached', '--name-only') == ''
prompt = ROOT / 'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md'
assert sha(prompt) == '313eb92ea69db33fe2ccaa6d881a6346949286aa8d9c688ac87dd820b0e92030'
history = {p.relative_to(ROOT).as_posix(): sha(p) for p in OUT.parent.rglob('*') if p.is_file() and OUT not in p.parents}
uiux = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / 'docs/governance/uiux').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
save('ENTRY.json', {'at': REAL_NOW(), 'branch': git('branch', '--show-current'), 'head': git('rev-parse', 'HEAD'), 'upstream': git('rev-parse', '@{u}'), 'origin_main': git('rev-parse', 'origin/main'), 'status': git('status', '--short'), 'diff_name_status': git('diff', '--name-status'), 'diff_stat': git('diff', '--stat'), 'index_sha256': sha(ROOT / '.git/index'), 'product_hashes': old['product_hashes'], 'prior_cep_evidence': history, 'accepted_uiux_files': uiux, 'registry_before': (ROOT / 'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf-8'), 'prompt_sha256': sha(prompt), 'entry': 'PASS_RETAINED; separate bounded remediation authority now explicit', 'gate07': 'SCOPED_PASS_REUSED_NOT_RERUN', 'ext0024': 'APPROVED_CHROME_EDGE_PASS_RETAINED; runtime continuity observation per session', 'touch_set': ['templates/accounts/login.html minimal landmark wrapper', 'this directory', 'bounded CEP078 Registry reconciliation']})
data = snapshot()
save('DATA_BEFORE.json', {name: hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest() for name, rows in data.items()})
org = Organization.objects.get(slug='demo-construction-01')
actors = []
for m in OrganizationMembership.objects.select_related('user').filter(organization=org):
    if m.user.username.startswith('uiux.') or m.user.username in {'admin', 'account.demo-construction-01.owner'}:
        actors.append({'alias': m.user.username, 'active': m.user.is_active, 'organization': org.slug, 'membership': str(m.pk), 'status': m.status, 'roles': list(effective_role_assignments(m).values_list('role__code', flat=True)), 'permissions': sorted(membership_permission_codes(m)), 'scope': list(effective_scope_grants(m).values('scope_type', 'project_id', 'site_id')), 'platform_admin': is_platform_admin(m.user)})
save('ACTOR_READINESS.json', {'at': REAL_NOW(), 'actors': actors, 'platform_admins': [u.username for u in User.objects.filter(is_active=True) if is_platform_admin(u)], 'no_grant_or_identity_writes': True})
print('Entry preserved:1497 source hashes; prior evidence snapshot; Development guard PASS; actors:', len(actors))
