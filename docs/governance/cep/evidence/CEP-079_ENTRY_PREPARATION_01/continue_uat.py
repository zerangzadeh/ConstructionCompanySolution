"""Bounded CEP079 continuation helpers; no scenario runs at import time."""
from datetime import timedelta
import hashlib
import json

import uat_execution_support as u
from django.db import transaction
from django.utils import timezone


def access(alias, codes, case, scope="project"):
    """Add exact existing catalogue permissions with actual independent approval."""
    from apps.organizations.models import OrganizationMembership, OrganizationRole
    from apps.organizations.authorization import membership_permission_codes, effective_scope_grants
    from apps.organizations.access_services import (
        create_organization_role, assign_membership_role, grant_membership_scope,
    )
    with transaction.atomic():
        target = OrganizationMembership.objects.get(organization=u.ORG, user__username=alias, status="active")
        previous = membership_permission_codes(target)
        missing = set(codes) - previous
        reason = f"Direct Human CEP079 Development continuation case{case:03d}; exact catalogue access; preserve expired history and independent approval."
        changes = {"alias": alias, "before_permissions": sorted(previous), "added_permissions": sorted(missing)}
        if missing:
            code = "cep079_cont_" + hashlib.sha256((alias + ";" + ";".join(sorted(missing))).encode()).hexdigest()[:16]
            role = OrganizationRole.objects.filter(organization=u.ORG, code=code).first()
            if role is None:
                role = create_organization_role(actor=u.actor("admin"), organization=u.ORG, code=code,
                    name=f"دسترسی محدود آزمون پذیرش {case}", description="CEP079 exact Development scenario prerequisite", permissions=missing, reason=reason)
            owner = OrganizationMembership.objects.get(organization=u.ORG, user__username="account.demo-construction-01.owner", status="active")
            approver = OrganizationMembership.objects.get(organization=u.ORG, user__username="uiux.persona.tenant-admin", status="active")
            assert target.pk not in (owner.pk, approver.pk)
            assignment = assign_membership_role(organization=u.ORG, actor=owner.user, membership_id=target.pk,
                role=role, approver_membership_id=approver.pk, reason=reason, ends_at=timezone.now()+timedelta(hours=12))
            changes.update(role=role.code, assignment=str(assignment.pk), ends_at=assignment.ends_at.isoformat())
        scopes = effective_scope_grants(target)
        has_scope = scopes.filter(scope_type="organization").exists() or (scope=="project" and scopes.filter(project=u.PROJECT, scope_type="project").exists())
        if not has_scope:
            owner = OrganizationMembership.objects.get(organization=u.ORG, user__username="account.demo-construction-01.owner", status="active")
            approver = OrganizationMembership.objects.get(organization=u.ORG, user__username="uiux.persona.tenant-admin", status="active")
            grant = grant_membership_scope(organization=u.ORG, actor=owner.user, membership_id=target.pk, scope_type=scope,
                project=u.PROJECT if scope=="project" else None, approver_membership_id=approver.pk,
                reason=reason, ends_at=timezone.now()+timedelta(hours=12))
            changes.update(scope_grant=str(grant.pk), scope=scope)
        target.refresh_from_db()
        assert set(codes).issubset(membership_permission_codes(target))
        changes["native_dual_control"] = True
    path = u.OUT / f"UAT_CASE_{case:03d}_RUNTIME.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("authorization_corrections", []).append({"at": timezone.now().isoformat(), **changes})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return changes


def post(client, url, data, expected=200):
    """Native authenticated CSRF form POST; retain redirects and visible errors."""
    import re
    token = client.cookies["csrftoken"].value
    response = client.post(url, {"csrfmiddlewaretoken": token, **data}, follow=True)
    assert response.status_code == expected, (url, response.status_code)
    body = response.content.decode("utf-8")
    return response, {"url": url, "status": response.status_code,
        "redirects": response.redirect_chain, "sha256": hashlib.sha256(response.content).hexdigest(),
        "messages": re.findall(r'<[^>]+class="[^\"]*(?:alert|message)[^\"]*"[^>]*>(.*?)</', body, re.S)}
