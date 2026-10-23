"""Resume an interrupted approved browser matrix without altering retained evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard, snapshot, REAL_NOW

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

guard()
assert not (OUT / 'ENTRY.json').exists()
old = json.loads((OUT.parent / 'CEP-078_REENTRY_03/ENTRY.json').read_text(encoding='utf-8'))
current = {p: sha(ROOT / p) for p in old['product_hashes']}
changes = [p for p, v in current.items() if v != old['product_hashes'][p]]
expected = {'apps/accounts/static/js/erp_table.js', 'apps/organizations/tests.py', 'apps/organizations/views.py', 'apps/subledgers/templates/subledgers/workbench.html', 'templates/accounts/login.html', 'templates/base.html', 'templates/components/table_sort_header.html', 'templates/organizations/members.html', 'templates/procurement/portal_context.html', 'templates/projects/list.html', 'templates/reporting/project_closeout_detail.html'}
assert set(changes) == expected, changes
assert git('rev-parse', 'HEAD') == old['head']
assert git('diff', '--cached', '--name-only') == ''
prompt = ROOT / 'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md'
assert sha(prompt) == '313eb92ea69db33fe2ccaa6d881a6346949286aa8d9c688ac87dd820b0e92030'
save('ENTRY.json', {'at': REAL_NOW(), 'branch': git('branch', '--show-current'), 'head': git('rev-parse', 'HEAD'), 'origin_main': git('rev-parse', 'origin/main'), 'upstream': git('rev-parse', '@{u}'), 'status': git('status', '--short'), 'diff_name_status': git('diff', '--name-status'), 'diff_stat': git('diff', '--stat'), 'index_sha256': sha(ROOT / '.git/index'), 'product_hashes': current, 'accepted_reentry03_changes': changes, 'prior_evidence': {p.relative_to(ROOT).as_posix(): sha(p) for folder in [OUT.parent / f'CEP-078_REENTRY_0{i}' for i in range(1, 4)] for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}, 'registry_before': (ROOT / 'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf-8'), 'prompt_sha256': sha(prompt), 'authority': 'Direct Human resume CEP078 remaining Chrome+Edge runtime and existing bounded technical remediation; no CEP079/Production/Human Sign-off/Git writes', 'entry': 'Retained canonical identity, dependencies and scoped GATE07; fresh browser-control proof; exact runtime continuity checked separately', 'touch_set': ['this directory and bounded CEP078 Registry reconciliation', 'only runtime-proven minimal technical UI defects if needed'], 'interruption_classification': 'Tooling/session interruption only; unobserved runtime remains UTV, never product FAIL'})
save('DATA_BEFORE.json', snapshot())
print('Resume entry PASS:', len(current), 'product sources pinned;', len(changes), 'accepted prior remediation changes; retained evidence hashes saved.')
