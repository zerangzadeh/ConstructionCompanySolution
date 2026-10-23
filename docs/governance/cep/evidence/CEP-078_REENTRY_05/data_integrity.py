"""Exact continuation-only retention: all prior rows unchanged, canonical new fixture only."""
import json
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard,snapshot,REAL_NOW
from apps.organizations.models import OrganizationMembership,AuthorizationMigrationIssue
from apps.audit.models import AuditEvent
guard()
before=json.loads((OUT/'DATA_BEFORE.json').read_text(encoding='utf-8'))
fixture=json.loads((OUT/'CASCADE_FIXTURE.json').read_text(encoding='utf-8'))
member=OrganizationMembership.objects.get(pk=fixture['membership'])
after=snapshot()
allowed={'accounts.User':{str(member.user_id)},'organizations.OrganizationMembership':{str(member.pk)},'organizations.MembershipRoleAssignment':{fixture['role_assignment']},'organizations.MembershipScopeGrant':{fixture['scope_grant']},'organizations.AuthorizationMigrationIssue':set(str(x) for x in AuthorizationMigrationIssue.objects.filter(membership=member).values_list('pk',flat=True))}
delta=[]
for label,rows in after.items():
    old=before[label]
    added=sorted(rows.keys()-old.keys());removed=sorted(old.keys()-rows.keys());changed=sorted(k for k in rows.keys()&old.keys() if rows[k]!=old[k])
    if not (added or removed or changed):continue
    permitted=not changed and not removed and (set(added)==allowed.get(label,set()) or label=='audit.AuditEvent')
    if label=='audit.AuditEvent':
        allowed_entities={str(member.pk),str(member.user_id),fixture['role_assignment'],fixture['scope_grant']}
        permitted=permitted and all(str(x) in allowed_entities for x in AuditEvent.objects.filter(pk__in=added).values_list('entity_id',flat=True))
    delta.append({'model':label,'added_ids':added,'changed_ids':changed,'removed_ids':removed,'authorized':permitted})
assert all(r['authorized'] for r in delta),delta
assert not member.role_assignments.filter(revoked_at__isnull=True).exists()
assert not member.scope_grants.filter(revoked_at__isnull=True).exists()
result={'at':REAL_NOW(),'result':'PASS','models_compared':len(after),'unchanged_model_aggregates':len(after)-len(delta),'all_preexisting_rows_unchanged':True,'new_only_isolated_fixture_and_audits':True,'deltas':delta,'cleanup':'New test role and scope canonically revoked; nonstaff/nonsuperuser identity and immutable audit retained','sessions_last_login':'Excluded by existing snapshot contract','prior_reentry03_attribution':'Historical PARTIAL remains; no retrospective inference from this exact continuation comparison','financial_business_policy_records_changed':False}
(OUT/'DATA_INTEGRITY.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':'PASS','models':len(after),'new_rows':[(r['model'],len(r['added_ids'])) for r in delta],'prior_rows_changed':0}))
