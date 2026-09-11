from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.contracts.models import ContractStatus
from apps.contracts.services import create_contract, get_organization_contracts
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.projects.services import create_project


class ContractServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="contract-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-contract-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Contract Company",
            slug="contract-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Contract Company",
            slug="other-contract-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-CONTRACT",
            name="Contract project",
        )

    def test_create_contract_scopes_project_and_records_audit(self) -> None:
        contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="C-001",
            title="Main works contract",
            counterparty_name="Client LLC",
            status=ContractStatus.ACTIVE,
            contract_value=Decimal("250000.00"),
        )

        self.assertEqual(contract.project, self.project)
        self.assertEqual(contract.contract_value, Decimal("250000.00"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.CONTRACT_CREATED,
                organization=self.organization,
                entity_id=str(contract.pk),
            ).exists()
        )

    def test_contract_number_is_unique_per_organization(self) -> None:
        create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="C-002",
            title="First contract",
            counterparty_name="Client LLC",
        )
        with self.assertRaisesMessage(
            ValueError,
            "قراردادی با این شماره از قبل وجود دارد.",
        ):
            create_contract(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                contract_number="C-002",
                title="Duplicate contract",
                counterparty_name="Client LLC",
            )

    def test_contract_rejects_project_from_other_organization(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER",
            name="Other project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            create_contract(
                organization=self.organization,
                project=other_project,
                actor=self.owner,
                contract_number="C-003",
                title="Invalid contract",
                counterparty_name="Client LLC",
            )

    def test_contract_rejects_negative_value(self) -> None:
        with self.assertRaisesMessage(
            ValueError,
            "مبلغ قرارداد نمی‌تواند منفی باشد.",
        ):
            create_contract(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                contract_number="C-004",
                title="Invalid value",
                counterparty_name="Client LLC",
                contract_value=Decimal("-1.00"),
            )

    def test_contract_queryset_is_tenant_scoped(self) -> None:
        create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="C-005",
            title="Visible contract",
            counterparty_name="Client LLC",
        )

        contracts = get_organization_contracts(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            list(contracts.values_list("title", flat=True)), ["Visible contract"]
        )
        with self.assertRaises(PermissionDenied):
            get_organization_contracts(
                user=self.other_user,
                organization=self.organization,
            )

    def test_contract_list_requires_active_organization(self) -> None:
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("contracts:list"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_contract_create_view_exposes_only_active_tenant_projects(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.get(reverse("contracts:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)

    def test_contract_create_view_creates_contract(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("contracts:create"),
            {
                "project": str(self.project.pk),
                "contract_number": "C-VIEW-001",
                "title": "View contract",
                "counterparty_name": "Client LLC",
                "status": ContractStatus.DRAFT,
                "contract_value": "1000.00",
                "signed_at": "",
                "start_date": "",
                "end_date": "",
                "notes": "",
            },
        )

        self.assertRedirects(response, reverse("contracts:list"))
        self.assertTrue(
            self.organization.contracts.filter(contract_number="C-VIEW-001").exists()
        )
