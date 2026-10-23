"""Canonical synthetic Development RFQ with explicitly authorized application time."""
from support import *
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from apps.organizations.authorization import has_business_permission, require_business_permission
from apps.organizations.access_services import create_organization_role, assign_platform_role
from apps.organizations.platform_grants import platform_initial_grant
from apps.organizations.policy_services import create_platform_policy, create_platform_policy_version, publish_platform_policy_version, select_tenant_policy_version, apply_tenant_policy_selection
from apps.procurement.models import *
from apps.procurement.rfq_services import create_rfq, add_rfq_line, submit_rfq_for_issue, issue_rfq, close_rfq
from apps.procurement.quote_services import capture_quote_revision, submit_quote_revision
from apps.procurement.custody_services import custody_sealed_quote_evidence
from apps.procurement.opening_services import request_quote_opening, approve_quote_opening, grant_quote_confidential_access, deliver_quote_confidential_document
from apps.procurement.admissibility_services import prepare_quote_admissibility, approve_quote_admissibility
from apps.procurement.comparison_services import prepare_comparison
from apps.procurement.rfq_action_forms import confidential_revisions, comparison_records
from apps.documents.services import record_document_processing_assessment
from apps.documents.models import DocumentProcessingAssessment

guard()
org = Organization.objects.get(slug="demo-construction-01")
retained = RequestForQuotation.objects.select_related("project", "purchase_request").get(organization=org, rfq_number="WAVE-C-RFQ-A")
project = retained.project
owner = User.objects.get(username="account.demo-construction-01.owner")
buyer = User.objects.get(username="uiux.wavec.buyer")
custodian = User.objects.get(username="uiux.wavec.custodian")
opening_approver = User.objects.get(username="uiux.wavec.opening-approver")
platform = User.objects.get(username="admin")
tenant_admin = User.objects.get(username="uiux.persona.tenant-admin")
scanner_actor = custodian
LABEL = "RV007-CONTROLLED-DEV-001"

def deny(case, operation, exceptions=(PermissionDenied, ValueError, ValidationError)):
    try:
        operation()
    except exceptions as exc:
        controls.append({"case": case, "result": "DENIED", "exception": type(exc).__name__, "message": str(exc), "application_now": timezone.now()})
        save("SERVICE_CONTROLS.json", controls)
    else:
        raise AssertionError("Expected denial: " + case)

controls = read("SERVICE_CONTROLS.json") if (OUT / "SERVICE_CONTROLS.json").exists() else []

def prerequisites():
    assert not (OUT / "PREREQUISITES.json").exists()
    with transaction.atomic():
        role = create_organization_role(actor=platform, organization=org, code="rv007_admissibility_approver", name="تأییدکننده مستقل پذیرش آزمایشی توسعه", description="Human-approved RV-007 only; exact Project; no default-role change", permissions=["rfq_quotes.approve_admissibility", "rfq_quotes.view_confidential"], reason="Human RV-007 bounded prerequisite authorization; self-approval disabled")
        membership = OrganizationMembership.objects.get(organization=org, user=custodian)
        assignment, scope = platform_initial_grant(organization=org, actor=platform, membership_id=membership.pk, role=role, scope_type="project", project=project, reason="Human RV-007 exact Project independent admissibility approver; existing custodian distinct from preparer")
        policy = create_platform_policy(actor=platform, code="rfq-admissibility-self-approval", reason="Human RV-007 Development-only prerequisite")
        version = create_platform_policy_version(actor=platform, policy=policy, version=1, parameters={"allow_self_approval": False}, effective_from=timezone.localdate(), effective_to=timezone.localdate()+timedelta(days=3), reason="Human RV-007 UIUX_TEST_ONLY_NON_AUTHORITATIVE; no self-approval", source_basis="product_defined")
        version = publish_platform_policy_version(actor=platform, policy_version=version, reason="Human-approved RV-007 Development-only explicit false")
        selection = select_tenant_policy_version(organization=org, actor=tenant_admin, policy_version=version, reason="Human-approved RV-007 Development-only admissibility policy")
        selection = apply_tenant_policy_selection(organization=org, actor=tenant_admin, selection=selection)
    save("PREREQUISITES.json", {"authorization": "Human Option 1 reply in current chat", "role": str(role.pk), "assignment": str(assignment.pk), "scope": str(scope.pk), "scope_type": scope.scope_type, "project": str(project.pk), "approver": custodian.username, "policy_version": str(version.pk), "selection": str(selection.pk), "allow_self_approval": False, "effective_from": version.effective_from, "effective_to": version.effective_to, "default_roles_changed": False})
    print("Minimal canonical policy and exact-Project independent approver provisioned.")

