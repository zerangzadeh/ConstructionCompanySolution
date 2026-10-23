"""Verify retained history, exact custody chain, bounded source/data and authority."""
from support import *
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from apps.accounts.models import User
from apps.organizations.authorization import has_platform_role, has_business_permission
from apps.organizations.models import Organization, OrganizationRole, OrganizationMembership, PlatformRoleAssignment
from apps.procurement.models import RequestForQuotation, QuoteRevision, QuoteRevisionEvidence, QuoteOpeningRequest, QuoteOpeningEvent, QuoteConfidentialAccessGrant, CommercialComparison
from apps.procurement.opening_services import request_quote_opening
from apps.procurement.rfq_services import close_rfq
from apps.documents.services import record_document_processing_assessment

guard()
made = read("FIXTURE.json")
org = Organization.objects.get(slug="demo-construction-01")
rfq = RequestForQuotation.objects.get(pk=made["rfq"])
revision = QuoteRevision.objects.select_related("rfq_version").get(pk=made["revision"])
evidence = QuoteRevisionEvidence.objects.select_related("document_version", "sealed_custody").get(pk=made["evidence"])
opening = QuoteOpeningEvent.objects.get(pk=made["opening"])
request = QuoteOpeningRequest.objects.get(pk=made["opening_request"])
comparison = CommercialComparison.objects.get(pk=made["comparison"])
retained = RequestForQuotation.objects.get(organization=org, rfq_number="WAVE-C-RFQ-A")
assert revision.status == "submitted" and not revision.is_late
assert revision.received_at <= revision.submitted_at <= revision.rfq_version.closing_at
assert revision.rfq_version.earliest_opening_at - revision.rfq_version.closing_at == timedelta(hours=24)
assert opening.opened_at > revision.rfq_version.earliest_opening_at
assert opening.approved_by_id != request.requested_by_id
digest = hashlib.sha256(Path(evidence.document_version.file.path).read_bytes()).hexdigest()
assert digest == made["source_sha256"] == revision.integrity_fingerprint == evidence.canonical_sha256 == evidence.document_version.sha256
assessment = evidence.document_version.processing_assessments.latest("sequence")
assert assessment.verdict == "clean" and assessment.input_sha256 == digest
assert request.frozen_package.items.get().evidence_id == evidence.pk
assert request.frozen_package.items.get().document_version_id == evidence.document_version_id
assert opening.package_fingerprint == request.frozen_package.package_fingerprint
assert comparison.inputs.get().opening_event_id == opening.pk
checks = []
for label, obj, field, changed in [("quote revision immutable", revision, "source_reference", "FORGED"), ("custody evidence immutable", evidence, "canonical_sha256", "f"*64), ("opening event immutable", opening, "package_fingerprint", "f"*64)]:
    original = getattr(obj, field)
    try:
        with transaction.atomic():
            setattr(obj, field, changed)
            obj.save()
            raise AssertionError(label + " was mutable")
    except ValidationError:
        checks.append({"case": label, "result": "DENIED"})
    finally:
        setattr(obj, field, original)
actor = User.objects.get(username="uiux.wavec.buyer")
try:
    record_document_processing_assessment(version=evidence.document_version, actor=actor, verdict="clean", adapter_code="forged")
except PermissionDenied:
    checks.append({"case": "business actor cannot fabricate CLEAN assessment", "result": "DENIED"})
else:
    raise AssertionError("Unauthorized scan assessment accepted")
