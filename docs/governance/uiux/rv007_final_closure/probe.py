"""RV-007 canonical real-clock feasibility probe; all business writes roll back."""
import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import Organization
from apps.procurement.models import RequestForQuotation, QuoteRevision
from apps.procurement.rfq_services import (
    create_rfq, add_rfq_line, submit_rfq_for_issue, issue_rfq, close_rfq,
)
from apps.procurement.quote_services import capture_quote_revision, submit_quote_revision
from apps.procurement.opening_services import request_quote_opening


def save(name, data):
    (OUT / name).write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def procurement_state():
    return {
        model._meta.label: digest(list(model._base_manager.order_by("pk").values()))
        for model in apps.get_app_config("procurement").get_models()
    }


assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql"
assert connection.settings_dict["NAME"] == "construction_erp"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
executor = MigrationExecutor(connection)
assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
org = Organization.objects.get(slug="demo-construction-01")
retained = RequestForQuotation.objects.select_related("project", "purchase_request").get(organization=org, rfq_number="WAVE-C-RFQ-A")
owner = User.objects.get(username="account.demo-construction-01.owner")
buyer = User.objects.get(username="uiux.wavec.buyer")
custodian = User.objects.get(username="uiux.wavec.custodian")
approver = User.objects.get(username="uiux.wavec.opening-approver")
before = procurement_state()
retained_before = digest(list(RequestForQuotation.objects.filter(pk=retained.pk).values()))
tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
paths = set(tracked)
for parent in ("apps", "core", "config", "templates", "tests"):
    paths.update(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
save("ENTRY.json", {
    "recorded_at": timezone.now(),
    "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "origin_main": subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip(),
    "upstream": subprocess.check_output(["git", "rev-parse", "@{u}"], text=True).strip(),
    "status": subprocess.check_output(["git", "status", "--short"], text=True),
    "diff_name_status": subprocess.check_output(["git", "diff", "--name-status"], text=True),
    "diff_stat": subprocess.check_output(["git", "diff", "--stat"], text=True),
    "index_sha256": hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(),
    "source_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT / p).is_file()},
    "database": {k: connection.settings_dict[k] for k in ("ENGINE", "HOST", "PORT", "NAME")},
    "touch_set": ["docs/governance/uiux/rv007_final_closure/", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml append", "UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md append"],
    "authorization": "Human RV-007 Final Closure request; current canonical services only; no Git/Production/downstream execution",
})
roles = {}
for actor, permissions in [(buyer, ["rfq_quotes.open", "rfq_quotes.view_confidential"]), (approver, ["rfq_quotes.approve_open", "rfq_quotes.manage_confidential_access"]), (custodian, ["rfqs.close_custody", "rfqs.custody_sealed_evidence"])]:
    roles[actor.username] = {p: has_business_permission(user=actor, organization=org, permission=p, project=retained.project) for p in permissions}
assert all(all(v.values()) for v in roles.values())
assert buyer.pk != approver.pk
now = timezone.now()
assert now < retained.closing_at < retained.earliest_opening_at
assert retained.earliest_opening_at - retained.closing_at == timedelta(hours=24)
events = []
number = "RV007-FINAL-SYNTHETIC-DEV"
assert not RequestForQuotation.objects.filter(organization=org, rfq_number=number).exists()
# This is a feasibility transaction, not retained successful runtime evidence.
# No service clock is mocked and no model/permission row is written directly.
with transaction.atomic():
    rfq = create_rfq(organization=org, actor=owner, project=retained.project,
        purchase_request=retained.purchase_request, rfq_number=number,
        title="RV-007 synthetic Development-only feasibility probe",
        closing_at=now - timedelta(hours=25), earliest_opening_at=now - timedelta(hours=1),
        terms="SYNTHETIC DEVELOPMENT ONLY; not supplier/business evidence")
    item = retained.purchase_request.items.order_by("pk").first()
    add_rfq_line(organization=org, actor=owner, rfq=rfq, purchase_request_item=item, quantity=item.quantity)
    submit_rfq_for_issue(organization=org, actor=owner, rfq=rfq)
    version = issue_rfq(organization=org, actor=owner, rfq=rfq,
        suppliers=[retained.versions.get(version_number=retained.current_version_number).invitations.first().supplier],
        idempotency_key=number + "-issue")
    source = b"RV-007 synthetic Development-only feasibility source; no actual supplier content.\n"
    revision = capture_quote_revision(organization=org, actor=buyer, invitation=version.invitations.get(),
        integrity_fingerprint=hashlib.sha256(source).hexdigest(), source_channel="manual_capture",
    source_reference="RV007-FEASIBILITY-SYNTHETIC-SOURCE",
        supplier_submitted_at=now - timedelta(hours=26), idempotency_key=number + "-capture")
    assert revision.is_late and revision.received_at > version.closing_at
    try:
        submit_quote_revision(organization=org, actor=buyer, revision=revision, idempotency_key=number + "-submit")
    except ValueError as exc:
        assert "پس از مهلت" in str(exc)
        events.append({"case": "new_past_close_rfq_quote_submission", "outcome": "DENIED", "exception": type(exc).__name__, "message": str(exc), "is_late": revision.is_late,
            "closing_at": version.closing_at, "received_at": revision.received_at,
            "claimed_supplier_submitted_at_does_not_override_server_receipt": True})
    else:
        raise AssertionError("A late quote unexpectedly submitted")
    manifest = close_rfq(organization=org, actor=custodian, rfq=rfq, idempotency_key=number + "-close")
    entry = manifest.entries.get()
    assert entry.effective_revision_id is None and entry.disposition == "no_effective_submission"
    try:
        request_quote_opening(organization=org, actor=buyer, quote_revision=revision, reason=number, idempotency_key=number + "-open")
    except PermissionDenied as exc:
        events.append({"case": "opening_without_effective_on_time_submission", "outcome": "DENIED", "exception": type(exc).__name__, "manifest_disposition": entry.disposition})
    else:
        raise AssertionError("Non-effective revision unexpectedly opened")
    transaction.set_rollback(True)
assert not RequestForQuotation.objects.filter(organization=org, rfq_number=number).exists()
with transaction.atomic():
    try:
        close_rfq(organization=org, actor=custodian, rfq=retained, idempotency_key="rv007-retained-too-early")
    except ValueError as exc:
        assert "پیش از مهلت" in str(exc)
        events.append({"case": "retained_rfq_early_close", "outcome": "DENIED", "message": str(exc)})
    else:
        raise AssertionError("Retained RFQ unexpectedly closed")
    original_revision = QuoteRevision.objects.filter(envelope__rfq=retained).order_by("pk").first()
    assert original_revision
    try:
        request_quote_opening(organization=org, actor=buyer, quote_revision=original_revision, reason="RV-007 early denial verification", idempotency_key="rv007-retained-too-early")
    except PermissionDenied as exc:
        events.append({"case": "retained_rfq_early_opening", "outcome": "DENIED", "message": str(exc), "first_failing_gate": "No closed/effective-submitted manifest; isolated 24-hour gate not reached"})
    else:
        raise AssertionError("Retained RFQ unexpectedly opened")
    transaction.set_rollback(True)
assert before == procurement_state()
assert retained_before == digest(list(RequestForQuotation.objects.filter(pk=retained.pk).values()))
save("FEASIBILITY.json", {
    "recorded_at": timezone.now(), "status": "BLOCKED_CANONICAL_TEMPORAL_PREREQUISITE",
    "roles_pre_authorized": roles, "independent_actors": True,
    "probe": events, "synthetic_probe_rolled_back": True, "synthetic_rfq_retained": False,
    "production": "UNTOUCHED", "git_writes": "NOT_EXECUTED", "clock_override": False,
    "direct_database_fabrication": False, "authorization_bypass": False,
    "procurement_all_model_fingerprints_unchanged": True, "retained_rfq_unchanged": True,
    "retained_rfq": {"id": str(retained.pk), "status": retained.status, "closing_at": retained.closing_at, "earliest_opening_at": retained.earliest_opening_at, "gap_hours": 24},
    "source_scan_custody": "NOT_REACHED; valid custody requires effective submitted revision; no fake clean verdict or file",
})
print("Canonical real-clock probe: late submission DENIED; no effective manifest entry; opening DENIED; entire synthetic transaction ROLLED BACK. Retained RFQ and all Procurement models UNCHANGED.")
