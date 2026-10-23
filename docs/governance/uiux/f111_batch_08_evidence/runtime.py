"""BATCH-08 real authenticated CSRF HTTP controls; no business/authority writes."""

import hashlib
import html
import json
import re
import runpy
import sys
from pathlib import Path
from urllib.parse import urlencode

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
support = runpy.run_path(str(OUT.parent / "f111_batch_05_evidence/runtime.py"), run_name="b08_support")
snapshot, row_hashes, digest = (support[n] for n in ("snapshot", "row_hashes", "digest"))


class Parsed(support["Parsed"]):
    def __init__(self, body):
        super().__init__(body)
        self.errors += [html.unescape(re.sub(r"<[^>]+>", " ", value)).strip() for value in re.findall(r'<ul[^>]*class="[^"]*errorlist[^"]*"[^>]*>(.*?)</ul>', body, re.S)]
login = support["login"]
BASE = "http://localhost:8011"
login.__globals__["BASE"] = BASE

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.contracts.services import create_contract
from apps.inventory.forms import WarehouseForm
from apps.inventory.models import Warehouse
from apps.inventory.services import create_warehouse
from apps.organizations.authorization import effective_role_assignments, effective_scope_grants, get_active_membership, has_business_permission
from apps.organizations.models import Organization
from apps.procurement.forms import PurchaseRequestForm
from apps.procurement.models import PurchaseRequest
from apps.procurement.services import create_purchase_request
from apps.projects.models import Project
from apps.workforce.forms import TrainingRequirementForm
from apps.workforce.models import TrainingRequirement
from apps.workforce.services import create_training_requirement

ALIASES, CODES = support["ALIASES"], support["CODES"]
SURFACES = {
    "113": ("/procurement/requests/create/", PurchaseRequestForm, "purchase_requests.create", "title"),
    "116": ("/contracts/create/", ContractForm, "contracts.create", "title"),
    "117": ("/inventory/create/", WarehouseForm, "warehouses.create", "name"),
    "125": ("/workforce/foundation/training-requirements/create/", TrainingRequirementForm, "workforce_qualifications.manage", "name"),
}


def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def guard():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "construction_erp"
    assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
    assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
    with connection.cursor() as c:
        c.execute("SET default_transaction_read_only = off")


def sources():
    return {key: Project.objects.get(code=code) for key, code in CODES.items()}


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


def payload(finding, key="B"):
    fields = {
        "113": {"request_number": "B08-REJECTED", "title": "B08 synthetic rejected request", "required_by": "", "notes": ""},
        "116": {"contract_number": "B08-REJECTED", "title": "B08 synthetic rejected contract", "counterparty_name": "B08 synthetic counterparty", "status": "draft", "contract_value": "10.00", "direction": "", "contract_type": "", "party": "", "signed_at": "", "start_date": "", "end_date": "", "notes": ""},
        "117": {"code": "B08-REJECTED", "name": "B08 synthetic rejected warehouse", "location": ""},
        "125": {"code": "B08-REJECTED", "name": "B08 synthetic rejected training requirement", "competency": "", "position": "", "description": ""},
    }
    return fields[finding] | {"project": str(sources()[key].pk) if key else ""}


def small():
    return {model._meta.label: digest(list(model.objects.order_by("pk").values())) for model in (PurchaseRequest, Contract, Warehouse, TrainingRequirement, AuditEvent)}


def prepare():
    guard()
    state = {"models": snapshot(), "rows": row_hashes(), "authority": authority(), "database": connection.settings_dict["NAME"], "settings": settings.SETTINGS_MODULE, "pending_migrations": 0}
    assert all(all(row["permissions"].values()) and not row["staff"] and not row["superuser"] for row in state["authority"])
    assert TrainingRequirement.objects.count() == 0
    save("RUNTIME_BEFORE.json", state)
    save("FIXTURES.json", {"reused_projects": {k: {"id": p.pk, "code": p.code, "name": p.name, "tenant": p.organization.slug, "non_deleted": p.deleted_at is None} for k, p in sources().items()}, "actors": ALIASES, "created": [], "authority_mutations": [], "temporary_authority": "NONE", "training_requirement_created": False, "SP031": "UNCHANGED"})
    save("BROWSER_PAYLOAD.json", {"base": BASE, "projects": {k: str(p.pk) for k, p in sources().items()}, "paths": {k: v[0] for k, v in SURFACES.items()}, "payloads": {k: payload(k) for k in SURFACES}})
    print("Preparation PASS: existing actors/Projects; zero persistent fixture or authority mutations")


