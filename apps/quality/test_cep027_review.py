from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.audit.models import AuditAction, AuditEvent
from apps.documents.models import DocumentType
from apps.documents.services import create_document
from apps.quality.models import QualityReviewEvidence, QualityReviewStatus
from apps.quality.record_review import (
    correct_returned_quality_record,
    decide_quality_record,
    submit_quality_record,
)
from apps.quality.services import (
    assign_quality_issue,
    close_quality_issue,
    review_quality_issue,
    start_quality_corrective_action,
    submit_quality_issue_for_verification,
    verify_quality_issue,
)
from apps.quality.tests import QualityTestBase


class QualityRecordReviewTests(QualityTestBase):
    def test_return_correction_resubmit_approval_and_history(self) -> None:
        issue = self.create_issue()
        first = submit_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            reason="Ready for review",
        )
        returned = decide_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            outcome=QualityReviewStatus.RETURNED,
            reason="Clarify specification",
        )
        corrected = correct_returned_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            description="Corrected defect",
            specification_reference="SPEC-REV-2",
            reason="Updated reference",
        )
        resubmitted = submit_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            reason="Corrected record",
        )
        approved = decide_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            outcome=QualityReviewStatus.APPROVED,
            reason="Record accepted",
        )
        self.assertEqual(
            [r.sequence for r in (first, returned, corrected, resubmitted, approved)],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(corrected.previous_id, returned.pk)
        self.assertEqual(first.snapshot["specification_reference"], "SPEC-CONC-04")
        self.assertEqual(resubmitted.snapshot["specification_reference"], "SPEC-REV-2")
        issue.refresh_from_db()
        self.assertEqual(issue.review_status, QualityReviewStatus.APPROVED)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(issue.pk),
                action=AuditAction.QUALITY_ISSUE_RECORD_REVIEWED,
            ).count(),
            5,
        )
        with self.assertRaises(ValidationError):
            first.delete()

    def test_permissions_tenant_and_invalid_evidence_fail_closed(self) -> None:
        issue = self.create_issue()
        with self.assertRaises(PermissionDenied):
            submit_quality_record(
                organization=self.organization,
                actor=self.viewer,
                issue_id=issue.pk,
                reason="Denied",
            )
        with self.assertRaises(PermissionDenied):
            submit_quality_record(
                organization=self.other_organization,
                actor=self.other_owner,
                issue_id=issue.pk,
                reason="Cross tenant",
            )
        with self.assertRaises(PermissionDenied):
            submit_quality_record(
                organization=self.organization,
                actor=self.owner,
                issue_id=issue.pk,
                reason="Bad evidence",
                document_version_ids=["00000000-0000-0000-0000-000000000001"],
            )
        self.assertEqual(issue.review_revisions.count(), 0)
        self.assertEqual(QualityReviewEvidence.objects.count(), 0)
        submit_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            reason="Submitted",
        )
        with self.assertRaises(PermissionDenied):
            decide_quality_record(
                organization=self.organization,
                actor=self.viewer,
                issue_id=issue.pk,
                outcome=QualityReviewStatus.APPROVED,
                reason="Denied",
            )

    def test_submitted_source_cannot_be_silently_edited(self) -> None:
        issue = self.create_issue()
        submit_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            reason="Submitted",
        )
        issue.refresh_from_db()
        issue.description = "Silent edit"
        with self.assertRaises(ValidationError):
            issue.save()

    def test_domain_closure_requires_record_approval(self) -> None:
        issue = self.create_issue()
        review_quality_issue(
            organization=self.organization, actor=self.owner, issue_id=issue.pk
        )
        assign_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        start_quality_corrective_action(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            corrective_action="Repair defect",
        )
        submit_quality_issue_for_verification(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            corrective_action_result="Repair complete",
        )
        verify_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            verification_summary="Verified",
        )
        with self.assertRaises(ValueError):
            close_quality_issue(
                organization=self.organization,
                actor=self.owner,
                issue_id=issue.pk,
                closure_summary="Closed",
            )
        self.approve_record(issue)
        closed = close_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            closure_summary="Closed after approval",
        )
        self.assertEqual(closed.status, "closed")

    def test_evidence_pins_exact_dms_version(self) -> None:
        issue = self.create_issue()
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Quality evidence",
            reference="QUAL-EVIDENCE-1",
            description="Controlled evidence",
            upload=SimpleUploadedFile(
                "evidence.pdf", b"%PDF-1.7\nevidence", content_type="application/pdf"
            ),
            target=self.project,
        )
        submitted = submit_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            reason="Evidence attached",
            document_version_ids=[str(document.current_version_id)],
        )
        self.assertEqual(
            submitted.evidence.get().document_version_id, document.current_version_id
        )
