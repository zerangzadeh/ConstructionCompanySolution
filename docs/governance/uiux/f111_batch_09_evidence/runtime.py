"""BATCH-09 Development fixtures and real authenticated CSRF controls."""

import hashlib
import html
import json
import re
import runpy
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
support = runpy.run_path(str(OUT.parent / "f111_batch_05_evidence/runtime.py"), run_name="b09_support")
snapshot, row_hashes, digest = (support[n] for n in ("snapshot", "row_hashes", "digest"))
login = support["login"]
BASE = "http://localhost:8012"
login.__globals__["BASE"] = BASE

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.daily_reports.models import DailyReport
from apps.daily_reports.services import create_daily_report
from apps.equipment.forms import MaintenanceRecordForm
from apps.equipment.models import Equipment, MaintenanceRecord
from apps.equipment.services import create_maintenance_record
from apps.organizations.authorization import effective_role_assignments, effective_scope_grants, get_active_membership, has_business_permission
from apps.organizations.models import Organization
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite, WBSNode
from apps.projects.services import create_activity, create_project_phase, create_project_site
from apps.quality.forms import QualityIssueForm
from apps.quality.models import QualityIssue
from apps.quality.services import create_quality_issue
from apps.safety.forms import SafetyIncidentForm
from apps.safety.models import SafetyIncident
from apps.safety.services import create_safety_incident

ALIASES, CODES = support["ALIASES"], support["CODES"]
SURFACES = {
    "115": ("/equipment/maintenance/create/", MaintenanceRecordForm, "maintenance_records.create", "summary"),
    "126": ("/quality/create/", QualityIssueForm, "quality_issues.create", "description"),
    "127": ("/safety/create/", SafetyIncidentForm, "safety_incidents.create", "description"),
}


class Parsed(support["Parsed"]):
    def __init__(self, body):
        super().__init__(body)
        self.errors += [html.unescape(re.sub(r"<[^>]+>", " ", value)).strip() for value in re.findall(r'<ul[^>]*class="[^"]*errorlist[^"]*"[^>]*>(.*?)</ul>', body, re.S)]


def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def guard():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "construction_erp"
    assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
    assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = off")


def authority():
    org = Organization.objects.get(slug="demo-construction-01")
    result = []
    for alias in ALIASES:
        user = User.objects.get(username=alias)
        member = get_active_membership(user=user, organization=org)
        result.append({"actor": alias, "membership": member.pk, "staff": user.is_staff, "superuser": user.is_superuser,
            "roles": list(effective_role_assignments(member).order_by("pk").values()),
            "grants": list(effective_scope_grants(member).order_by("pk").values()),
            "permissions": {key: has_business_permission(user=user, organization=org, permission=row[2], allow_any_scope=True) for key, row in SURFACES.items()}})
    return result


def state():
    return {"models": snapshot(), "rows": row_hashes(), "authority": authority(), "database": connection.settings_dict["NAME"], "settings": settings.SETTINGS_MODULE, "pending_migrations": 0}


def sources():
    result = {}
    for key, code in CODES.items():
        project = Project.objects.get(code=code)
        site = ProjectSite.objects.get(project=project, code="SITE-01", is_active=True)
        phase = ProjectPhase.objects.get(site=site, code="PH-01")
        result[key] = {"project": project, "site": site, "phase": phase,
            "activity": Activity.objects.get(project=project, site=site, phase=phase, code="ACT-01", is_active=True, archived_at__isnull=True),
            "daily_report": DailyReport.objects.filter(project=project, site=site, phase=phase).order_by("pk").first(),
            "project_activity": Activity.objects.get(project=project, code="B06-A-" + key, is_active=True, archived_at__isnull=True)}
        assert result[key]["daily_report"] is not None
    project = result["A"]["project"]
    site = ProjectSite.objects.get(project=project, code="B09-SIBLING")
    phase = ProjectPhase.objects.get(site=site, code="B09-PH-SIBLING")
    result["A2"] = {"project": project, "site": site, "phase": phase,
        "activity": Activity.objects.get(project=project, code="B09-ACT-SIBLING"),
        "daily_report": DailyReport.objects.get(site=site, reporting_date=date(2026, 10, 1))}
    return result


