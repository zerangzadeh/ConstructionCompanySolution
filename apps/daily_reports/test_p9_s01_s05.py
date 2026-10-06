from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.daily_reports.field_models import (
    FieldObservationStatus,
    FieldProposalStatus,
)
from apps.daily_reports.field_services import (
    create_field_correction,
    create_field_observation,
    create_field_proposal,
    review_field_observation,
    review_field_proposal,
    start_field_observation_review,
    submit_field_observation,
    submit_field_proposal,
    update_field_observation,
)
from apps.documents.models import DocumentProcessingVerdict, DocumentType
from apps.documents.services import (
    add_document_version,
    create_document,
    record_document_processing_assessment,
)
from apps.organizations.access_services import assign_platform_role
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
    PlatformRoleCode,
)
from apps.organizations.services import set_active_organization
from apps.projects.services import create_project, create_project_site


class FieldOperationsP9S01S05Tests(TestCase):
    def setUp(self):
        self.storage_directory = TemporaryDirectory()
        self.storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self.storage_directory.name
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.storage_directory.cleanup)
        self.creator = User.objects.create_user(username="p9-field-creator", password="test-password")
        self.reviewer = User.objects.create_user(username="p9-field-reviewer", password="test-password")
        self.other = User.objects.create_user(username="p9-field-other", password="test-password")
        self.viewer = User.objects.create_user(username="p9-field-viewer", password="test-password")
        self.organization = Organization.objects.create(
            name="P9 Field Company", slug="p9-field-company", created_by=self.creator, updated_by=self.creator
        )
        self.other_organization = Organization.objects.create(
            name="P9 Other Company", slug="p9-other-company", created_by=self.other, updated_by=self.other
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.organization.memberships.create(user=self.creator, role=MembershipRole.COMPANY_OWNER, status=MembershipStatus.ACTIVE)
        self.organization.memberships.create(user=self.reviewer, role=MembershipRole.COMPANY_MANAGER, status=MembershipStatus.ACTIVE)
        self.organization.memberships.create(user=self.viewer, role=MembershipRole.VIEWER, status=MembershipStatus.ACTIVE)
        self.other_organization.memberships.create(user=self.other, role=MembershipRole.COMPANY_OWNER, status=MembershipStatus.ACTIVE)
        self.project = create_project(organization=self.organization, actor=self.creator, code="P9-P", name="P9 project")
        self.site = create_project_site(organization=self.organization, project=self.project, actor=self.creator, code="P9-S", name="P9 site")
        self.other_project = create_project(organization=self.other_organization, actor=self.other, code="P9-OP", name="Other project")

    @staticmethod
    def _upload(name: str, suffix: bytes = b"") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, b"%PDF-1.7\nfield evidence" + suffix, content_type="application/pdf")

    def _create(self, operation_key=None):
        return create_field_observation(
            organization=self.organization,
            actor=self.creator,
            project=self.project,
            site=self.site,
            kind="work_front",
            title="Rebar observation",
            summary="Foundation work observed.",
            structured_payload={"quantity": "12", "unit": "m"},
            captured_at=datetime(2026, 10, 5, 7, 0, tzinfo=dt_timezone.utc),
            operation_key=operation_key or uuid4(),
        )

    def test_create_is_idempotent_and_cross_tenant_is_denied(self):
        key = uuid4()
        observation = self._create(key)
        self.assertEqual(self._create(key).pk, observation.pk)
        with self.assertRaises(PermissionDenied):
            create_field_observation(
                organization=self.organization,
                actor=self.creator,
                project=self.other_project,
                site=None,
                kind="general",
                title="Cross tenant",
                operation_key=uuid4(),
            )

    def test_capture_permission_project_site_scope_and_minimized_location(self):
        other_project = create_project(
            organization=self.organization, actor=self.creator, code="P9-P2", name="Other P9 project"
        )
        other_site = create_project_site(
            organization=self.organization, project=other_project, actor=self.creator, code="P9-S2", name="Other P9 site"
        )
        with self.assertRaises(PermissionDenied):
            create_field_observation(
                organization=self.organization, actor=self.viewer, project=self.project, site=self.site,
                kind="general", title="Viewer cannot capture", operation_key=uuid4(),
            )
        with self.assertRaises(PermissionDenied):
            create_field_observation(
                organization=self.organization, actor=self.creator, project=self.project, site=other_site,
                kind="general", title="Mismatched site", operation_key=uuid4(),
            )
        observation = create_field_observation(
            organization=self.organization, actor=self.creator, project=self.project, site=self.site,
            kind="general", title="Untrusted location", location_permission="granted",
            latitude=Decimal("35.700000"), longitude=Decimal("51.400000"),
            horizontal_accuracy_meters=Decimal("80.00"), location_mismatch_note="Manual context wins.",
            location_captured_at=datetime(2026, 10, 5, 7, 0, tzinfo=dt_timezone.utc),
            client_context={"platform": "android", "device_id": "discarded"}, operation_key=uuid4(),
        )
        self.assertEqual(observation.location_mismatch_note, "Manual context wins.")
        self.assertEqual(observation.client_context, {"platform": "android"})

    def test_dms_version_hash_is_pinned_and_submission_blocks_new_attachment(self):
        observation = self._create()
        document = create_document(
            organization=self.organization, actor=self.creator, document_type=DocumentType.GENERAL,
            title="Field photo evidence", upload=self._upload("field.pdf"), target=observation,
        )
        assigner = User.objects.create_superuser(username="p9-platform-assigner")
        approver = User.objects.create_superuser(username="p9-platform-approver")
        operator = User.objects.create_user(username="p9-platform-operator")
        assign_platform_role(
            actor=assigner, approver=approver, target=operator,
            role=PlatformRoleCode.PLATFORM_OPERATIONS, reason="P9 validation",
        )
        first = document.current_version
        record_document_processing_assessment(
            version=first, actor=operator, verdict=DocumentProcessingVerdict.CLEAN,
            adapter_code="test-scanner",
        )
        link = observation.evidence_links.get(document=document)
        self.assertEqual(link.document_version_id, first.pk)
        self.assertEqual(link.sha256, first.sha256)
        second = add_document_version(document=document, actor=self.creator, upload=self._upload("field-v2.pdf", b"-v2"))
        self.assertNotEqual(first.sha256, second.sha256)
        link.refresh_from_db()
        self.assertEqual(link.document_version_id, first.pk)
        submit_field_observation(organization=self.organization, actor=self.creator, observation_id=observation.pk, operation_key=uuid4())
        with self.assertRaises(PermissionDenied):
            create_document(
                organization=self.organization, actor=self.creator, document_type=DocumentType.GENERAL,
                title="Late evidence", upload=self._upload("late.pdf"), target=observation,
            )

    def test_responsive_rtl_workbench_is_accessible_to_authorized_user(self):
        self.client.force_login(self.creator)
        set_active_organization(self.client.session, self.organization)
        response = self.client.get(reverse("daily_reports:field_observation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "مشاهدات میدانی")

    def test_draft_revision_and_immutable_review_lineage(self):
        observation = self._create()
        save_key = uuid4()
        updated = update_field_observation(
            organization=self.organization,
            actor=self.creator,
            observation_id=observation.pk,
            expected_revision=1,
            operation_key=save_key,
            summary="Updated field evidence.",
        )
        self.assertEqual(
            update_field_observation(
                organization=self.organization,
                actor=self.creator,
                observation_id=observation.pk,
                expected_revision=1,
                operation_key=save_key,
                summary="Updated field evidence.",
            ).pk,
            updated.pk,
        )
        with self.assertRaises(ValidationError):
            update_field_observation(
                organization=self.organization,
                actor=self.creator,
                observation_id=observation.pk,
                expected_revision=1,
                operation_key=save_key,
                summary="Different retry payload.",
            )
        with self.assertRaises(ValidationError):
            update_field_observation(
                organization=self.organization,
                actor=self.creator,
                observation_id=observation.pk,
                expected_revision=1,
                operation_key=uuid4(),
                summary="Stale update",
            )
        submit_field_observation(organization=self.organization, actor=self.creator, observation_id=observation.pk, operation_key=uuid4())
        start_field_observation_review(organization=self.organization, actor=self.reviewer, observation_id=observation.pk, operation_key=uuid4())
        review_key = uuid4()
        accepted = review_field_observation(organization=self.organization, actor=self.reviewer, observation_id=observation.pk, accepted=True, reason="Evidence is admissible.", operation_key=review_key)
        self.assertEqual(accepted.status, FieldObservationStatus.ACCEPTED)
        self.assertEqual(
            review_field_observation(
                organization=self.organization,
                actor=self.reviewer,
                observation_id=observation.pk,
                accepted=True,
                reason="Evidence is admissible.",
                operation_key=review_key,
            ).status,
            FieldObservationStatus.ACCEPTED,
        )
        with self.assertRaises(PermissionDenied):
            review_field_observation(organization=self.organization, actor=self.creator, observation_id=observation.pk, accepted=True, reason="", operation_key=uuid4())
        correction = create_field_correction(
            organization=self.organization,
            actor=self.creator,
            predecessor_id=observation.pk,
            operation_key=uuid4(),
            correction_reason="Corrected measured context.",
            title="Corrected rebar observation",
            summary="Corrected evidence.",
        )
        self.assertEqual(correction.replaces_id, observation.pk)
        self.assertEqual(correction.status, FieldObservationStatus.DRAFT)

    def test_reviewed_proposal_does_not_create_downstream_fact(self):
        observation = self._create()
        submit_field_observation(organization=self.organization, actor=self.creator, observation_id=observation.pk, operation_key=uuid4())
        start_field_observation_review(organization=self.organization, actor=self.reviewer, observation_id=observation.pk, operation_key=uuid4())
        review_field_observation(organization=self.organization, actor=self.reviewer, observation_id=observation.pk, accepted=True, reason="Accepted.", operation_key=uuid4())
        proposal = create_field_proposal(
            organization=self.organization,
            actor=self.creator,
            observation_id=observation.pk,
            family="progress",
            lines=[{"description": "Foundation", "quantity": "12", "unit": "m"}],
            operation_key=uuid4(),
        )
        submit_field_proposal(organization=self.organization, actor=self.creator, proposal_id=proposal.pk, operation_key=uuid4())
        proposal_review_key = uuid4()
        reviewed = review_field_proposal(organization=self.organization, actor=self.reviewer, proposal_id=proposal.pk, accepted=True, reason="Proposal is reviewable.", operation_key=proposal_review_key)
        self.assertEqual(reviewed.status, FieldProposalStatus.ACCEPTED)
        self.assertEqual(
            review_field_proposal(
                organization=self.organization,
                actor=self.reviewer,
                proposal_id=proposal.pk,
                accepted=True,
                reason="Proposal is reviewable.",
                operation_key=proposal_review_key,
            ).status,
            FieldProposalStatus.ACCEPTED,
        )
        self.assertFalse(hasattr(reviewed, "progress_record"))
