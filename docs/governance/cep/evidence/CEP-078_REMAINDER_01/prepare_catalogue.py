"""Build a whitelisted read-only Development projection of approved definitions."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / '.pytest_cache/cep_tools'))
import yaml

sources = [
    'docs/governance/uiux/UIUX_REFERENCE_PERSONA_CATALOGUE.yaml',
    'docs/governance/uiux/UIUX_RUNTIME_PERSONA_DATA_MATRIX.yaml',
]
catalogue, matrix = [yaml.safe_load((ROOT / p).read_text(encoding='utf8')) for p in sources]
shapes = {p['persona_id']: p for p in matrix['personas']}
rows = []
for persona in catalogue['personas']:
    shape = shapes[persona['persona_id']]
    rows.append({
        'persona_id': persona['persona_id'],
        'label': persona['documentation_label_fa'],
        'target_alias': persona['reference_username_target'],
        'documented_identity': persona['reconciled_identity'],
        'documented_readiness': persona['provisioning_status'],
        'authority_shape': shape['required_authority_shape'],
        'context_requirements': shape['required_data'],
        'scenario_ids': shape['scenario_ids'],
    })
assert len(rows) == 26 and len({p['persona_id'] for p in rows}) == 26
result = {'sources': [{'path': p, 'sha256': hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in sources],
          'documented_at': catalogue['document']['approved_at'], 'personas': rows}
destination = ROOT / 'apps/organizations/reference_personas.json'
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print('26 approved definitions projected; no live account/tenant objects or secrets queried.')
