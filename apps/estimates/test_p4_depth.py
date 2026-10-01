from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.estimates.models import EstimateRevisionStatus
from apps.estimates.services import (
    add_estimate_assumption,
    add_estimate_item,
    compare_revisions,
    create_estimate,
    create_estimate_revision,
    create_price_source,
    preview_estimate_csv,
    record_estimate_rate,
)
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.payments.models import Payment
from apps.projects.services import create_project


class EstimateDepthTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p4-owner")
        self.other = User.objects.create_user(username="p4-other")
        self.organization = Organization.objects.create(name="P4", slug="p4")
        self.other_organization = Organization.objects.create(
            name="P4 Other", slug="p4-other"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization, actor=self.owner, code="P4", name="P4"
        )
        self.estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="P4-1",
            title="P4",
        )
        self.item = add_estimate_item(
            estimate=self.estimate,
            actor=self.owner,
            description="Line",
            quantity=Decimal(2),
            unit_price=Decimal(5),
        )

    def test_comparison_uses_revision_evidence_and_approved_assumption_is_immutable(
        self,
    ) -> None:
        revision = self.estimate.current_revision
        add_estimate_assumption(
            revision=revision,
            actor=self.owner,
            kind="coefficient",
            name="OH",
            decimal_value=Decimal("0.1"),
            sequence=1,
            rationale="record",
            source_reference="internal",
        )
        from apps.estimates.services import approve_estimate

        approve_estimate(estimate=self.estimate, actor=self.owner)
        revision.refresh_from_db()
        self.assertEqual(revision.status, EstimateRevisionStatus.APPROVED)
        with self.assertRaises(ValidationError):
            revision.assumptions.first().save()
        draft = create_estimate_revision(estimate=self.estimate, actor=self.owner)
        result = compare_revisions(
            estimate=self.estimate, left=revision, right=draft, actor=self.owner
        )
        self.assertEqual(result.difference, Decimal("0.00"))

    def test_source_lineage_requires_same_tenant_and_external_source_is_closed(
        self,
    ) -> None:
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EA",
            name="Each",
            symbol="ea",
            category="count",
        )
        source = create_price_source(
            organization=self.organization,
            actor=self.owner,
            code="INT",
            name="Internal",
            version="1",
            source_reference="file",
            license_reference="owned",
        )
        rate = record_estimate_rate(
            price_source=source,
            actor=self.owner,
            resource_type="labor",
            code="L1",
            unit_of_measure=unit,
            rate=Decimal("12.5"),
        )
        self.assertEqual(rate.source_version_snapshot, "1")
        with self.assertRaisesMessage(ValueError, "P4-G03"):
            create_price_source(
                organization=self.organization,
                actor=self.owner,
                code="EXT",
                name="External",
                version="1",
                source_reference="x",
                license_reference="x",
                is_external=True,
            )
        with self.assertRaises(PermissionDenied):
            create_price_source(
                organization=self.organization,
                actor=self.other,
                code="NO",
                name="No",
                version="1",
                source_reference="x",
                license_reference="x",
            )

    def test_preview_rejects_formula_and_unknown_mapping_without_mutation(self) -> None:
        before = self.estimate.items.count()
        payments_before = Payment.objects.count()
        formula = preview_estimate_csv(
            estimate=self.estimate,
            actor=self.owner,
            content="description,quantity,unit,unit_price,sort_order\n=SUM(A1),1,ea,2,0\n",
        )
        unknown = preview_estimate_csv(
            estimate=self.estimate,
            actor=self.owner,
            content="description,qty,unit,unit_price,sort_order\nA,1,ea,2,0\n",
        )
        self.assertEqual(formula.valid_rows, 0)
        self.assertIn("فرمول", formula.errors[0])
        self.assertIn("P4-G04", unknown.errors[0])
        self.assertEqual(self.estimate.items.count(), before)
        self.assertEqual(Payment.objects.count(), payments_before)
