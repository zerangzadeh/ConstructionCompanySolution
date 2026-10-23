"""Revoke only the prior explicitly disposable accessibility test authority."""
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard, REAL_NOW
from django.db import transaction
from apps.accounts.models import User
from apps.organizations.access_services import revoke_membership_role, revoke_membership_scope
from apps.organizations.authorization import membership_has_permission, membership_has_scope, membership_permission_codes, effective_scope_grants
from apps.organizations.models import OrganizationMembership, BusinessPermissionCode

guard()
assert not (OUT / 'AUTHORITY_CLEANUP.json').exists()
prior = OUT.parent / 'CEP-078_REENTRY_03'
fixture = json.loads((prior / 'ACCESSIBILITY_FIXTURE.json').read_text(encoding='utf-8'))
remaining = json.loads((prior / 'REMAINING_FIXTURES.json').read_text(encoding='utf-8'))
target = OrganizationMembership.objects.select_related('organization', 'user').get(pk=fixture['membership'])
assert target.user.username == 'cep078.synthetic.accessibility'
actor = User.objects.get(username='account.demo-construction-01.owner')
approver = OrganizationMembership.objects.select_related('user').get(organization=target.organization, user__username='uiux.persona.tenant-admin')
actor_membership = OrganizationMembership.objects.get(organization=target.organization, user=actor)
for member in (actor_membership, approver):
    assert member.status == 'active' and member.user.is_active
    assert membership_has_scope(member)
    for permission in (BusinessPermissionCode.AUTHORIZATION_ROLES_REVOKE, BusinessPermissionCode.AUTHORIZATION_GRANTS_REVOKE):
        assert membership_has_permission(member, permission)
assert set(str(x) for x in target.role_assignments.filter(revoked_at__isnull=True).values_list('pk', flat=True)) == {fixture['assignment']}
grant_ids = {fixture['grant'], remaining['scope_grant']}
assert set(str(x) for x in effective_scope_grants(target).values_list('pk', flat=True)) == grant_ids
reason = 'CEP078_SYNTHETIC_DEVELOPMENT_ONLY; authorized post-verification cleanup of isolated accessibility test authority; retain identity, immutable source and audit history; no real/reference persona change'
with transaction.atomic():
    for grant_id in sorted(grant_ids):
        revoke_membership_scope(organization=target.organization, actor=actor, grant_id=grant_id, approver_membership_id=approver.pk, reason=reason)
    revoke_membership_role(organization=target.organization, actor=actor, assignment_id=fixture['assignment'], approver_membership_id=approver.pk, reason=reason)
    target.refresh_from_db()
    assert not membership_permission_codes(target)
    assert not effective_scope_grants(target).exists()
result = {'at': REAL_NOW(), 'target': target.user.username, 'membership': str(target.pk), 'actor': actor.username, 'independent_existing_test_approver': approver.user.username, 'role_revoked': fixture['assignment'], 'scopes_revoked': sorted(grant_ids), 'effective_permissions': [], 'effective_scopes': [], 'identity_and_immutable_fixtures_retained': True, 'operations_authority': 'Prior six-hour expiry retained; no extension or new grant', 'external_authority': 'Prior expiring non-member portal grant retained; no extension or new grant', 'mechanism': 'Existing atomic audited revoke_membership_scope and revoke_membership_role; no direct field writes, no role/catalogue changes', 'authority': 'Prior explicit fixture disposition; resumed CEP078 scope', 'result': 'PASS'}
(OUT / 'AUTHORITY_CLEANUP.json').write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('Synthetic accessibility authority cleanup PASS: one role and two scopes revoked canonically; identity and immutable history retained.')