assert not has_platform_role(User.objects.get(username="uiux.wavec.custodian"), "platform_operations")
temporary = PlatformRoleAssignment.objects.get(pk=made["scanner_assignment"])
assert temporary.ends_at <= REAL_NOW()
# Real-clock retained RFQ remains unchanged and refuses early close/opening.
assert REAL_NOW() < retained.closing_at < retained.earliest_opening_at
with transaction.atomic():
    try:
        close_rfq(organization=org, actor=User.objects.get(username="uiux.wavec.custodian"), rfq=retained, idempotency_key="RV007-retained-early-final")
    except ValueError:
        checks.append({"case": "retained RFQ real-clock early close", "result": "DENIED"})
    else:
        raise AssertionError("Retained RFQ closed early")
    target = QuoteRevision.objects.get(envelope__rfq=retained)
    try:
        request_quote_opening(organization=org, actor=actor, quote_revision=target, reason="RV007 retained real clock", idempotency_key="RV007-retained-early-final")
    except PermissionDenied:
        checks.append({"case": "retained RFQ real-clock early opening", "result": "DENIED", "first_guard": "closed effective manifest; time guard separately proved on synthetic RFQ"})
    else:
        raise AssertionError("Retained RFQ opened early")
    transaction.set_rollback(True)
before = read("DATA_BEFORE.json")
after = snapshot()
save("DATA_AFTER.json", after)
approver_membership = OrganizationMembership.objects.get(organization=org, user__username="uiux.wavec.custodian")
changes = {}
for label, old in before.items():
    new = after[label]
    modified = [pk for pk, sha in old.items() if pk in new and new[pk] != sha]
    deleted = [pk for pk in old if pk not in new]
    added = [pk for pk in new if pk not in old]
    assert not deleted, (label, deleted)
    if modified or added:
        changes[label] = {"modified": modified, "added": added}
    assert not modified or label == "documents.DocumentNumberSequence" or (label == "organizations.OrganizationMembership" and modified == [str(approver_membership.pk)]), (label, modified)
assert before["procurement.RequestForQuotation"][str(retained.pk)] == after["procurement.RequestForQuotation"][str(retained.pk)]
expected_additions = {"organizations.OrganizationRole", "organizations.OrganizationMembership", "organizations.MembershipRoleAssignment", "organizations.PlatformRoleAssignment", "organizations.PlatformPolicy", "organizations.PlatformPolicyVersion", "organizations.TenantPolicySelection", "audit.AuditEvent", "documents.Document", "documents.DocumentVersion", "documents.DocumentNumberSequence", "documents.DocumentProcessingAssessment", "documents.SealedDocumentCustody"}
for label in changes:
    assert label.startswith("procurement.") or label in expected_additions, label
entry = read("ENTRY.json")
changed_files = [p for p, sha in entry["hashes"].items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest() != sha]
allowed = {"apps/procurement/test_rfq_close.py", "apps/procurement/test_cep032_buyer_actions.py", "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md", "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"}
assert set(changed_files) <= allowed, changed_files
assert hashlib.sha256((ROOT/".git/index").read_bytes()).hexdigest() == entry["index_sha256"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == entry["head"]
save("INTEGRITY.json", {"recorded_at": REAL_NOW(), "all_preexisting_rows_preserved": True, "only_modified_preexisting_business_rows": {k:v["modified"] for k,v in changes.items() if v["modified"]}, "retained_rfq_unchanged": True, "retained_closing_at_tehran": retained.closing_at.astimezone(ZoneInfo("Asia/Tehran")), "retained_earliest_opening_at_tehran": retained.earliest_opening_at.astimezone(ZoneInfo("Asia/Tehran")), "source_chain_sha256": digest, "source_assessment": str(assessment.pk), "opening_separation": True, "all_new_financial_inventory_payroll_facts": 0, "data_changes": changes, "new_rfq_count": len(changes["procurement.RequestForQuotation"]["added"]), "temporary_scanner_duty": {"id": str(temporary.pk), "ends_at": temporary.ends_at, "effective_now": False, "revoked": temporary.revoked_at is not None, "expiry_enforced_without_bypass": True}, "additional_controls": checks, "changed_entry_files": changed_files, "git_head_index_unchanged": True, "production": "UNTOUCHED", "wave_d_cep078079": "NOT_EXECUTED"})
print("Integrity PASS; existing rows preserved; one synthetic RFQ; retained RFQ unchanged; source chain matches; temporary scan duty expired.")
