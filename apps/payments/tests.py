from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.contracts.services import create_contract
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.payments.models import Payment, PaymentDirection, PaymentStatus
from apps.payments.services import (
    create_payment,
    get_organization_payments,
    void_payment,
)
from apps.projects.services import (
    create_project,
    create_project_phase,
    create_project_site,
)


class PaymentServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="payment-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-payment-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Payment Company",
            slug="payment-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Payment Company",
            slug="other-payment-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-PAYMENT",
            name="Payment project",
        )
        self.site = create_project_site(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="SITE-PAYMENT",
            name="Payment worksite",
        )
        self.phase = create_project_phase(
            organization=self.organization,
            site=self.site,
            actor=self.owner,
            code="PH-PAYMENT",
            name="Payment phase",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="C-PAYMENT",
            title="Payment contract",
            counterparty_name="Client LLC",
        )

    def _create_payment(self, **overrides):
        data = {
            "organization": self.organization,
            "project": self.project,
            "actor": self.owner,
            "payment_number": "PAY-001",
            "direction": PaymentDirection.RECEIPT,
            "amount": Decimal("1250.75"),
            "paid_on": date(2026, 9, 3),
            "counterparty_name": "Client LLC",
        }
        data.update(overrides)
        return create_payment(**data)

    def test_create_payment_records_decimal_amount_and_audit(self) -> None:
        payment = self._create_payment(contract=self.contract, phase=self.phase)

        self.assertEqual(payment.amount, Decimal("1250.75"))
        self.assertEqual(payment.status, PaymentStatus.POSTED)
        event = AuditEvent.objects.get(
            action=AuditAction.PAYMENT_RECORDED,
            entity_id=str(payment.pk),
        )
        self.assertEqual(event.metadata["contract_id"], str(self.contract.pk))
        self.assertEqual(event.metadata["phase_id"], str(self.phase.pk))

    def test_payment_rejects_non_positive_amount(self) -> None:
        with self.assertRaisesMessage(ValueError, "Payment amount must be positive."):
            self._create_payment(amount=Decimal("0.00"))

    def test_payment_rejects_cross_tenant_project(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-PAYMENT",
            name="Other payment project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            self._create_payment(project=other_project)

    def test_payment_rejects_phase_from_another_project(self) -> None:
        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-PAYMENT-OTHER",
            name="Other payment project",
        )
        other_site = create_project_site(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            code="SITE-PAYMENT-OTHER",
            name="Other payment worksite",
        )
        other_phase = create_project_phase(
            organization=self.organization,
            site=other_site,
            actor=self.owner,
            code="PH-PAYMENT-OTHER",
            name="Other payment phase",
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "The project phase does not belong to this project.",
        ):
            self._create_payment(phase=other_phase)

    def test_payment_queryset_is_tenant_scoped(self) -> None:
        self._create_payment()

        payments = get_organization_payments(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            list(payments.values_list("payment_number", flat=True)),
            ["PAY-001"],
        )
        with self.assertRaises(PermissionDenied):
            get_organization_payments(
                user=self.other_user,
                organization=self.organization,
            )

    def test_void_payment_preserves_amount_and_records_audit_event(self) -> None:
        payment = self._create_payment()

        void_payment(payment=payment, actor=self.owner, reason="Duplicate entry")

        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.VOID)
        self.assertEqual(payment.amount, Decimal("1250.75"))
        self.assertEqual(payment.void_reason, "Duplicate entry")
        self.assertEqual(payment.voided_by, self.owner)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PAYMENT_VOIDED,
                entity_id=str(payment.pk),
            ).exists()
        )
        with self.assertRaisesMessage(
            ValueError,
            "Only posted payments can be voided.",
        ):
            void_payment(payment=payment, actor=self.owner, reason="Repeated request")

    def test_member_cannot_create_or_void_payment(self) -> None:
        member = User.objects.create_user(
            username="payment-member",
            password="test-password",
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        payment = self._create_payment()

        with self.assertRaises(PermissionDenied):
            self._create_payment(payment_number="PAY-MEMBER", actor=member)
        with self.assertRaises(PermissionDenied):
            void_payment(payment=payment, actor=member, reason="Unauthorized")

    def test_payment_create_view_limits_project_choices_and_posts_payment(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.other_organization.projects.create(
            code="P-PAYMENT-HIDDEN",
            name="Hidden payment project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        response = self.client.get(reverse("payments:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, "Hidden payment project")

        response = self.client.post(
            reverse("payments:create"),
            {
                "project": str(self.project.pk),
                "contract": str(self.contract.pk),
                "phase": str(self.phase.pk),
                "payment_number": "PAY-VIEW-001",
                "direction": PaymentDirection.DISBURSEMENT,
                "amount": "75.50",
                "paid_on": "2026-09-03",
                "method": "bank_transfer",
                "counterparty_name": "Supplier LLC",
                "reference": "TX-001",
                "notes": "",
            },
        )

        self.assertRedirects(response, reverse("payments:list"))
        self.assertTrue(
            self.organization.payments.filter(
                payment_number="PAY-VIEW-001",
            ).exists()
        )

    def test_payment_list_requires_active_organization(self) -> None:
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("payments:list"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_payment_detail_and_void_reject_cross_tenant_uuid(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-PRIVATE",
            name="Other private project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        other_payment = Payment.objects.create(
            organization=self.other_organization,
            project=other_project,
            payment_number="PAY-OTHER-PRIVATE",
            direction=PaymentDirection.DISBURSEMENT,
            amount=Decimal("99.00"),
            paid_on=date(2026, 9, 3),
            counterparty_name="Other supplier",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        detail_response = self.client.get(
            reverse("payments:detail", kwargs={"payment_id": other_payment.pk})
        )
        void_response = self.client.post(
            reverse("payments:void", kwargs={"payment_id": other_payment.pk}),
            {"reason": "Unauthorized attempt"},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(void_response.status_code, 404)
        other_payment.refresh_from_db()
        self.assertEqual(other_payment.status, PaymentStatus.POSTED)

    def test_payment_void_view_rejects_a_repeat_void_request(self) -> None:
        payment = self._create_payment()
        void_payment(payment=payment, actor=self.owner, reason="Duplicate entry")
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("payments:void", kwargs={"payment_id": payment.pk}),
            {"reason": "Repeated request"},
        )

        self.assertEqual(response.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.VOID)