def prepare():
    guard()
    before = state()
    save("PREPARATION_BEFORE.json", before)
    assert all(all(row["permissions"].values()) and not row["staff"] and not row["superuser"] for row in before["authority"])
    org = Organization.objects.get(slug="demo-construction-01")
    project = Project.objects.get(code=CODES["A"])
    actor = User.objects.get(username="account.demo-construction-01.owner")
    assert not ProjectSite.objects.filter(project=project, code="B09-SIBLING").exists()
    created = []
    with transaction.atomic():
        site = create_project_site(organization=org, actor=actor, project=project, code="B09-SIBLING", name="B09 synthetic ungranted sibling")
        phase = create_project_phase(organization=org, actor=actor, site=site, code="B09-PH-SIBLING", name="B09 synthetic sibling phase", status="active")
        wbs = WBSNode.objects.filter(project=project, is_active=True, archived_at__isnull=True).order_by("pk").first()
        activity = create_activity(organization=org, actor=actor, project=project, site=site, phase=phase, wbs_node=wbs, code="B09-ACT-SIBLING", name="B09 synthetic sibling activity")
        report = create_daily_report(organization=org, actor=actor, project=project, site=site, phase=phase, reporting_date=date(2026, 10, 1), work_performed="B09 synthetic Development sibling selector control")
        created = [{"model": obj._meta.label, "id": obj.pk, "service": service, "actor": actor.username} for obj, service in ((site, "create_project_site"), (phase, "create_project_phase"), (activity, "create_activity"), (report, "create_daily_report"))]
    assert digest(authority()) == digest(before["authority"])
    src = sources()
    save("FIXTURES.json", {"created": created, "reused": {k: {f: {"id": obj.pk, "label": str(obj)} for f, obj in row.items()} for k, row in src.items()}, "authority_mutations": [], "temporary_authority": "NONE", "reason": "Existing A had no ungranted sibling site/children; four minimum synthetic objects created through canonical services; existing project-only Activities reused"})
    save("RUNTIME_BEFORE.json", state())
    save("BROWSER_PAYLOAD.json", {"base": BASE, "paths": {k: v[0] for k, v in SURFACES.items()}, "sources": {k: {f: str(obj.pk) for f, obj in row.items()} for k, row in src.items()}, "payloads": {f: payload(f) for f in SURFACES}})
    print("Preparation PASS: four canonical sibling fixtures; existing actors and grants unchanged")


def fields(finding):
    return ("project", "site") if finding == "115" else ("project", "site", "phase", "activity", "daily_report")


def payload(finding, key="B"):
    data = {f: str(sources()[key][f].pk) for f in fields(finding)}
    if finding == "115":
        return data | {"equipment": str(Equipment.objects.get(code="EQ-01-EXC").pk), "record_number": "B09-REJECTED", "maintenance_type": "preventive", "summary": "B09 synthetic maintenance control", "scheduled_date": "1405/07/01", "provider": "", "cost": "", "description": "", "notes": ""}
    prefix, stamp = ("issue", "identified_at") if finding == "126" else ("incident", "occurred_at")
    return data | {prefix + "_number": "B09-REJECTED", prefix + "_type": "other", stamp: "2026-01-01T10:00", "severity": "minor" if finding == "126" else "low", "description": "B09 synthetic operational control"}


def small():
    return {model._meta.label: digest(list(model.objects.order_by("pk").values())) for model in (MaintenanceRecord, QualityIssue, SafetyIncident, AuditEvent)}


