"""Native WS10 service-backed HTTP journeys, isolation and rendered fixtures."""

import re
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.services import create_project
from apps.treasury import operational_views
from apps.treasury.models import (
    AdvanceSettlement,
    BankStatementImport,
    ChequeInstrument,
    PaymentRequest,
    TreasuryAccount,
    TreasuryAdvance,
    TreasuryAdvanceReconciliationRun,
    TreasuryGLReconciliationRun,
    TreasuryMovement,
)
from apps.treasury.services import create_treasury_account
from apps.treasury.test_payment_retirement import (
    TreasuryPaymentReplacementTests as Fixtures,
)


class NativeTreasuryWorkspaceTests(TestCase):
    setUpTestData = classmethod(Fixtures.setUpTestData.__func__)
    movement = Fixtures.movement
    login = Fixtures.login

    def setUp(self):
        self.login()

    def url(self, operation, target=None):
        if target:
            return reverse("treasury:object_operation", args=[operation, target.pk])
        return reverse("treasury:operation", args=[operation])

    def post(self, operation, data=None, target=None):
        response = self.client.post(self.url(operation, target), data or {})
        self.assertEqual(response.status_code, 302, response.content.decode()[:2000])
        return response

    def request(self, **overrides):
        data = {
            "kind": "payment",
            "amount": "100",
            "purpose": "پرداخت آزمایشی",
            "party": str(self.party.pk),
            "project": str(self.project.pk),
            "idempotency_key": "NATIVE-REQUEST",
        }
        data.update(overrides)
        self.post("request_create", data)
        return PaymentRequest.objects.get(idempotency_key=data["idempotency_key"])

    def approved_request(self, **overrides):
        request = self.request(**overrides)
        self.post("request_submit", {"reason": "ارسال"}, request)
        review = self.client.get(self.url("request_decide", request))
        self.assertContains(review, request.purpose)
        self.assertContains(review, "مبلغ درخواست (ریال)")
        self.post(
            "request_decide",
            {"reason": "تأیید با خط‌مشی صریح", "approve": "yes"},
            request,
        )
        request.refresh_from_db()
        self.assertEqual(request.status, "approved")
        return request

    def fixture(self, name, response):
        path = Path("docs/governance/cep/evidence/CEP-060_UI")
        path.mkdir(exist_ok=True)
        html = response.content.decode()
        # Synthetic test pages only; retain no usable session/CSRF token.
        html = re.sub(
            r'(name="csrfmiddlewaretoken" value=")[^"]+', r"\1SYNTHETIC", html
        )
        (path / f"{name}.html").write_text(html, encoding="utf-8")

    def test_all_creation_forms_use_native_routes_persian_and_jalali(self):
        for name, op in operational_views.OPERATIONS.items():
            if op.model is None:
                with self.subTest(operation=name):
                    response = self.client.get(self.url(name))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'dir="rtl"')
                    self.assertNotContains(response, "/admin/")
        response = self.client.get(self.url("cheque_create"))
        self.assertContains(response, 'data-jalali-date="date"')
        self.fixture("form", response)
        self.fixture("statement_form", self.client.get(self.url("statement_preview")))

    def test_request_create_replay_approval_cash_link_and_release(self):
        request = self.approved_request()
        self.request()
        self.assertEqual(PaymentRequest.objects.count(), 1)
        form = self.client.get(reverse("treasury:movement_create"))
        self.assertNotContains(form, str(request.pk))
        movement = self.cash.post(self.movement(kind="disbursement"))
        self.post(
            "request_release",
            {"movement": str(movement.pk), "reason": "تخصیص پرداخت قطعی"},
            request,
        )
        request.refresh_from_db()
        self.assertEqual(request.released_movement_id, movement.pk)
        self.assertEqual(request.status, "released")
        response = self.client.get(reverse("treasury:operations"))
        self.assertContains(
            response, reverse("treasury:movement_detail", args=[movement.pk])
        )
        self.fixture("ready", response)
        detail = self.client.get(
            reverse("treasury:operational_detail", args=["request", request.pk])
        )
        self.assertContains(detail, request.purpose)
        self.fixture("detail", detail)

    def test_account_create_mapping_and_activation_preserve_sensitive_identity(self):
        serial = "TEST-PRIVATE-567890"
        self.post(
            "account_create",
            {
                "code": "NATIVE-BANK",
                "name": "حساب آزمایشی",
                "kind": "bank",
                "sensitive_identifier": serial,
            },
        )
        account = TreasuryAccount.objects.get(code="NATIVE-BANK")
        self.assertEqual(account.status, "draft")
        self.post(
            "account_mapping",
            {
                "cash_ledger_account": str(self.cash.cash_gl.pk),
                "clearing_ledger_account": str(self.cash.clearing_gl.pk),
                "effective_from": "1405/01/01",
                "reason": "نگاشت صریح",
            },
            account,
        )
        self.post(
            "account_status",
            {"to_status": "active", "reason": "فعال‌سازی با خط‌مشی مصوب"},
            account,
        )
        account.refresh_from_db()
        self.assertEqual(account.status, "active")
        self.assertNotContains(self.client.get(reverse("treasury:operations")), serial)

    def test_cheque_lifecycle_clear_and_bounce_use_atomic_domain_services(self):
        self.post(
            "cheque_create",
            {
                "direction": "incoming",
                "controlled_account": str(self.cash.bank.pk),
                "amount": "100",
                "due_date": "1405/07/28",
                "serial": "TEST-CHEQUE-09876",
                "party": str(self.party.pk),
            },
        )
        cheque = ChequeInstrument.objects.get()
        for state in ["received", "deposited", "presented"]:
            self.post(
                "cheque_status", {"to_status": state, "reason": "گردش مصوب چک"}, cheque
            )
        self.post(
            "cheque_clear",
            {
                "accounting_preparer": str(self.cash.accountant_membership.pk),
                "period": str(self.cash.period.pk),
                "clearing_date": "1405/07/28",
                "reason": "وصول",
            },
            cheque,
        )
        cheque.refresh_from_db()
        self.assertEqual(cheque.status, "cleared")
        self.assertEqual(cheque.cleared_movement.status, "posted")
        self.post(
            "cheque_bounce",
            {
                "requested_by": str(self.cash.accountant_membership.pk),
                "period": str(self.cash.period.pk),
                "accounting_date": "1405/07/28",
                "reason": "برگشت وصول",
            },
            cheque,
        )
        cheque.refresh_from_db()
        self.assertEqual(cheque.status, "bounced")
        self.assertTrue(cheque.transitions.exists())

    def test_advance_request_issue_settlement_reversal_and_reconciliation(self):
        request = self.approved_request(kind="vendor_advance")
        issue = self.cash.post(self.movement(kind="disbursement"))
        self.post(
            "request_release",
            {"movement": str(issue.pk), "reason": "پرداخت تنخواه"},
            request,
        )
        self.post("advance_open", target=request)
        advance = TreasuryAdvance.objects.get(request=request)
        receipt = self.cash.post(self.movement(idempotency_key="NATIVE-RETURN"))
        self.post(
            "advance_settle",
            {
                "receipt_movement": str(receipt.pk),
                "amount": "60",
                "idempotency_key": "NATIVE-SETTLE",
            },
            advance,
        )
        settlement = AdvanceSettlement.objects.get()
        self.post("settlement_submit", {"reason": "ارسال"}, settlement)
        self.post(
            "settlement_decide", {"approve": "yes", "reason": "تأیید"}, settlement
        )
        advance.refresh_from_db()
        self.assertEqual(advance.status, "partially_settled")
        self.post(
            "settlement_reverse",
            {
                "requested_by": str(self.cash.accountant_membership.pk),
                "period": str(self.cash.period.pk),
                "accounting_date": "1405/07/28",
                "reason": "برگشت تسویه",
            },
            settlement,
        )
        self.post(
            "advance_reconcile",
            {"cutoff_date": "1405/07/28", "idempotency_key": "NATIVE-ADV-RECON"},
        )
        self.post(
            "advance_reverse",
            {
                "requested_by": str(self.cash.accountant_membership.pk),
                "period": str(self.cash.period.pk),
                "accounting_date": "1405/07/28",
                "reason": "برگشت پرداخت تنخواه",
            },
            advance,
        )
        advance.refresh_from_db()
        self.assertEqual(advance.status, "reversed")
        self.post("gl_reconcile", {"cutoff_date": "1405/07/28"})
        self.assertEqual(
            TreasuryGLReconciliationRun.objects.latest("created_at").exceptions, []
        )
        self.assertEqual(
            TreasuryAdvanceReconciliationRun.objects.latest("created_at").exceptions, []
        )
        response = self.client.get(reverse("treasury:operations"))
        self.assertContains(response, "تطبیق‌های نگهداری‌شده تنخواه")
        self.fixture("advance_recon", response)

    def test_transfer_uses_native_two_leg_draft_without_posting(self):
        destination = self.cash._bank(
            "NATIVE-DEST", "TEST-DEST-1234", self.cash.cash_gl
        )
        self.post(
            "transfer",
            {
                "source_account": str(self.cash.bank.pk),
                "destination_account": str(destination.pk),
                "project": str(self.project.pk),
                "movement_date": "1405/07/28",
                "amount": "20",
                "description": "انتقال صریح",
                "idempotency_key": "NATIVE-TRANSFER",
            },
        )
        movement = TreasuryMovement.objects.get(idempotency_key="NATIVE-TRANSFER")
        self.assertEqual(movement.kind, "transfer")
        self.assertEqual(movement.status, "draft")
        self.assertEqual(movement.legs.count(), 2)
        self.assertIsNone(movement.journal_id)

    def test_cancel_reject_and_payload_conflict_preserve_native_history(self):
        cancelled = self.request(idempotency_key="NATIVE-CANCEL")
        self.post("request_cancel", {"reason": "لغو درخواست"}, cancelled)
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, "cancelled")
        rejected = self.request(idempotency_key="NATIVE-REJECT")
        self.post("request_submit", {"reason": "ارسال"}, rejected)
        self.post("request_decide", {"approve": "no", "reason": "رد درخواست"}, rejected)
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, "rejected")
        response = self.client.post(
            self.url("request_create"),
            {
                "kind": "payment",
                "amount": "101",
                "purpose": "DIFFERENT",
                "party": str(self.party.pk),
                "idempotency_key": "NATIVE-REJECT",
            },
        )
        self.assertEqual(response.status_code, 200)
        rejected.refresh_from_db()
        self.assertEqual(str(rejected.amount), "100.000000")
        self.assertEqual(PaymentRequest.objects.count(), 2)

    def test_statement_preview_accept_and_bad_file_are_bounded_without_cash_effect(
        self,
    ):
        csv = b"transaction_date,direction,amount,provider_row_id,reference\n2026-10-20,in,100,ROW-1,TEST\n"
        data = {
            "account": str(self.cash.bank.pk),
            "provider_code": "SYNTHETIC",
            "period_start": "1405/07/28",
            "period_end": "1405/07/28",
            "idempotency_key": "NATIVE-STATEMENT",
            "file": SimpleUploadedFile("test.csv", csv, content_type="text/csv"),
        }
        self.post("statement_preview", data)
        statement = BankStatementImport.objects.get()
        self.assertEqual(statement.row_count, 1)
        self.post("statement_accept", {"reason": "پذیرش منبع صریح"}, statement)
        statement.refresh_from_db()
        self.assertEqual(statement.status, "accepted")
        self.assertEqual(TreasuryMovement.objects.count(), 0)
        data["file"] = SimpleUploadedFile("bad.csv", b"wrong,headers\n")
        response = self.client.post(self.url("statement_preview"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertEqual(BankStatementImport.objects.count(), 1)
        for value in ["1e999999999", "NaN", "0.1234567"]:
            with self.subTest(invalid_amount=value):
                data["file"] = SimpleUploadedFile(
                    "invalid.csv",
                    (
                        "transaction_date,direction,amount,provider_row_id,reference\n2026-10-20,in,"
                        + value
                        + ",BAD,TEST\n"
                    ).encode(),
                )
                denied = self.client.post(self.url("statement_preview"), data)
                self.assertEqual(denied.status_code, 200)
                self.assertEqual(BankStatementImport.objects.count(), 1)

    def test_empty_validation_and_no_get_mutation_have_explicit_states(self):
        response = self.client.get(reverse("treasury:operations"))
        self.assertContains(response, "رکورد مجاز وجود ندارد")
        self.fixture("empty", response)
        response = self.client.post(self.url("request_create"), {"amount": "-1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.fixture("error", response)
        request = self.request()
        self.assertEqual(
            self.client.get(self.url("request_submit", request)).status_code, 200
        )
        request.refresh_from_db()
        self.assertEqual(request.status, "draft")

    def test_csrf_cross_tenant_choice_and_direct_url_are_enforced(self):
        strict = self.login(Client(enforce_csrf_checks=True))
        self.assertEqual(strict.post(self.url("request_create"), {}).status_code, 403)
        other_owner = User.objects.create_user(username="cep060-other")
        other = create_organization_with_owner(
            owner=other_owner, name="SECRET", slug="cep060-other"
        )
        project = create_project(
            organization=other, actor=other_owner, code="SECRET", name="SECRET"
        )
        other_account = create_treasury_account(
            organization=other,
            actor=other_owner,
            code="SECRET",
            name="SECRET",
            kind="cash",
            custodian=other.memberships.get(user=other_owner),
        )
        direct = self.client.get(self.url("account_status", other_account))
        self.assertEqual(direct.status_code, 404)
        self.assertNotContains(direct, "SECRET", status_code=404)
        self.assertEqual(
            self.client.get(
                reverse(
                    "treasury:operational_detail", args=["account", other_account.pk]
                )
            ).status_code,
            404,
        )
        response = self.client.post(
            self.url("request_create"),
            {
                "kind": "payment",
                "amount": "100",
                "purpose": "test",
                "party": str(self.party.pk),
                "project": str(project.pk),
                "idempotency_key": "BAD-TENANT",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET")
        request = self.request()
        self.organization.memberships.filter(user=self.owner).update(status="removed")
        self.assertIn(
            self.client.post(
                self.url("request_submit", request), {"reason": "DENIED"}
            ).status_code,
            [302, 403],
        )
        request.refresh_from_db()
        self.assertEqual(request.status, "draft")

    def test_view_only_role_cannot_invoke_mutations_or_unknown_services(self):
        user = User.objects.create_user(username="cep060-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="cep060-reader", name="خواننده"
        )
        role.permissions.add(BusinessPermission.objects.get(code=P.TREASURY_VIEW))
        membership = self.organization.memberships.create(
            user=user, role_definition=role, status="active"
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit synthetic UI role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit synthetic scope",
        )
        self.client.force_login(user)
        response = self.client.post(self.url("account_create"), {"code": "DENIED"})
        self.assertEqual(response.status_code, 403)
        self.fixture("unauthorized", response)
        self.assertFalse(TreasuryAccount.objects.filter(code="DENIED").exists())
        self.assertEqual(
            self.client.get(self.url("arbitrary_service")).status_code, 404
        )

    def test_project_scope_does_not_expose_global_accounts_or_unrelated_requests(self):
        allowed = self.request()
        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="SECOND",
            name="Hidden project",
        )
        hidden = self.request(project=str(other_project.pk), idempotency_key="HIDDEN")
        user = User.objects.create_user(username="cep060-project-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep060-project-reader",
            name="خواننده پروژه",
        )
        role.permissions.add(BusinessPermission.objects.get(code=P.TREASURY_VIEW))
        membership = self.organization.memberships.create(
            user=user, role_definition=role, status="active"
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit scoped fixture",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="Explicit project scope",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("treasury:operations"))
        # Registered Treasury read authority requires organization scope. A
        # project title/grant must not expand it into organization cash access.
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, str(allowed.pk), status_code=403)
        self.assertNotContains(response, str(hidden.pk), status_code=403)
        root = self.client.get(reverse("treasury:workbench"))
        self.assertEqual(root.status_code, 403)
        self.assertNotContains(root, self.cash.bank.name, status_code=403)
