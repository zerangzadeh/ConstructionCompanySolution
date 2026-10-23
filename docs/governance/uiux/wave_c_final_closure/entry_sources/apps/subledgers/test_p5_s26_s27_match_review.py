from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.inventory.models import StockTransaction
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationRole,
)
from apps.organizations.services import set_active_organization
from apps.procurement.services import (
    add_goods_receipt_item,
    create_goods_receipt,
    post_goods_receipt,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.subledgers.models import Obligation, SupplierInvoiceLineKind
from apps.subledgers.services import (
    approve_match_tolerance_policy,
    decide_supplier_invoice,
    prepare_match_tolerance_policy,
    prepare_supplier_invoice,
    run_supplier_invoice_match,
    submit_supplier_invoice,
)


class P5S26S27MatchReviewTests(ProcurementFixtureMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.approver = User.objects.create_user(username="p5-s27-approver")
        self.organization.memberships.create(
            user=self.approver,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.match = self._retained_match()

    def _retained_match(self):
        order, item = self.create_issued_order(quantity=Decimal("5.0000"))
        order.refresh_from_db()
        receipt = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="P5-S27-GR",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
            purchase_order_item=item,
            quantity=Decimal("5.0000"),
        )
        post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
        )
        policy = prepare_match_tolerance_policy(
            organization=self.organization,
            actor=self.owner,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            quantity_tolerance_bps=0,
            unit_price_tolerance_bps=0,
            reason="P5-S27 review policy",
        )
        approve_match_tolerance_policy(
            organization=self.organization,
            actor=self.approver,
            policy=policy,
        )
        invoice = prepare_supplier_invoice(
            organization=self.organization,
            actor=self.owner,
            supplier=self.supplier,
            project=self.project,
            invoice_number="P5-S27-INV",
            invoice_date=date(2026, 9, 10),
            due_date=date(2026, 10, 10),
            lines=[
                {
                    "kind": SupplierInvoiceLineKind.GOODS,
                    "purchase_order_version_line": order.current_version.lines.get(),
                    "quantity": Decimal("5.0000"),
                    "unit_price": Decimal("12.34"),
                }
            ],
            idempotency_key="p5-s27-invoice",
        )
        submit_supplier_invoice(
            organization=self.organization,
            actor=self.owner,
            invoice_version=invoice,
        )
        decide_supplier_invoice(
            organization=self.organization,
            actor=self.approver,
            invoice_version=invoice,
            approve=True,
            reason="Independent invoice approval",
        )
        return run_supplier_invoice_match(
            organization=self.organization,
            actor=self.owner,
            invoice_version=invoice,
            idempotency_key="p5-s27-match",
        )

    def _client(self, user, organization):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        set_active_organization(client.session, organization)
        client.session.save()
        return client

    def test_review_is_permissioned_read_only_and_preserves_downstream_state(self):
        client = self._client(self.owner, self.organization)
        counts = (
            Obligation.objects.count(),
            JournalEntry.objects.count(),
            StockTransaction.objects.count(),
        )
        response = client.get(
            reverse("subledgers:supplier_invoice_match_detail", args=[self.match.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "P5-S27-INV")
        self.assertContains(response, "هیچ کنترل رفع اجباری")
        self.assertEqual(
            counts,
            (
                Obligation.objects.count(),
                JournalEntry.objects.count(),
                StockTransaction.objects.count(),
            ),
        )
        self.assertEqual(
            client.post(reverse("subledgers:supplier_invoice_match_review")).status_code,
            403,
        )
        with self.assertRaises(ValidationError):
            self.match.save()

    def test_tenant_permission_and_project_scope_hide_match_evidence(self):
        other_client = self._client(self.outsider, self.other_organization)
        self.assertEqual(
            other_client.get(
                reverse(
                    "subledgers:supplier_invoice_match_detail",
                    args=[self.match.pk],
                )
            ).status_code,
            404,
        )

        viewer = User.objects.create_user(username="p5-s27-viewer")
        no_match_role = OrganizationRole.objects.create(
            organization=self.organization,
            code="p5_s27_no_match",
            name="P5 S27 no match access",
        )
        self.organization.memberships.create(
            user=viewer,
            role=no_match_role.code,
            role_definition=no_match_role,
            status=MembershipStatus.ACTIVE,
        )
        self.assertEqual(
            self._client(viewer, self.organization)
            .get(reverse("subledgers:supplier_invoice_match_review"))
            .status_code,
            403,
        )

        scoped = User.objects.create_user(username="p5-s27-scoped")
        membership = self.organization.memberships.create(
            user=scoped,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.other_project,
            reason="P5-S27 unrelated project only",
        )
        scoped_client = self._client(scoped, self.organization)
        list_response = scoped_client.get(
            reverse("subledgers:supplier_invoice_match_review")
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertNotContains(list_response, "P5-S27-INV")
        self.assertEqual(
            scoped_client.get(
                reverse(
                    "subledgers:supplier_invoice_match_detail",
                    args=[self.match.pk],
                )
            ).status_code,
            404,
        )
