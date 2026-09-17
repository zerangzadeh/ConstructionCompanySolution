from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.contracts.models import (
    ContractAmendment,
    ContractAmendmentStatus,
    ContractStatus,
)
from apps.contracts.services import approve_contract_amendment, create_contract
from apps.contracts.workflow import (
    backfill_open_contract_amendment_approvals,
    contract_amendment_shadow_comparison,
    request_contract_amendment_approval,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.projects.services import create_project
from apps.workflows.models import WorkflowInstance, WorkflowInstanceStatus


class ContractAmendmentWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="w54-contract-owner")
        self.other_owner = User.objects.create_user(username="w54-contract-other")
        self.organization = Organization.objects.create(
            name="W54 Contract", slug="w54-contract"
        )
        self.other_organization = Organization.objects.create(
            name="W54 Contract Other", slug="w54-contract-other"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="W54-C",
            name="Contract workflow",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=project,
            actor=self.owner,
            contract_number="W54-C-1",
            title="Active",
            counterparty_name="Client",
            status=ContractStatus.ACTIVE,
            contract_value=Decimal(100),
        )

    def _amendment(self, number: int = 1) -> ContractAmendment:
        return ContractAmendment.objects.create(
            organization=self.organization,
            contract=self.contract,
            amendment_number=number,
            title="Extension",
            reason="Scope",
            value_change=Decimal(5),
            created_by=self.owner,
        )

    def test_explicit_request_completes_with_shared_runtime_and_locks_amendment(
        self,
    ) -> None:
        amendment = self._amendment()
        instance = request_contract_amendment_approval(
            organization=self.organization, actor=self.owner, amendment=amendment
        )
        self.assertFalse(
            contract_amendment_shadow_comparison(
                organization=self.organization, amendment=amendment
            )["mismatch"]
        )
        approved = approve_contract_amendment(
            organization=self.organization, actor=self.owner, amendment=amendment
        )
        approved.refresh_from_db()
        self.assertEqual(approved.status, ContractAmendmentStatus.APPROVED)
        self.assertEqual(
            WorkflowInstance.objects.get(pk=instance.pk).status,
            WorkflowInstanceStatus.COMPLETED,
        )
        approved.title = "Changed"
        with self.assertRaises(ValidationError):
            approved.save()

    def test_backfill_does_not_make_drafts_actionable_and_tenant_scope_is_enforced(
        self,
    ) -> None:
        amendment = self._amendment()
        report = backfill_open_contract_amendment_approvals(
            organization=self.organization
        )
        self.assertEqual((report.scanned, report.created), (0, 0))
        self.assertFalse(
            WorkflowInstance.objects.filter(subject_id=amendment.pk).exists()
        )
        request_contract_amendment_approval(
            organization=self.organization, actor=self.owner, amendment=amendment
        )
        with self.assertRaises(PermissionDenied):
            approve_contract_amendment(
                organization=self.other_organization,
                actor=self.other_owner,
                amendment=amendment,
            )
        self.assertEqual(
            backfill_open_contract_amendment_approvals(
                organization=self.organization
            ).existing,
            1,
        )
