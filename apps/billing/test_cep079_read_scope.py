"""Regression for Representative UAT's project-scoped progress readers."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.accounts.models import User
from apps.billing.models import BaselineItem, ProgressRecord, ProjectBaseline
from apps.billing.services import get_progress_records
from apps.contracts.models import Contract
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.projects.models import Project


class ProgressReadScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="uat-progress-reader")
        self.org = Organization.objects.create(name="UAT", slug="uat-progress")
        self.foreign = Organization.objects.create(name="Other", slug="uat-other")
        role = OrganizationRole.objects.create(
            organization=self.org, code="progress-read", name="Reader"
        )
        role.permissions.add(BusinessPermission.objects.get(code="progress.view"))
        self.membership = OrganizationMembership.objects.create(
            organization=self.org, user=self.user, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.org,
            membership=self.membership,
            role=role,
            reason="Test explicit role",
        )
        self.allowed = self.source(self.org, "A")
        self.denied = self.source(self.org, "B")
        self.other = self.source(self.foreign, "C")
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.membership,
            scope_type="project",
            project=self.allowed.baseline.project,
            reason="Test exact project",
        )

    def source(self, org, code):
        project = Project.objects.create(organization=org, code=code, name=code)
        contract = Contract.objects.create(
            organization=org,
            project=project,
            contract_number=code,
            title=code,
            counterparty_name="Synthetic",
            direction="receivable",
            status="active",
        )
        baseline = ProjectBaseline.objects.create(
            organization=org,
            project=project,
            contract=contract,
            version=1,
            effective_date=date(2026, 1, 1),
        )
        item = BaselineItem.objects.create(
            organization=org,
            baseline=baseline,
            line_key="1",
            description="Synthetic",
            unit="ea",
            planned_quantity=Decimal(1),
            unit_rate=Decimal(1),
            planned_value=Decimal(1),
        )
        return ProgressRecord.objects.create(
            organization=org,
            baseline=baseline,
            baseline_item=item,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 1),
            measured_on=date(2026, 1, 1),
            source_type="test",
            source_reference=code,
            period_quantity=Decimal(1),
            cumulative_quantity=Decimal(1),
        )

    def test_project_reader_sees_only_granted_project(self):
        self.assertEqual(
            list(get_progress_records(actor=self.user, organization=self.org)),
            [self.allowed],
        )

    def test_foreign_tenant_denied(self):
        with self.assertRaises(PermissionDenied):
            get_progress_records(actor=self.user, organization=self.foreign)

    def test_suspended_membership_denied(self):
        self.membership.status = "suspended"
        self.membership.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            get_progress_records(actor=self.user, organization=self.org)

    def test_organization_scope_stays_tenant_scoped(self):
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.membership,
            scope_type="organization",
            reason="Test organization scope",
        )
        self.assertSetEqual(
            set(get_progress_records(actor=self.user, organization=self.org)),
            {self.allowed, self.denied},
        )
