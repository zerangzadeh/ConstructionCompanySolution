"""Create a fresh invite through canonical services, with no membership or expiry rewrite."""
from datetime import timedelta
import json

from entry import OUT, guard, save
from apps.accounts.models import User
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode, OrganizationMembership
from apps.procurement.models import SupplierPortalGrant
from apps.procurement.portal_services import create_supplier_portal_invitation, accept_supplier_portal_invitation, get_supplier_portal_rfq_context
from django.db import transaction
from django.utils import timezone

guard()
assert not (OUT / "PORTAL_FIXTURE.json").exists()
entry = json.loads((OUT / "PORTAL_ENTRY.json").read_text(encoding="utf-8"))
old = SupplierPortalGrant.objects.select_related("portal_invitation", "principal__user", "rfq_invitation__rfq_version__rfq").get(pk=entry["old_grant"])
external = old.principal.user
assert not OrganizationMembership.objects.filter(user=external).exists()
rfq_invitation = old.rfq_invitation
organization = old.organization
actors = [User.objects.get(username="uiux.wavec.portal")]
actor = next(u for u in actors if has_business_permission(user=u, organization=organization, permission=BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE, project=rfq_invitation.rfq_version.rfq.project))
now = timezone.now()
expires_at = min(now + timedelta(hours=6), rfq_invitation.rfq_version.closing_at - timedelta(minutes=1))
assert expires_at > now + timedelta(minutes=30)
with transaction.atomic():
    invitation, token = create_supplier_portal_invitation(organization=organization, actor=actor, rfq_invitation=rfq_invitation, invited_email=external.email, expires_at=expires_at)
    grant = accept_supplier_portal_invitation(actor=external, token=token)
    del token
    context = get_supplier_portal_rfq_context(actor=external, grant=grant)
    assert context["rfq_number"] == rfq_invitation.rfq_version.rfq.rfq_number
    assert not OrganizationMembership.objects.filter(user=external).exists()
save("PORTAL_FIXTURE.json", {"created_at": now, "actor": actor.username, "external": external.username, "invitation": invitation.pk, "grant": grant.pk, "path": f"/procurement/portal/grants/{grant.pk}/", "expires_at": expires_at, "closing_at": rfq_invitation.rfq_version.closing_at, "rfq": rfq_invitation.rfq_version.rfq_id, "rfq_invitation": rfq_invitation.pk, "capability": grant.capability, "membership_count": 0, "services": ["create_supplier_portal_invitation", "accept_supplier_portal_invitation", "get_supplier_portal_rfq_context"], "token_persisted": False, "old_invitation_rewritten": False, "rfq_mutated": False})
print("Fresh canonical invitation/acceptance/context PASS; no tenant membership; no token persisted.")