def http():
    guard()
    src = sources()
    org = Organization.objects.get(slug="demo-construction-01")
    records = []
    for alias, allowed, site_only in zip(ALIASES, ("AB", "ABCD", "A"), (False, False, True), strict=True):
        request = login(alias)
        member = get_active_membership(user=User.objects.get(username=alias), organization=org)
        for finding, (path, form_class, _, required) in SURFACES.items():
            form = form_class(organization=org, membership=member)
            expected = {f: [{"value": str(v), "label": str(l)} for v, l in form.fields[f].choices] for f in fields(finding)}
            for field in fields(finding):
                values = {o["value"] for o in expected[field]}
                for key in "ABCDX":
                    assert (str(src[key][field].pk) in values) == (key in allowed), (finding, alias, field, key)
                if field != "project":
                    assert (str(src["A2"][field].pk) in values) == (not site_only), (alias, field, "sibling")
                if field == "activity":
                    assert all((str(src[k]["project_activity"].pk) in values) == (k in allowed and not site_only) for k in "ABCDX")

            def observe(case, data=None, query=None, error_field=None):
                before = small()
                status, body, url = request(path + ("?" + urlencode(query) if query else ""), data)
                parsed = Parsed(body)
                actual = {f: parsed.fields[f] for f in fields(finding)}
                assert status == 200 and actual == expected, (finding, alias, case, status, actual)
                assert small() == before, (finding, alias, case, "mutation")
                clean = re.sub(r'<input[^>]*name="next"[^>]*>', "", body)
                clean = re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"', "", clean)
                leaks = []
                for field in fields(finding):
                    visible = {o["value"] for o in expected[field]}
                    permitted_labels = {str(obj) for row in src.values() for obj in row.values() if str(obj.pk) in visible}
                    for row in src.values():
                        obj = row[field]
                        if str(obj.pk) in visible:
                            continue
                        if str(obj.pk) in clean:
                            leaks.append(str(obj.pk))
                        label = str(obj)
                        if label not in permitted_labels and label in clean:
                            leaks.append(label)
                assert not leaks, (finding, alias, case, leaks)
                if data is not None:
                    assert parsed.errors, (finding, alias, case, "missing error")
                    bound = form_class(data, organization=org, membership=member)
                    assert not bound.is_valid(), (finding, alias, case, "unexpected valid form")
                    if error_field:
                        assert error_field in bound.errors, (finding, case, bound.errors)
                records.append({"finding": "UIUX-F-" + finding, "actor": alias, "case": case, "method": "POST" if data else "GET", "status": status, "options": actual, "errors": parsed.errors, "forbidden_metadata": leaks, "business_and_success_audit_unchanged": True, "real_authentication_csrf": True, "response_sha256": hashlib.sha256(body.encode()).hexdigest()})
                save("RUNTIME_HTTP.json", records)
                return parsed

            parsed = observe("GET")
            data = payload(finding, "A" if site_only else "B"); data.pop(required)
            parsed = observe("required-field redisplay", data | {"csrfmiddlewaretoken": parsed.token}, error_field=required)
            if allowed == "ABCD":
                continue
            for key in "CDX":
                parsed = observe("forced query " + key, query={f: src[key][f].pk for f in fields(finding)})
            for field in fields(finding):
                for key in ("BCDX" if site_only else "CDX"):
                    data = payload(finding, "A" if site_only else "B") | {field: str(src[key][field].pk)}
                    parsed = observe("forced " + key + " " + field, data | {"csrfmiddlewaretoken": parsed.token}, error_field=field)
                if site_only and field != "project":
                    data = payload(finding, "A") | {field: str(src["A2"][field].pk)}
                    parsed = observe("ungranted sibling " + field, data | {"csrfmiddlewaretoken": parsed.token}, error_field=field)
                if not site_only and field != "project":
                    data = payload(finding) | {field: str(src["A"][field].pk)}
                    parsed = observe("mixed authorized parent/child " + field, data | {"csrfmiddlewaretoken": parsed.token})
            if finding != "115" and site_only:
                data = payload(finding, "A") | {"activity": str(src["A"]["project_activity"].pk)}
                parsed = observe("site grant cannot enumerate project-only Activity", data | {"csrfmiddlewaretoken": parsed.token}, error_field="activity")
            if finding == "115":
                # Valid blank context reaches the unchanged organization-only service gate.
                before = small()
                data = payload(finding) | {"project": "", "site": "", "csrfmiddlewaretoken": parsed.token}
                status, body, _ = request(path, data)
                parsed = Parsed(body)
                assert status == 200 and parsed.errors and small() == before
                assert {f: parsed.fields[f] for f in fields(finding)} == expected
                records.append({"finding": "UIUX-F-115", "actor": alias, "case": "blank unassigned service denial", "method": "POST", "status": status, "errors": parsed.errors, "business_and_success_audit_unchanged": True, "real_authentication_csrf": True})
                save("RUNTIME_HTTP.json", records)
    save("HTTP_SUMMARY.json", {"all_pass": True, "observations": len(records), "by_finding": {"UIUX-F-" + k: sum(r["finding"] == "UIUX-F-" + k for r in records) for k in SURFACES}, "unauthorized_mutations": 0})
    print("HTTP PASS:", len(records), "observations; independent Project/Site/all-child matrices")