def pdf_bytes():
    text = "SYNTHETIC DEVELOPMENT ONLY RV-007. Unit price IRR 12.50. Discount 0.50. Not an actual supplier quotation."
    stream = f"BT /F1 10 Tf 40 100 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 700 180] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data = b"%PDF-1.7\n"; offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data)); data += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    start = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    return data

def prepare():
    assert not (OUT / "FIXTURE.json").exists()
    assert not RequestForQuotation.objects.filter(organization=org, rfq_number=LABEL).exists()
    begin = REAL_NOW()
    set_clock(begin, "on_time_receipt_and_submission")
    payload = pdf_bytes()
    (OUT / "SYNTHETIC_QUOTE.pdf").write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    # Temporary real-time scanner duty is canonical, expires in five minutes;
    # no expired duty is revived by moving the application clock backwards.
    superuser = User.objects.get(username="superuser")
    assignment = assign_platform_role(actor=superuser, approver=superuser, target=scanner_actor, role="platform_operations", reason="Existing PD-WC-07 / Human RV-007 valid synthetic source scan only", ends_at=begin + timedelta(minutes=5))
    with patch("django.utils.timezone.now", side_effect=controlled_now):
        with transaction.atomic():
            item = retained.purchase_request.items.order_by("pk").first()
            rfq = create_rfq(organization=org, actor=owner, project=project, purchase_request=retained.purchase_request, rfq_number=LABEL, title="استعلام مصنوعی توسعه — کنترل گشایش و مقایسه", closing_at=begin+timedelta(minutes=1), earliest_opening_at=begin+timedelta(minutes=1,hours=24), terms="UIUX_TEST_ONLY_NON_AUTHORITATIVE; controlled application clock; no actual supplier offer")
            add_rfq_line(organization=org, actor=owner, rfq=rfq, purchase_request_item=item, quantity=item.quantity)
            submit_rfq_for_issue(organization=org, actor=owner, rfq=rfq)
            supplier = retained.versions.get(version_number=retained.current_version_number).invitations.first().supplier
            version = issue_rfq(organization=org, actor=owner, rfq=rfq, suppliers=[supplier], idempotency_key=LABEL+"-issue")
            revision = capture_quote_revision(organization=org, actor=buyer, invitation=version.invitations.get(), integrity_fingerprint=digest, source_channel="manual_capture", source_reference="RV007-CONTROLLED-SYNTHETIC-PDF", idempotency_key=LABEL+"-capture")
            revision = submit_quote_revision(organization=org, actor=buyer, revision=revision, idempotency_key=LABEL+"-submit")
            assert not revision.is_late and revision.received_at <= version.closing_at and revision.submitted_at <= version.closing_at
        made = {"rfq": str(rfq.pk), "version": str(version.pk), "revision": str(revision.pk), "source_sha256": digest, "begin": begin.isoformat(), "closing_at": version.closing_at.isoformat(), "earliest_opening_at": version.earliest_opening_at.isoformat(), "actual_creation_wall_clock": REAL_NOW().isoformat(), "scanner_assignment": str(assignment.pk), "scanner_assignment_expires": assignment.ends_at.isoformat()}
        save("FIXTURE.json", made)
        set_clock(begin+timedelta(minutes=2), "canonical_close_and_custody")
        manifest = close_rfq(organization=org, actor=custodian, rfq=rfq, idempotency_key=LABEL+"-close")
        assert manifest.entries.get().effective_revision_id == revision.pk
        evidence = custody_sealed_quote_evidence(organization=org, actor=custodian, quote_revision=revision, evidence_type="supplier_original", evidence_slot="primary", upload=SimpleUploadedFile("rv007-synthetic-quote.pdf", payload, content_type="application/pdf"), idempotency_key=LABEL+"-custody")
        made.update(manifest=str(manifest.pk), evidence=str(evidence.pk), document_version=str(evidence.document_version_id))
        save("FIXTURE.json", made)
        deny("early protected opening after close but before close+24h", lambda: request_quote_opening(organization=org, actor=buyer, quote_revision=revision, reason=LABEL, idempotency_key=LABEL+"-early"))
        deny("unopened confidential source delivery", lambda: deliver_quote_confidential_document(organization=org, actor=buyer, quote_revision=revision, evidence=evidence))
        assert not DocumentProcessingAssessment.objects.filter(version=evidence.document_version).exists()
        scanner = sorted(Path("C:/ProgramData/Microsoft/Windows Defender/Platform").glob("*/MpCmdRun.exe"))[-1]
        source = Path(evidence.document_version.file.path)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest == evidence.canonical_sha256 == evidence.document_version.sha256
        scan = subprocess.run([str(scanner), "-Scan", "-ScanType", "3", "-File", str(source), "-DisableRemediation"], capture_output=True, text=True, timeout=55)
        scan_result = {"scanner": str(scanner), "version": scanner.parent.name, "exit_code": scan.returncode, "stdout": scan.stdout, "stderr": scan.stderr, "sha256_before": digest, "sha256_after": hashlib.sha256(source.read_bytes()).hexdigest(), "actual_wall_clock": REAL_NOW(), "application_clock": timezone.now()}
        save("SCAN.json", scan_result)
        assert scan.returncode == 0 and "found no threats" in scan.stdout.lower()
        assert scan_result["sha256_after"] == digest
        assessment = record_document_processing_assessment(version=evidence.document_version, actor=scanner_actor, verdict="clean", adapter_code="microsoft-defender-mpcmdrun", adapter_version=scanner.parent.name)
        scan_result["assessment"] = str(assessment.pk); save("SCAN.json", scan_result)
    print("Canonical synthetic RFQ and on-time quote retained; close/custody completed; real Defender clean scan recorded; early opening denied.")

