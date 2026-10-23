"""Verify this continuation changes only its explicitly authorized test cleanup."""
import json
from pathlib import Path
import sys
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard, snapshot, REAL_NOW
guard()
before = json.loads((OUT / 'DATA_BEFORE.json').read_text(encoding='utf-8'))
after = snapshot()
cleanup = json.loads((OUT / 'AUTHORITY_CLEANUP.json').read_text(encoding='utf-8'))
expected = {'organizations.MembershipRoleAssignment': {cleanup['role_revoked']}, 'organizations.MembershipScopeGrant': set(cleanup['scopes_revoked'])}
delta = []
for model, rows in after.items():
    old = before[model]
    added = sorted(set(rows)-set(old))
    removed = sorted(set(old)-set(rows))
    changed = sorted(k for k in rows.keys() & old.keys() if rows[k] != old[k])
    if added or removed or changed:
        valid = not removed and ((model in expected and not added and set(changed) == expected[model]) or (model == 'audit.AuditEvent' and not changed))
        delta.append({'model': model, 'added_ids': added, 'removed_ids': removed, 'changed_ids': changed, 'authorized': valid})
result = {'at': REAL_NOW(), 'models_compared': len(after), 'unchanged_models': len(after)-len(delta), 'deltas': delta, 'result': 'PASS' if all(r['authorized'] for r in delta) else 'PARTIAL_DELTA_ATTRIBUTION_REQUIRED', 'scope': 'This continuation versus its exact ENTRY snapshot only. No retroactive claim resolving REENTRY03 DATA_INTEGRITY unresolved attribution.', 'sessions_last_login': 'Excluded by retained snapshot contract', 'no_financial_domain_policy_catalogue_or_real_persona_write': all(r['authorized'] for r in delta)}
(OUT / 'DATA_INTEGRITY.json').write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'result':result['result'],'models':len(after),'deltas':[(r['model'],len(r['added_ids']),len(r['changed_ids'])) for r in delta]}))