def direct():
    guard()
    src = sources(); org = Organization.objects.get(slug="demo-construction-01")
    before = small(); records = []
    for alias, keys in ((ALIASES[0], ("C", "D", "X")), (ALIASES[2], ("B", "C", "D", "X", "A2"))):
        actor = User.objects.get(username=alias)
        for finding, (_, form_class, _, _) in SURFACES.items():
            owner = get_active_membership(user=User.objects.get(username=ALIASES[1]), organization=org)
            form = form_class(payload(finding), organization=org, membership=owner)
            assert form.is_valid(), (finding, form.errors)
            for key in keys:
                kwargs = form.cleaned_data | {f: src[key][f] for f in fields(finding)}
                try:
                    {"115": create_maintenance_record, "126": create_quality_issue, "127": create_safety_incident}[finding](organization=org, actor=actor, **kwargs)
                except PermissionDenied:
                    pass
                else:
                    raise AssertionError((finding, alias, key, "not denied"))
                assert small() == before
                records.append({"finding": "UIUX-F-" + finding, "actor": alias, "source": key, "denied": True, "mutations": 0})
    save("DIRECT_SERVICE.json", records)
    print("Direct service denials PASS:", len(records))


def authorized_denials():
    """Observe existing organization-only workflow reader gates with valid forms."""
    guard()
    records = json.loads((OUT / "RUNTIME_HTTP.json").read_text(encoding="utf-8"))
    org = Organization.objects.get(slug="demo-construction-01")
    for alias, key in ((ALIASES[0], "B"), (ALIASES[2], "A")):
        request = login(alias)
        member = get_active_membership(user=User.objects.get(username=alias), organization=org)
        for finding in ("126", "127"):
            path, form_class, _, _ = SURFACES[finding]
            status, body, _ = request(path)
            parsed = Parsed(body)
            data = payload(finding, key)
            form = form_class(data, organization=org, membership=member)
            assert form.is_valid(), (finding, form.errors)
            expected = {f: parsed.fields[f] for f in fields(finding)}
            before = small()
            status, body, url = request(path, data | {"csrfmiddlewaretoken": parsed.token})
            parsed = Parsed(body)
            assert status == 200 and url == BASE + path and parsed.errors
            assert {f: parsed.fields[f] for f in fields(finding)} == expected
            assert small() == before
            records.append({"finding": "UIUX-F-" + finding, "actor": alias, "case": "authorized valid form; existing workflow organization-scope reader denial", "method": "POST", "status": status, "options": expected, "errors": parsed.errors, "forbidden_metadata": [], "business_and_success_audit_unchanged": True, "real_authentication_csrf": True, "form_valid_before_unchanged_service_denial": True, "response_sha256": hashlib.sha256(body.encode()).hexdigest()})
    save("RUNTIME_HTTP.json", records)
    save("HTTP_SUMMARY.json", {"all_pass": True, "observations": len(records), "by_finding": {"UIUX-F-" + k: sum(r["finding"] == "UIUX-F-" + k for r in records) for k in SURFACES}, "unauthorized_mutations": 0})
    print("Existing Quality/Safety workflow-gate runtime denials PASS: four valid forms; scoped redisplay and zero mutations")


def after():
    guard()
    before = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
    prep = json.loads((OUT / "PREPARATION_BEFORE.json").read_text(encoding="utf-8"))
    current = snapshot(); rows = row_hashes()
    deltas = [m for m, v in current.items() if v != before["models"][m]]
    assert set(deltas) <= {"sessions.Session"}, deltas
    changed = [(m, pk) for m, rs in prep["rows"].items() if m != "sessions.Session" for pk, h in rs.items() if rows[m].get(pk) != h]
    assert not changed, changed
    assert digest(authority()) == digest(before["authority"]) == digest(prep["authority"])
    additions = {m: len(set(rs) - set(prep["rows"][m])) for m, rs in rows.items() if set(rs) - set(prep["rows"][m])}
    assert set(additions) <= {"sessions.Session", "projects.ProjectSite", "projects.ProjectPhase", "projects.Activity", "daily_reports.DailyReport", "audit.AuditEvent"}, additions
    save("RUNTIME_AFTER.json", current)
    save("RUNTIME_INTEGRITY.json", {"tables": len(current), "runtime_deltas": deltas, "preexisting_business_rows_changed": changed, "unauthorized_mutations": 0, "runtime_success_audits": 0, "authority_fingerprint_before": digest(prep["authority"]), "authority_fingerprint_after": digest(authority()), "authority_unchanged": True, "temporary_authority": "NONE; no revocation necessary", "preparation_additions": additions, "last_login_excluded": True})
    print("Integrity PASS:", len(current), "tables; runtime sessions only; all business rows and authority preserved")


if __name__ == "__main__":
    {"prepare": prepare, "http": http, "direct": direct, "authorized_denials": authorized_denials, "after": after}[sys.argv[1]]()
