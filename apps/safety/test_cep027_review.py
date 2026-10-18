from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.audit.models import AuditAction, AuditEvent
from apps.documents.models import DocumentType
from apps.documents.services import create_document
from apps.safety.models import SafetyReviewEvidence, SafetyReviewStatus
from apps.safety.record_review import (
    correct_returned_safety_record,
    decide_safety_record,
    submit_safety_record,
)
from apps.safety.services import (
    assign_safety_incident,
    close_safety_incident,
    resolve_safety_incident,
    review_safety_incident,
    start_corrective_action,
)
from apps.safety.tests import SafetyTestBase


class SafetyRecordReviewTests(SafetyTestBase):
    def test_return_correction_resubmit_approval_and_history(self) -> None:
        incident = self.create_incident()
        with self.assertRaises(ValueError):
            decide_safety_record(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                outcome=SafetyReviewStatus.APPROVED,
                reason="Premature",
            )
        first = submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            reason="Ready for review",
        )
        returned = decide_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            outcome=SafetyReviewStatus.RETURNED,
            reason="Clarify immediate action",
        )
        corrected = correct_returned_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            description="Corrected incident detail",
            immediate_action="Area secured",
            reason="Clarified report",
        )
        resubmitted = submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            reason="Corrected record",
        )
        approved = decide_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            outcome=SafetyReviewStatus.APPROVED,
            reason="Record accepted",
        )
        self.assertEqual(
            [r.sequence for r in (first, returned, corrected, resubmitted, approved)],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(corrected.previous_id, returned.pk)
        self.assertEqual(first.snapshot["description"], "Falling object near miss")
        self.assertEqual(
            resubmitted.snapshot["description"], "Corrected incident detail"
        )
        incident.refresh_from_db()
        self.assertEqual(incident.review_status, SafetyReviewStatus.APPROVED)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(incident.pk),
                action=AuditAction.SAFETY_INCIDENT_RECORD_REVIEWED,
            ).count(),
            5,
        )
        with self.assertRaises(ValidationError):
            first.delete()
        with self.assertRaises(ValidationError):
            type(first).objects.filter(pk=first.pk).update(reason="Tampered")

    def test_permissions_tenant_and_policy_absence_fail_closed(self) -> None:
        incident = self.create_incident()
        with self.assertRaises(PermissionDenied):
            submit_safety_record(
                organization=self.organization,
                actor=self.viewer,
                incident_id=incident.pk,
                reason="Denied",
            )
        with self.assertRaises(PermissionDenied):
            submit_safety_record(
                organization=self.other_organization,
                actor=self.other_owner,
                incident_id=incident.pk,
                reason="Cross tenant",
            )
        with self.assertRaises(ValueError):
            submit_safety_record(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                reason=" ",
            )
        with self.assertRaises(PermissionDenied):
            submit_safety_record(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                reason="Bad evidence",
                document_version_ids=["00000000-0000-0000-0000-000000000001"],
            )
        self.assertEqual(incident.review_revisions.count(), 0)
        self.assertEqual(SafetyReviewEvidence.objects.count(), 0)
        submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            reason="Submitted",
        )
        with self.assertRaises(PermissionDenied):
            decide_safety_record(
                organization=self.organization,
                actor=self.viewer,
                incident_id=incident.pk,
                outcome=SafetyReviewStatus.APPROVED,
                reason="Denied",
            )

    def test_submitted_source_cannot_be_silently_edited(self) -> None:
        incident = self.create_incident()
        submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            reason="Submitted",
        )
        incident.refresh_from_db()
        incident.description = "Silent edit"
        with self.assertRaises(ValidationError):
            incident.save()

    def test_evidence_pins_exact_dms_version(self) -> None:
        incident = self.create_incident()
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Safety evidence",
            reference="SAFE-EVIDENCE-1",
            description="Controlled evidence",
            upload=SimpleUploadedFile(
                "evidence.pdf", b"%PDF-1.7\nevidence", content_type="application/pdf"
            ),
            target=self.project,
        )
        submitted = submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            reason="Evidence attached",
            document_version_ids=[str(document.current_version_id)],
        )
        self.assertEqual(
            submitted.evidence.get().document_version_id, document.current_version_id
        )

    def test_domain_closure_requires_record_approval(self) -> None:
        incident = self.create_incident()
        review_safety_incident(
            organization=self.organization, actor=self.owner, incident_id=incident.pk
        )
        assign_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        start_corrective_action(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            corrective_action="Install control",
        )
        resolve_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            resolution_summary="Control installed",
        )
        with self.assertRaises(ValueError):
            close_safety_incident(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                closure_summary="Closed",
            )
        self.approve_record(incident)
        closed = close_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            closure_summary="Closed after approval",
        )
        self.assertEqual(closed.status, "closed")
