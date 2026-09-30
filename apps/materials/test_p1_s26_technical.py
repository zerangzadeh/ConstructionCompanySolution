from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import User
from apps.documents.models import DocumentType
from apps.documents.services import create_document
from apps.materials.models import (
    MaterialRelationshipType,
    MaterialTechnicalApprovalStatus,
)
from apps.materials.services import (
    create_material,
    create_material_category,
    create_material_technical_revision,
    create_unit_of_measure,
    record_material_relationship,
    transition_material_technical_revision,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)


class P1S26TechnicalGovernanceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="s26-author")
        self.approver = User.objects.create_user(username="s26-approver")
        self.organization = Organization.objects.create(name="S26", slug="s26")
        OrganizationSettings.objects.create(organization=self.organization)
        for user in (self.author, self.approver):
            self.organization.memberships.create(user=user, role=MembershipRole.COMPANY_OWNER, status=MembershipStatus.ACTIVE)
        category = create_material_category(organization=self.organization, actor=self.author, code="STEEL", name="Steel")
        unit = create_unit_of_measure(organization=self.organization, actor=self.author, code="KG", name="Kilogram", symbol="kg", category="weight")
        self.source = create_material(organization=self.organization, actor=self.author, code="A", name="A", category=category, unit_of_measure=unit)
        self.candidate = create_material(organization=self.organization, actor=self.author, code="B", name="B", category=category, unit_of_measure=unit)

    def test_relationship_and_separated_technical_decision_preserve_history(self):
        relationship = record_material_relationship(organization=self.organization, actor=self.author, source=self.source, candidate=self.candidate, relationship_type=MaterialRelationshipType.EQUIVALENT, reason="technical comparison")
        self.assertEqual(relationship.source, self.source)
        approval = create_material_technical_revision(organization=self.organization, actor=self.author, material=self.source)
        approval = transition_material_technical_revision(organization=self.organization, actor=self.author, approval=approval, target_status=MaterialTechnicalApprovalStatus.REVIEW)
        with self.assertRaises(PermissionDenied):
            transition_material_technical_revision(organization=self.organization, actor=self.author, approval=approval, target_status=MaterialTechnicalApprovalStatus.APPROVED)
        approval = transition_material_technical_revision(organization=self.organization, actor=self.approver, approval=approval, target_status=MaterialTechnicalApprovalStatus.APPROVED, reason="evidence accepted")
        self.assertEqual(approval.status, MaterialTechnicalApprovalStatus.APPROVED)

    def test_new_approval_supersedes_prior_approved_revision(self):
        first = create_material_technical_revision(
            organization=self.organization, actor=self.author, material=self.source
        )
        first = transition_material_technical_revision(
            organization=self.organization, actor=self.author, approval=first,
            target_status=MaterialTechnicalApprovalStatus.REVIEW,
        )
        transition_material_technical_revision(
            organization=self.organization, actor=self.approver, approval=first,
            target_status=MaterialTechnicalApprovalStatus.APPROVED, reason="approved"
        )
        second = create_material_technical_revision(
            organization=self.organization, actor=self.author, material=self.source
        )
        second = transition_material_technical_revision(
            organization=self.organization, actor=self.author, approval=second,
            target_status=MaterialTechnicalApprovalStatus.REVIEW,
        )
        transition_material_technical_revision(
            organization=self.organization, actor=self.approver, approval=second,
            target_status=MaterialTechnicalApprovalStatus.APPROVED, reason="revised evidence"
        )
        first.refresh_from_db()
        self.assertEqual(first.status, MaterialTechnicalApprovalStatus.SUPERSEDED)

    def test_technical_document_link_pins_the_uploaded_document_version(self):
        document = create_document(
            organization=self.organization,
            actor=self.author,
            document_type=DocumentType.OTHER,
            title="Material datasheet",
            target=self.source,
            upload=SimpleUploadedFile(
                "datasheet.pdf", b"%PDF-1.4\ntechnical evidence", content_type="application/pdf"
            ),
        )
        link = self.source.document_links.get(document=document)
        self.assertEqual(link.document_version_id, document.current_version_id)
