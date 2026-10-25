"""CEP079 execution helpers: real native requests/services, retained measured results."""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.db import connection
from django.test import Client
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.projects.models import Project

OUT = Path(__file__).parent
assert settings.DEBUG and settings.SETTINGS_MODULE == "config.settings.development"
assert connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1")
ORG = Organization.objects.get(slug="demo-construction-01", status="active")
PROJECT = Project.objects.get(organization=ORG, pk="58f517da-2139-45ac-8b7b-4f3d3a3d26e8")


def actor(alias):
    return User.objects.get(username=alias, is_active=True)


def native_client(alias):
    # Existing DPAPI secret is passed only to native LoginView; never persisted.
    secret = subprocess.check_output([
        "powershell.exe", "-NoProfile", "-Command",
        "$c = Import-Clixml -LiteralPath (Join-Path $env:LOCALAPPDATA "
        + "'BONIRA/UIUXRuntimeAudit/credentials/" + alias + ".clixml'); "
        + "[Console]::Write($c.GetNetworkCredential().Password)",
    ], text=True)
    client = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8000")
    form = client.get("/accounts/login/")
    assert form.status_code == 200
    response = client.post("/accounts/login/", {
        "username": alias, "password": secret,
        "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
    }, follow=True)
    secret = None
    assert response.status_code == 200 and response.wsgi_request.user.pk == actor(alias).pk
    return client


def measured_get(client, url, expected=200):
    response = client.get(url)
    assert response.status_code == expected, (url, response.status_code)
    body = response.content if not response.streaming else b"".join(response.streaming_content)
    return response, {"url": url, "status": response.status_code,
        "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}


def ensure_source_permissions(alias, codes, case):
    """Human-authorized minimum catalogue permission delta, using owning services."""
    from django.db import transaction
    from apps.organizations.models import OrganizationMembership, OrganizationRole, BusinessPermissionCode as P
    from apps.organizations.authorization import membership_permission_codes, membership_has_scope, effective_scope_grants
    from apps.organizations.access_services import create_organization_role, assign_membership_role
    from apps.organizations.platform_grants import platform_initial_grant
    target = OrganizationMembership.objects.get(organization=ORG, user__username=alias, status="active")
    before = membership_permission_codes(target)
    missing = set(codes) - before
    if not missing:
        return {"added_permissions": [], "role_or_scope_changes": False}
    reason = f"Direct Human CEP079 Development continuation; case{case:03d} exact source-access prerequisite; no unrelated authority."
    role_code = "cep079_uat_" + hashlib.sha256(";".join(sorted(missing)).encode()).hexdigest()[:12]
    with transaction.atomic():
        scopes = list(effective_scope_grants(target).values_list("pk", flat=True))
        role = OrganizationRole.objects.filter(organization=ORG, code=role_code).first()
        if role is None:
            role = create_organization_role(actor=actor("admin"), organization=ORG,
                code=role_code, name=f"دسترسی محدود آزمون پذیرش {case}",
                description="CEP079 exact existing catalogue prerequisite only", permissions=missing, reason=reason)
        assert set(role.permissions.values_list("code", flat=True)) == missing
        members = list(OrganizationMembership.objects.filter(organization=ORG, status="active", user__is_active=True).exclude(pk=target.pk).select_related("user"))
        delegators = [m for m in members if P.AUTHORIZATION_ROLES_ASSIGN in membership_permission_codes(m)
            and membership_has_scope(m) and missing.issubset(membership_permission_codes(m))]
        pair = next(((a,b) for a in delegators for b in members if a.pk != b.pk
            and P.AUTHORIZATION_ROLES_ASSIGN in membership_permission_codes(b) and membership_has_scope(b)), None)
        if pair:
            grant = assign_membership_role(organization=ORG, actor=pair[0].user,
                membership_id=target.pk, role=role, approver_membership_id=pair[1].pk, reason=reason)
            route = "ordinary_dual_control"
        else:
            existing = list(effective_scope_grants(target))
            organization_scope = any(x.scope_type == "organization" for x in existing)
            assert organization_scope or all(x.project_id == PROJECT.pk for x in existing)
            grant, _ = platform_initial_grant(organization=ORG, actor=actor("admin"), membership_id=target.pk,
                role=role, scope_type="organization" if organization_scope else "project",
                project=None if organization_scope else PROJECT, reason=reason)
            route = "native_platform_initial_grant_no_lawful_pair"
        target.refresh_from_db()
        after = membership_permission_codes(target)
        assert after-before == missing and not before-after
        assert scopes == list(effective_scope_grants(target).values_list("pk", flat=True))
    return {"role": role.code, "assignment": str(grant.pk), "route": route,
        "added_permissions": sorted(missing), "existing_scope_unchanged": True}


def record(number, trace, result="PASS"):
    path = OUT / f"UAT_CASE_{number:03d}_RUNTIME.json"
    retained = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    trace = {"at": timezone.now().isoformat(), **trace, "result": result}
    retained.setdefault("continuation_execution", []).append(trace)
    retained["scenario_result"] = result
    path.write_text(json.dumps(retained, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    sync(number, result)


def sync(number, result):
    path = OUT / "44_CASE_READINESS_MATRIX.json"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    row = matrix["rows"][number - 1]
    row["uat_execution_result"] = result
    row["uat_execution"] = {**row.get("uat_execution", {}),
        "evidence": (OUT / f"UAT_CASE_{number:03d}_RUNTIME.json").relative_to(ROOT).as_posix(),
        "execution_extent": "ACTUAL_NATIVE_WORKFLOW", "result": result}
    counts = {x: sum(r["uat_execution_result"] == x for r in matrix["rows"])
              for x in ("PASS", "FAIL", "BLOCKED", "NOT_EXECUTED")}
    summary = matrix["uat_execution_summary"]
    summary.update(updated_at=timezone.now().isoformat(), attempted=44-counts["NOT_EXECUTED"],
        fully_executed=counts["PASS"]+counts["FAIL"], terminal_results=44-counts["NOT_EXECUTED"],
        **{"pass": counts["PASS"], "fail": counts["FAIL"], "blocked": counts["BLOCKED"], "not_executed": counts["NOT_EXECUTED"]},
        satisfied_mappings=sum(len(r["upstream_imb_ids"]) for r in matrix["rows"] if r["uat_execution_result"]=="PASS"),
        blocked_mappings=sum(len(r["upstream_imb_ids"]) for r in matrix["rows"] if r["uat_execution_result"]=="BLOCKED"),
        unexecuted_mappings=sum(len(r["upstream_imb_ids"]) for r in matrix["rows"] if r["uat_execution_result"]=="NOT_EXECUTED"),
        blocker=None if not counts["BLOCKED"] else summary.get("blocker"),
        order="Canonical001..044; direct Human authorized continuation from005")
    path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    path = OUT / "44_CASE_READINESS_MATRIX.csv"
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f); fields = reader.fieldnames; rows = list(reader)
    for csvrow, current in zip(rows, matrix["rows"]):
        csvrow["uat_execution_result"] = current["uat_execution_result"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(f"Case{number:03d}: {result}")
