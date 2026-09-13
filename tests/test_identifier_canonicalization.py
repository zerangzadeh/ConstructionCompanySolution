from datetime import date
from decimal import Decimal

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.forms import UserLoginForm
from apps.accounts.models import User
from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.contracts.services import create_contract
from apps.estimates.forms import EstimateForm
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate
from apps.organizations.forms import OrganizationForm
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.organizations.services import create_organization_with_owner
from apps.payments.forms import PaymentForm
from apps.payments.models import Payment, PaymentDirection, PaymentMethod
from apps.payments.services import create_payment
from apps.projects.forms import ProjectForm, ProjectPhaseForm, ProjectSiteForm
from apps.projects.models import (
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
    ProjectStatus,
)
from apps.projects.services import (
    create_project,
    create_project_phase,
    create_project_site,
)


class IdentifierCanonicalizationTests(TestCase):
    def setUp(self) -> None:
        self.password = "test-password"
        self.business_date = date(2026, 9, 3)
        self.owner = User.objects.create_user(
            username="identifier-owner",
            password=self.password,
        )
        self.organization = Organization.objects.create(
            name="Identifier Company",
            slug="identifier-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="BASE-PROJECT",
            name="Base project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="BASE-SITE",
            name="Base site",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=self.site,
            code="BASE-PHASE",
            name="Base phase",
            status=ProjectPhaseStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def test_username_is_canonical_for_creation_authentication_and_lookup(self) -> None:
        user = User.objects.create_user(
            username="  Mixed.User  ",
            password=self.password,
        )

        self.assertEqual(user.username, "mixed.user")
        self.assertEqual(User.objects.get_by_natural_key(" MIXED.USER "), user)
        self.assertEqual(
            authenticate(username="  MIXED.USER ", password=self.password),
            user,
        )

        login_form = UserLoginForm(
            data={"username": " MIXED.USER ", "password": self.password}
        )
        self.assertTrue(login_form.is_valid(), login_form.errors)
        self.assertEqual(login_form.cleaned_data["username"], "mixed.user")

        direct_user = User.objects.create(username="  Direct.User  ")
        self.assertEqual(direct_user.username, "direct.user")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username=" mixed.USER ")

    def test_organization_slug_is_canonical_across_service_form_and_direct_save(
        self,
    ) -> None:
        organization = create_organization_with_owner(
            owner=self.owner,
            name="Mixed Organization",
            slug="  Mixed-Organization  ",
        )
        self.assertEqual(organization.slug, "mixed-organization")
        self.assertEqual(
            Organization.objects.get(slug="mixed-organization"),
            organization,
        )

        form = OrganizationForm(
            data={
                "name": "Form Organization",
                "legal_name": "",
                "slug": "  Form-Organization  ",
                "timezone": "UTC",
                "currency": "USD",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["slug"], "form-organization")

        duplicate_form = OrganizationForm(
            data={
                "name": "Duplicate Organization",
                "legal_name": "",
                "slug": " MIXED-ORGANIZATION ",
                "timezone": "UTC",
                "currency": "USD",
            }
        )
        self.assertFalse(duplicate_form.is_valid())
        self.assertIn("slug", duplicate_form.errors)

        direct = Organization.objects.create(
            name="Direct Organization",
            slug="  Direct-Organization  ",
        )
        self.assertEqual(direct.slug, "direct-organization")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Organization.objects.create(
                name="Semantic duplicate",
                slug=" MIXED-ORGANIZATION ",
            )

    def test_project_site_and_phase_codes_are_canonical_and_semantically_unique(
        self,
    ) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="  p-mixed  ",
            name="Mixed project",
        )
        self.assertEqual(project.code, "P-MIXED")
        self.assertEqual(
            Project.objects.get(organization=self.organization, code="P-MIXED"),
            project,
        )
        with self.assertRaises(IntegrityError):
            create_project(
                organization=self.organization,
                actor=self.owner,
                code=" p-MIXED ",
                name="Semantic duplicate",
            )

        site = create_project_site(
            organization=self.organization,
            project=project,
            actor=self.owner,
            code=" site-mixed ",
            name="Mixed site",
        )
        self.assertEqual(site.code, "SITE-MIXED")
        self.assertEqual(
            ProjectSite.objects.get(
                organization=self.organization,
                project=project,
                code="SITE-MIXED",
            ),
            site,
        )
        with self.assertRaisesMessage(ValueError, "از قبل"):
            create_project_site(
                organization=self.organization,
                project=project,
                actor=self.owner,
                code=" SITE-mixed ",
                name="Semantic duplicate",
            )

        phase = create_project_phase(
            organization=self.organization,
            site=site,
            actor=self.owner,
            code=" phase-mixed ",
            name="Mixed phase",
        )
        self.assertEqual(phase.code, "PHASE-MIXED")
        self.assertEqual(
            ProjectPhase.objects.get(
                organization=self.organization,
                site=site,
                code="PHASE-MIXED",
            ),
            phase,
        )
        with self.assertRaisesMessage(ValueError, "از قبل"):
            create_project_phase(
                organization=self.organization,
                site=site,
                actor=self.owner,
                code=" PHASE-mixed ",
                name="Semantic duplicate",
            )

        direct = Project.objects.create(
            organization=self.organization,
            code="  direct-project  ",
            name="Direct project",
        )
        self.assertEqual(direct.code, "DIRECT-PROJECT")

        admin_candidate = Project(
            organization=self.organization,
            code=" base-project ",
            name="Admin candidate",
        )
        with self.assertRaises(ValidationError):
            admin_candidate.full_clean()
        self.assertEqual(admin_candidate.code, "BASE-PROJECT")

    def test_contract_estimate_and_payment_numbers_are_canonical_and_lookup_safe(
        self,
    ) -> None:
        contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="  con-mixed  ",
            title="Mixed contract",
            counterparty_name="Client",
        )
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="  est-mixed  ",
            title="Mixed estimate",
        )
        payment = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="  pay-mixed  ",
            direction=PaymentDirection.RECEIPT,
            amount=Decimal("100.00"),
            paid_on=self.business_date,
            counterparty_name="Client",
        )

        self.assertEqual(contract.contract_number, "CON-MIXED")
        self.assertEqual(estimate.estimate_number, "EST-MIXED")
        self.assertEqual(payment.payment_number, "PAY-MIXED")
        self.assertEqual(
            Contract.objects.get(
                organization=self.organization,
                contract_number="CON-MIXED",
            ),
            contract,
        )
        self.assertEqual(
            Estimate.objects.get(
                organization=self.organization,
                estimate_number="EST-MIXED",
            ),
            estimate,
        )
        self.assertEqual(
            Payment.objects.get(
                organization=self.organization,
                payment_number="PAY-MIXED",
            ),
            payment,
        )

        with self.assertRaisesMessage(ValueError, "از قبل"):
            create_contract(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                contract_number=" con-MIXED ",
                title="Duplicate contract",
                counterparty_name="Client",
            )
        with self.assertRaisesMessage(ValueError, "از قبل"):
            create_estimate(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                estimate_number=" est-MIXED ",
                title="Duplicate estimate",
            )
        with self.assertRaisesMessage(ValueError, "از قبل"):
            create_payment(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                payment_number=" pay-MIXED ",
                direction=PaymentDirection.RECEIPT,
                amount=Decimal("1.00"),
                paid_on=self.business_date,
                counterparty_name="Client",
            )

        direct_contract = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number=" direct-contract ",
            title="Direct contract",
            counterparty_name="Client",
        )
        direct_estimate = Estimate.objects.create(
            organization=self.organization,
            project=self.project,
            estimate_number=" direct-estimate ",
            title="Direct estimate",
        )
        direct_payment = Payment.objects.create(
            organization=self.organization,
            project=self.project,
            payment_number=" direct-payment ",
            direction=PaymentDirection.RECEIPT,
            amount=Decimal("1.00"),
            paid_on=self.business_date,
            counterparty_name="Client",
        )
        self.assertEqual(direct_contract.contract_number, "DIRECT-CONTRACT")
        self.assertEqual(direct_estimate.estimate_number, "DIRECT-ESTIMATE")
        self.assertEqual(direct_payment.payment_number, "DIRECT-PAYMENT")

    def test_identifier_forms_return_canonical_codes_and_numbers(self) -> None:
        project_form = ProjectForm(
            data={
                "code": " form-project ",
                "name": "Form project",
                "description": "",
                "status": ProjectStatus.PLANNING,
                "start_date": "",
                "end_date": "",
                "budget": "0.00",
            }
        )
        site_form = ProjectSiteForm(
            data={"code": " form-site ", "name": "Form site", "address": ""}
        )
        phase_form = ProjectPhaseForm(
            data={
                "code": " form-phase ",
                "name": "Form phase",
                "status": ProjectPhaseStatus.PLANNING,
                "planned_start_date": "",
                "planned_end_date": "",
            }
        )
        contract_form = ContractForm(
            data={
                "project": self.project.pk,
                "contract_number": " form-contract ",
                "title": "Form contract",
                "counterparty_name": "Client",
                "status": "draft",
                "contract_value": "0.00",
                "signed_at": "",
                "start_date": "",
                "end_date": "",
                "notes": "",
            },
            organization=self.organization,
        )
        estimate_form = EstimateForm(
            data={
                "project": self.project.pk,
                "contract": "",
                "phase": "",
                "estimate_number": " form-estimate ",
                "title": "Form estimate",
                "notes": "",
            },
            organization=self.organization,
        )
        payment_form = PaymentForm(
            data={
                "project": self.project.pk,
                "contract": "",
                "phase": "",
                "payment_number": " form-payment ",
                "direction": PaymentDirection.RECEIPT,
                "amount": "1.00",
                "paid_on": self.business_date.isoformat(),
                "method": PaymentMethod.BANK_TRANSFER,
                "counterparty_name": "Client",
                "reference": "",
                "notes": "",
            },
            organization=self.organization,
        )

        forms_and_values = (
            (project_form, "code", "FORM-PROJECT"),
            (site_form, "code", "FORM-SITE"),
            (phase_form, "code", "FORM-PHASE"),
            (contract_form, "contract_number", "FORM-CONTRACT"),
            (estimate_form, "estimate_number", "FORM-ESTIMATE"),
            (payment_form, "payment_number", "FORM-PAYMENT"),
        )
        for form, field_name, expected in forms_and_values:
            with self.subTest(form=form.__class__.__name__):
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data[field_name], expected)