def http():
    guard()
    src = sources()
    org = Organization.objects.get(slug="demo-construction-01")
    records = []
    for alias, allowed in zip(ALIASES, ("AB", "ABCD", ""), strict=True):
        request = login(alias)
        member = get_active_membership(user=User.objects.get(username=alias), organization=org)
        for finding, (path, form_class, _, required) in SURFACES.items():
            form = form_class(organization=org, membership=member)
            expected = [{"value": str(v), "label": str(l)} for v, l in form.fields["project"].choices]
            assert {o["value"] for o in expected if o["value"]} == {str(src[k].pk) for k in allowed}

            def observe(case, data=None, query=None):
                before = small()
                status, body, url = request(path + ("?" + urlencode(query) if query else ""), data)
                parsed = Parsed(body)
                assert status == 200 and parsed.fields["project"] == expected, (finding, alias, case, status, parsed.fields)
                assert small() == before, (finding, alias, case, "mutation")
                clean = re.sub(r'<input[^>]*name="next"[^>]*>', "", body)
                clean = re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"', "", clean)
                leaks = []
                allowed_names = {src[k].name for k in allowed}
                if not allowed:
                    allowed_names.add(src["A"].name)
                for key, project in src.items():
                    if key in allowed:
                        continue
                    if not (not allowed and key == "A"):
                        if str(project.pk) in clean:
                            leaks.append(str(project.pk))
                        if project.name not in allowed_names and project.name in clean:
                            leaks.append(project.name)
                assert not leaks, (finding, alias, case, leaks)
                if data is not None:
                    assert parsed.errors, (finding, alias, case, "missing validation error")
                records.append({"finding": "UIUX-F-" + finding, "actor": alias, "case": case, "method": "POST" if data else "GET", "status": status, "options": parsed.fields["project"], "errors": parsed.errors, "forbidden_metadata": leaks, "business_and_success_audit_unchanged": True, "real_authentication_csrf": True, "response_sha256": hashlib.sha256(body.encode()).hexdigest()})
                save("RUNTIME_HTTP.json", records)
                return parsed

            parsed = observe("GET")
            # Organization positive redisplay remains scoped without persistent creation.
            data = payload(finding)
            data.pop(required)
            parsed = observe("required-field redisplay", data | {"csrfmiddlewaretoken": parsed.token})
            if allowed == "ABCD":
                continue
            for key in "CDX":
                parsed = observe("forced query " + key, query={"project": src[key].pk})
            for key in ("CDX" if allowed else "ABCDX"):
                parsed = observe("forced Project " + key, payload(finding, key) | {"csrfmiddlewaretoken": parsed.token})
            if finding == "125":
                parsed = observe("authorized B stricter service denial" if allowed else "blank stricter service denial", payload(finding, "B" if allowed else "") | {"csrfmiddlewaretoken": parsed.token})
            if finding == "117":
                parsed = observe("blank central warehouse service denial", payload(finding, "") | {"csrfmiddlewaretoken": parsed.token})
            if finding in {"113", "116"}:
                parsed = observe("missing required Project", payload(finding, "") | {"csrfmiddlewaretoken": parsed.token})
    save("HTTP_SUMMARY.json", {"all_pass": True, "observations": len(records), "by_finding": {"UIUX-F-" + k: sum(r["finding"] == "UIUX-F-" + k for r in records) for k in SURFACES}, "unauthorized_mutations": 0})
    print("HTTP PASS:", len(records), "independent observations across all four routes")


def direct():
    guard()
    src = sources()
    org = Organization.objects.get(slug="demo-construction-01")
    before = small()
    records = []
    for alias, keys in ((ALIASES[0], "CDX"), (ALIASES[2], "ABCDX")):
        actor = User.objects.get(username=alias)
        for finding in SURFACES:
            for key in keys:
                data = payload(finding, key)
                data.pop("project")
                if finding == "113":
                    data.pop("required_by")
                if finding == "116":
                    from decimal import Decimal
                    data = {k: v for k, v in data.items() if v != ""}
                    data["contract_value"] = Decimal(data["contract_value"])
                if finding == "125":
                    data.pop("competency")
                    data.pop("position")
                service = {"113": create_purchase_request, "116": create_contract, "117": create_warehouse, "125": create_training_requirement}[finding]
                try:
                    service(organization=org, actor=actor, project=src[key], **data)
                except PermissionDenied:
                    pass
                else:
                    raise AssertionError((finding, alias, key, "not denied"))
                assert small() == before
                records.append({"finding": "UIUX-F-" + finding, "actor": alias, "project": key, "denied": True, "mutations": 0})
    save("DIRECT_SERVICE.json", records)
    print("Direct service denials PASS:", len(records))


def after():
    guard()
    before = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
    current = snapshot()
    rows = row_hashes()
    deltas = [m for m, v in current.items() if v != before["models"][m]]
    assert set(deltas) <= {"sessions.Session"}, deltas
    changed = [(m, pk) for m, rs in before["rows"].items() if m != "sessions.Session" for pk, h in rs.items() if rows[m].get(pk) != h]
    assert not changed, changed
    assert digest(authority()) == digest(before["authority"])
    assert TrainingRequirement.objects.count() == 0
    save("RUNTIME_AFTER.json", current)
    save("RUNTIME_INTEGRITY.json", {"tables": len(current), "runtime_deltas": deltas, "preexisting_business_rows_changed": changed, "unauthorized_mutations": 0, "runtime_success_audits": 0, "authority_fingerprint_before": digest(before["authority"]), "authority_fingerprint_after": digest(authority()), "authority_unchanged": True, "temporary_authority": "NONE; no revocation necessary", "persistent_preparation_mutations": [], "training_requirements": 0, "last_login_excluded": True})
    print("Integrity PASS:", len(current), "tables; only sessions changed; authority and business rows preserved")


if __name__ == "__main__":
    {"prepare": prepare, "http": http, "direct": direct, "after": after}[sys.argv[1]]()