def opened():
    made = read("FIXTURE.json")
    rfq = RequestForQuotation.objects.get(pk=made["rfq"])
    revision = QuoteRevision.objects.get(pk=made["revision"])
    evidence = QuoteRevisionEvidence.objects.get(pk=made["evidence"])
    earliest = datetime.fromisoformat(made["earliest_opening_at"])
    set_clock(earliest-timedelta(microseconds=1), "one_microsecond_before_24_hour_boundary")
    with patch("django.utils.timezone.now", side_effect=controlled_now):
        deny("close+24h minus one microsecond", lambda: request_quote_opening(organization=org, actor=buyer, quote_revision=revision, reason=LABEL, idempotency_key=LABEL+"-boundary-early"))
        set_clock(earliest+timedelta(seconds=1), "protected_opening_and_comparison_after_24h")
        opening_request = request_quote_opening(organization=org, actor=buyer, quote_revision=revision, reason="RV007 controlled Development opening", idempotency_key=LABEL+"-opening")
        deny("requester cannot approve own opening", lambda: approve_quote_opening(organization=org, actor=buyer, opening_request=opening_request))
        opening = approve_quote_opening(organization=org, actor=opening_approver, opening_request=opening_request)
        assert opening.approved_by_id != opening_request.requested_by_id
        assert approve_quote_opening(organization=org, actor=opening_approver, opening_request=opening_request).pk == opening.pk
        deny("business permission without revision grant cannot read source", lambda: deliver_quote_confidential_document(organization=org, actor=buyer, quote_revision=revision, evidence=evidence))
        for actor in (buyer, custodian):
            grant_quote_confidential_access(organization=org, actor=opening_approver, quote_revision=revision, membership=org.memberships.get(user=actor), reason="RV007 exact opened revision only", idempotency_key=LABEL+"-grant-"+actor.username)
        delivery = deliver_quote_confidential_document(organization=org, actor=buyer, quote_revision=revision, evidence=evidence)
        assert hashlib.sha256(delivery.content).hexdigest() == made["source_sha256"] == delivery.canonical_sha256
        preparation = prepare_quote_admissibility(organization=org, actor=buyer, quote_revision=revision, state="admissible", reason_code="requirements_met", rationale="Synthetic quote: original retained, on-time submission, clean scan and protected opening verified", idempotency_key=LABEL+"-admissibility")
        deny("admissibility preparer cannot approve", lambda: approve_quote_admissibility(organization=org, actor=buyer, preparation=preparation))
        decision = approve_quote_admissibility(organization=org, actor=custodian, preparation=preparation)
        # Scope has no application creator service. Use its existing immutable,
        # validating domain constructor under the exact canonical permission.
        require_business_permission(user=buyer, organization=org, permission="rfq_quotes.prepare_comparison", project=project, message="RV007 exact comparison scope")
        line = revision.rfq_version.lines.get()
        scope = RFQCommercialScope(organization=org, rfq_version=revision.rfq_version, rfq_version_line=line, scope_type="line", scope_code="RV007-SYNTHETIC-LINE", required_quantity=line.quantity, unit_of_measure=line.unit_of_measure, created_by=buyer)
        scope.full_clean(); scope.save()
        comparison = prepare_comparison(organization=org, actor=buyer, scope=scope, assertions=[{"quote_revision_id": str(revision.pk), "offered_quantity": str(line.quantity), "unit_price": "12.50", "currency": "IRR", "explicit_discount": "0.50", "source_locator": "page-1-synthetic-unit-price"}], idempotency_key=LABEL+"-comparison")
        assert confidential_revisions(rfq=rfq, actor=buyer).filter(pk=revision.pk).exists()
        assert comparison_records(rfq=rfq, actor=buyer).filter(pk=comparison.pk).exists()
        unauthorized = User.objects.get(username="uiux.wavec.hr")
        site_only = User.objects.get(username="uiux.reference.batch03.site-only")
        foreign_org = Organization.objects.get(slug="demo-construction-02")
        foreign_actor = User.objects.get(username="account.demo-construction-02.owner")
        for name, actor, tenant in [("same-tenant unauthorized confidential denial", unauthorized, org), ("site-only cannot read project-level confidential quote", site_only, org), ("cross-tenant confidential denial", foreign_actor, foreign_org), ("opening approver cannot read confidential content without permission", opening_approver, org)]:
            deny(name, lambda actor=actor, tenant=tenant: deliver_quote_confidential_document(organization=tenant, actor=actor, quote_revision=revision, evidence=evidence))
            assert not comparison_records(rfq=rfq, actor=actor).filter(pk=comparison.pk).exists()
        deny("changed idempotent opening reason rejected", lambda: request_quote_opening(organization=org, actor=buyer, quote_revision=revision, reason="Manipulated reason", idempotency_key=LABEL+"-opening"))
        deny("sealed original cannot be silently overwritten", lambda: custody_sealed_quote_evidence(organization=org, actor=custodian, quote_revision=revision, evidence_type="supplier_original", evidence_slot="primary", upload=SimpleUploadedFile("changed.pdf", pdf_bytes()+b"%different", content_type="application/pdf"), idempotency_key=LABEL+"-custody"))
        assert hashlib.sha256(Path(evidence.document_version.file.path).read_bytes()).hexdigest() == made["source_sha256"]
        made.update(opening_request=str(opening_request.pk), opening=str(opening.pk), opening_requester=buyer.username, opening_approver=opening_approver.username, admissibility_preparer=buyer.username, admissibility_approver=custodian.username, admissibility_decision=str(decision.pk), scope=str(scope.pk), comparison=str(comparison.pk), application_opened_at=opening.opened_at.isoformat(), actual_opening_wall_clock=REAL_NOW().isoformat(), delivery_sha256=delivery.canonical_sha256)
        save("FIXTURE.json", made)
    print("Protected opening and independent admissibility approved; populated confidential comparison prepared; source and negative service controls PASS.")

if __name__ == "__main__":
    {"prerequisites": prerequisites, "prepare": prepare, "open": opened}[sys.argv[1]]()
