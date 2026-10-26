"""Read-only CEP078 continuation baseline; no product or Git mutation."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / '.pytest_cache/cep_tools'))
import yaml

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()
registry = yaml.safe_load((ROOT/'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf8'))
old = json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
assert sha(ROOT/'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md') == old['canonical_sha']
paths = subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard'],text=True).splitlines()
record = {
    'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'head': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'origin_main': subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip(),
    'branch': subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
    'status': subprocess.check_output(['git','status','--short'],text=True),
    'cep078_before': registry['ceps']['CEP-078'],
    'all_other_cep_hashes': {k:digest(v) for k,v in registry['ceps'].items() if k!='CEP-078'},
    'gate_state':registry['gates'], 'summary':registry['summary'],
    'frontier':registry['execution_frontier'],
    'canonical_sha':old['canonical_sha'],
    'prior_files':{p:sha(ROOT/p) for p in paths if (ROOT/p).is_file() and p!='docs/governance/cep/evidence/CEP-078_REMAINDER_02/ENTRY_RESUME.json'},
    'scope':'CEP078 remaining runtime and synchronization of captured Edge390 only; no completed coverage rerun, product changes, other CEP execution, broad regression, Git writes or Production',
}
assert record['head']==record['origin_main']=='961e3fd942c668337012c22d42f59545c5e9fc0a'
assert record['branch']=='main'
assert registry['ceps']['CEP-003']['execution']['status']=='COMPLETE'
assert registry['ceps']['CEP-017']['execution']['status']=='COMPLETE'
target=OUT/'ENTRY_RESUME.json'
assert not target.exists()
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Baseline retained; canonical SHA matches; CEP003/017 COMPLETE; current scoped entry retained; other85 CEPs and Gates snapshotted.')
