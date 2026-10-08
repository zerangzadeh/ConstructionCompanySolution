from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Sum
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import AccountType, JournalStatus
from apps.accounting.services import (
    create_account,
    create_fiscal_period,
    create_fiscal_year,
)
from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_INITIAL_POLICY_PARAMETERS,
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    TREASURY_SELF_APPROVAL_POLICY_CODE,
    get_platform_policy_spec,
)
from apps.organizations.services import create_organization_with_owner
from apps.parties.models import BusinessParty, PartyKind
from apps.treasury.models import (
    AdvanceSettlement,
    AdvanceSettlementStatus,
    BankReconciliationRun,
    BankStatementImport,
    BankStatementLine,
    ChequeDirection,
    ChequeStatus,
    TreasuryAccount,
    TreasuryAccountKind,
    TreasuryAccountStatus,
    TreasuryAdvanceStatus,
    TreasuryGLReconciliationReview,
    TreasuryMovementClearing,
    TreasuryMovementStatus,
)
from apps.treasury.services import (
    approve_and_post_movement,
    bounce_cleared_cheque,
    clear_cheque,
    create_account_mapping_version,
    create_advance_settlement,
    create_cheque,
    create_movement,
    create_payment_request,
    create_treasury_account,
    decide_advance_settlement,
    decide_payment_request,
    masked_account_identifier,
    open_advance,
    release_payment_request,
    reverse_advance_settlement,
    review_treasury_gl_reconciliation,
    run_advance_reconciliation,
    run_treasury_gl_reconciliation,
    submit_advance_settlement,
    submit_movement,
    submit_payment_request,
    transition_cheque,
    transition_treasury_account,
    verify_treasury_gl_reconciliation_review,
)
from apps.treasury.statement_services import (
    StatementRowInput,
    accept_statement_import,
    confirm_statement_match,
    generate_statement_match_suggestions,
    preview_statement_import,
    reverse_statement_clearing,
    run_bank_reconciliation,
)
from apps.workforce.models import Employee


class TreasuryFoundationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p3-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="P3 Tenant", slug="p3-tenant"
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.accountant = self._member("p3-accountant", MembershipRole.ACCOUNTANT)
        self.accountant_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.accountant
        )
        self._activate_policy(
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_INITIAL_POLICY_PARAMETERS[
                ACCOUNTING_MONEY_PRECISION_POLICY_CODE
            ],
        )
        self._activate_policy(
            ACCOUNTING_ROUNDING_POLICY_CODE,
            ACCOUNTING_INITIAL_POLICY_PARAMETERS[ACCOUNTING_ROUNDING_POLICY_CODE],
        )
        self._activate_policy(
            TREASURY_SELF_APPROVAL_POLICY_CODE,
            {"allow_self_approval": True},
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-P3",
            name="سال مالی خزانه",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        self.period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=year,
            number=1,
            name="دوره خزانه",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.cash_gl = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1101",
            name="بانک",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        self.cash_gl_2 = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1102",
            name="بانک دوم",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        self.clearing_gl = create_account(
            organization=self.organization,
            actor=self.owner,
            code="2199",
            name="وجوه در راه",
            account_type=AccountType.LIABILITY,
            is_posting=True,
        )
        self.bank = self._bank("BANK-1", "IR0000001234", self.cash_gl)

    def _member(self, username: str, role_code: str) -> User:
        user = User.objects.create_user(username=username, password="x")
        role = OrganizationRole.objects.get(code=role_code, organization__isnull=True)
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=role_code,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="P3 test assignment",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P3 test scope",
        )
        return user

    def _activate_policy(self, code: str, parameters: dict[str, object]) -> None:
        spec = get_platform_policy_spec(code)
        policy = PlatformPolicy.objects.create(
            code=code,
            name=spec.name,
            category=spec.category,
            sensitivity=spec.sensitivity,
            tenant_selectable=True,
            requires_source_provenance=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        now = timezone.now()
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=1,
            parameters=parameters,
            effective_from=timezone.localdate(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            created_by=self.owner,
            published_by=self.owner,
            published_at=now,
            reason="P3 test policy",
        )
        TenantPolicySelection.objects.create(
            organization=self.organization,
            policy=policy,
            policy_version=version,
            status=TenantPolicySelectionStatus.ACTIVE,
            approved_by=self.owner_membership,
            approved_at=now,
            applied_by=self.owner_membership,
            applied_at=now,
            reason="P3 test activation",
        )

    def _bank(self, code: str, identifier: str, cash_gl):
        account = create_treasury_account(
            organization=self.organization,
            actor=self.owner,
            code=code,
            name=code,
            kind=TreasuryAccountKind.BANK,
            sensitive_identifier=identifier,
        )
        create_account_mapping_version(
            organization=self.organization,
            actor=self.owner,
            account=account,
            cash_ledger_account=cash_gl,
            clearing_ledger_account=self.clearing_gl,
            effective_from=date(2026, 1, 1),
            reason="نگاشت مصوب آزمون",
        )
        return transition_treasury_account(
            organization=self.organization,
            actor=self.owner,
            account=account,
            to_status=TreasuryAccountStatus.ACTIVE,
            reason="فعال‌سازی آزمون",
        )

    def _replace_treasury_approval_policy(self, *, allow: bool) -> None:
        policy = PlatformPolicy.objects.get(code=TREASURY_SELF_APPROVAL_POLICY_CODE)
        now = timezone.now()
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=2,
            parameters={"allow_self_approval": allow},
            effective_from=timezone.localdate(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            created_by=self.owner,
            published_by=self.owner,
            published_at=now,
            reason="P3 replacement test policy",
        )
        TenantPolicySelection.objects.filter(
            organization=self.organization,
            policy=policy,
            status=TenantPolicySelectionStatus.ACTIVE,
        ).update(status=TenantPolicySelectionStatus.SUPERSEDED)
        TenantPolicySelection.objects.create(
            organization=self.organization,
            policy=policy,
            policy_version=version,
            status=TenantPolicySelectionStatus.ACTIVE,
            approved_by=self.owner_membership,
            approved_at=now,
            applied_by=self.owner_membership,
            applied_at=now,
            reason="P3 replacement test activation",
        )

    def _post(self, movement):
        movement = submit_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            reason="ارسال آزمون",
        )
        return approve_and_post_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            accounting_preparer=self.accountant_membership,
            period=self.period,
            reason="تأیید و ثبت آزمون",
        )

    def test_account_masks_identifier_and_rejects_cross_tenant_access(self) -> None:
        self.assertEqual(
            masked_account_identifier(
                organization=self.organization, actor=self.owner, account=self.bank
            ),
            "••••1234",
        )
        other_owner = User.objects.create_user(username="p3-other", password="x")
        other = create_organization_with_owner(
            owner=other_owner, name="Other", slug="p3-other"
        )
        other_membership = OrganizationMembership.objects.get(
            organization=other, user=other_owner
        )
        other_account = create_treasury_account(
            organization=other,
            actor=other_owner,
            code="OTHER",
            name="Other",
            kind=TreasuryAccountKind.BANK,
            sensitive_identifier="99991234",
        )
        self.assertEqual(other_account.created_by, other_membership)
        with self.assertRaises(PermissionDenied):
            masked_account_identifier(
                organization=self.organization,
                actor=self.owner,
                account=other_account,
            )

    def test_direct_receipt_posts_once_with_exact_evidence_and_reconciles(self) -> None:
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="receipt",
            movement_date=date(2026, 6, 1),
            amount=Decimal(100),
            description="دریافت مستقیم",
            idempotency_key="receipt-1",
            account=self.bank,
        )
        self.assertEqual(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 6, 1),
                amount=Decimal(100),
                description="دریافت مستقیم",
                idempotency_key="receipt-1",
                account=self.bank,
            ).pk,
            movement.pk,
        )
        with self.assertRaises(ValidationError):
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 6, 1),
                amount=Decimal(101),
                description="دریافت مستقیم",
                idempotency_key="receipt-1",
                account=self.bank,
            )
        posted = self._post(movement)
        self.assertEqual(posted.status, TreasuryMovementStatus.POSTED)
        self.assertEqual(posted.journal.status, JournalStatus.POSTED)
        self.assertEqual(posted.journal.source_uuid, posted.pk)
        self.assertEqual(posted.journal.source_version, posted.version)
        self.assertEqual(
            posted.posting_evidence.mapping_version_ids,
            [str(self.bank.mapping_versions.get(is_active=True).pk)],
        )
        self.assertEqual(
            approve_and_post_movement(
                organization=self.organization,
                actor=self.owner,
                movement=posted,
                accounting_preparer=self.accountant_membership,
                period=self.period,
                reason="retry",
            ).journal_id,
            posted.journal_id,
        )
        reconciliation = run_treasury_gl_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 12, 31),
        )
        self.assertEqual(reconciliation.exceptions, [])
        self.assertEqual(reconciliation.movement_count, 1)

    def test_transfer_is_one_atomic_movement_with_two_cash_legs(self) -> None:
        destination = self._bank("BANK-2", "IR0000005678", self.cash_gl_2)
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="transfer",
            movement_date=date(2026, 7, 1),
            amount=Decimal(75),
            description="انتقال داخلی",
            idempotency_key="transfer-1",
            source_account=self.bank,
            destination_account=destination,
        )
        posted = self._post(movement)
        self.assertEqual(posted.legs.count(), 2)
        self.assertEqual(posted.journal.lines.count(), 2)
        self.assertEqual(
            posted.journal.lines.aggregate(total=Sum("debit"))["total"], Decimal(75)
        )

    def test_self_approval_and_protected_accounting_post_fail_closed(self) -> None:
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="disbursement",
            movement_date=date(2026, 7, 2),
            amount=Decimal(25),
            description="کنترل تفکیک وظایف",
            idempotency_key="sod-1",
            account=self.bank,
        )
        movement = submit_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            reason="ارسال کنترل",
        )
        with self.assertRaises(PermissionDenied):
            approve_and_post_movement(
                organization=self.organization,
                actor=self.owner,
                movement=movement,
                accounting_preparer=self.owner_membership,
                period=self.period,
                reason="نباید ثبت شود",
            )
        self._replace_treasury_approval_policy(allow=False)
        with self.assertRaises(PermissionDenied):
            approve_and_post_movement(
                organization=self.organization,
                actor=self.owner,
                movement=movement,
                accounting_preparer=self.accountant_membership,
                period=self.period,
                reason="خودتأییدی ممنوع",
            )

    def test_cheque_changes_bank_cash_only_when_cleared(self) -> None:
        cheque = create_cheque(
            organization=self.organization,
            actor=self.owner,
            direction=ChequeDirection.INCOMING,
            controlled_account=self.bank,
            amount=Decimal(50),
            due_date=date(2026, 8, 1),
            serial="CHQ-00009999",
        )
        for status in (
            ChequeStatus.RECEIVED,
            ChequeStatus.DEPOSITED,
            ChequeStatus.PRESENTED,
        ):
            cheque = transition_cheque(
                organization=self.organization,
                actor=self.owner,
                cheque=cheque,
                to_status=status,
                reason="گذار آزمون",
            )
        self.assertIsNone(cheque.cleared_movement_id)
        cheque = clear_cheque(
            organization=self.organization,
            actor=self.owner,
            cheque=cheque,
            accounting_preparer=self.accountant_membership,
            period=self.period,
            clearing_date=date(2026, 8, 2),
            reason="وصول بانکی تأیید شد",
        )
        self.assertEqual(cheque.status, ChequeStatus.CLEARED)
        self.assertEqual(cheque.cleared_movement.status, TreasuryMovementStatus.POSTED)
        cheque = bounce_cleared_cheque(
            organization=self.organization,
            actor=self.owner,
            cheque=cheque,
            requested_by=self.accountant_membership,
            accounting_date=date(2026, 8, 3),
            period=self.period,
            reason="برگشت بانکی تأیید شد",
        )
        self.assertEqual(cheque.status, ChequeStatus.BOUNCED)
        self.assertEqual(
            cheque.cleared_movement.reversal_movement.status,
            TreasuryMovementStatus.POSTED,
        )

    def test_payment_request_is_idempotent_and_policy_controls_self_approval(
        self,
    ) -> None:
        party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind=PartyKind.COMPANY,
            display_name="تأمین‌کننده آزمون",
            created_by=self.owner,
            updated_by=self.owner,
        )
        request = create_payment_request(
            organization=self.organization,
            actor=self.owner,
            kind="vendor_advance",
            amount=Decimal(120),
            purpose="پیش‌پرداخت آزمون",
            idempotency_key="request-policy-1",
            party=party,
        )
        self.assertEqual(
            create_payment_request(
                organization=self.organization,
                actor=self.owner,
                kind="vendor_advance",
                amount=Decimal(120),
                purpose="پیش‌پرداخت آزمون",
                idempotency_key="request-policy-1",
                party=party,
            ).pk,
            request.pk,
        )
        with self.assertRaises(ValidationError):
            create_payment_request(
                organization=self.organization,
                actor=self.owner,
                kind="vendor_advance",
                amount=Decimal(121),
                purpose="پیش‌پرداخت آزمون",
                idempotency_key="request-policy-1",
                party=party,
            )
        other_owner = User.objects.create_user(
            username="p3-request-other", password="x"
        )
        other_organization = create_organization_with_owner(
            owner=other_owner, name="Other Request Tenant", slug="p3-request-other"
        )
        other_party = BusinessParty.objects.create(
            organization=other_organization,
            party_kind=PartyKind.COMPANY,
            display_name="طرف Tenant دیگر",
            created_by=other_owner,
            updated_by=other_owner,
        )
        with self.assertRaises(ValidationError):
            create_payment_request(
                organization=self.organization,
                actor=self.owner,
                kind="vendor_advance",
                amount=Decimal(120),
                purpose="نباید ایجاد شود",
                idempotency_key="request-cross-tenant",
                party=other_party,
            )
        request = submit_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            reason="ارسال آزمون",
        )
        self._replace_treasury_approval_policy(allow=False)
        with self.assertRaises(PermissionDenied):
            decide_payment_request(
                organization=self.organization,
                actor=self.owner,
                request=request,
                approve=True,
                reason="خودتأییدی ممنوع",
            )
        request = decide_payment_request(
            organization=self.organization,
            actor=self.accountant,
            request=request,
            approve=True,
            reason="تأیید مستقل",
        )
        self.assertEqual(request.status, "approved")
        self.assertEqual(request.approved_by, self.accountant_membership)
        self.assertFalse(hasattr(request, "scheduled_for"))

    def test_employee_advance_cash_settlement_reversal_and_reconciliation(
        self,
    ) -> None:
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="EMP-ADV-1",
            first_name="علی",
            last_name="آزمون",
            created_by=self.owner,
            updated_by=self.owner,
        )
        request = create_payment_request(
            organization=self.organization,
            actor=self.owner,
            kind="employee_advance",
            amount=Decimal(100),
            purpose="تنخواه مأموریت",
            idempotency_key="employee-advance-1",
            employee=employee,
        )
        request = submit_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            reason="ارسال تنخواه",
        )
        request = decide_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            approve=True,
            reason="تأیید تنخواه",
        )
        issue = self._post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="disbursement",
                movement_date=date(2026, 9, 1),
                amount=Decimal(100),
                description="پرداخت تنخواه",
                idempotency_key="employee-advance-issue-1",
                account=self.bank,
            )
        )
        request = release_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            movement=issue,
            reason="تخصیص پرداخت",
        )
        advance = open_advance(
            organization=self.organization, actor=self.owner, request=request
        )
        receipt = self._post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 9, 2),
                amount=Decimal(100),
                description="بازپرداخت نقدی تنخواه",
                idempotency_key="employee-advance-return-1",
                account=self.bank,
            )
        )
        settlement = create_advance_settlement(
            organization=self.organization,
            actor=self.owner,
            advance=advance,
            receipt_movement=receipt,
            amount=Decimal(60),
            idempotency_key="employee-settlement-1",
        )
        settlement = submit_advance_settlement(
            organization=self.organization,
            actor=self.owner,
            settlement=settlement,
            reason="ارسال تسویه",
        )
        settlement = decide_advance_settlement(
            organization=self.organization,
            actor=self.owner,
            settlement=settlement,
            approve=True,
            reason="تأیید تسویه",
        )
        advance.refresh_from_db()
        self.assertEqual(settlement.status, AdvanceSettlementStatus.APPROVED)
        self.assertEqual(advance.status, TreasuryAdvanceStatus.PARTIALLY_SETTLED)
        with self.assertRaises(ValidationError):
            extra = create_advance_settlement(
                organization=self.organization,
                actor=self.owner,
                advance=advance,
                receipt_movement=receipt,
                amount=Decimal(50),
                idempotency_key="employee-settlement-over-1",
            )
            extra = submit_advance_settlement(
                organization=self.organization,
                actor=self.owner,
                settlement=extra,
                reason="ارسال مازاد",
            )
            decide_advance_settlement(
                organization=self.organization,
                actor=self.owner,
                settlement=extra,
                approve=True,
                reason="نباید تأیید شود",
            )
        run = run_advance_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 12, 31),
            idempotency_key="advance-recon-1",
        )
        self.assertEqual(run.exceptions, [])
        self.assertEqual(run.issued_total, Decimal(100))
        self.assertEqual(run.settled_total, Decimal(60))
        self.assertEqual(run.outstanding_total, Decimal(40))
        reversal = reverse_advance_settlement(
            organization=self.organization,
            actor=self.owner,
            settlement=settlement,
            requested_by=self.accountant_membership,
            accounting_date=date(2026, 9, 3),
            period=self.period,
            reason="برگشت یکپارچه آزمون",
        )
        self.assertIsNone(reversal.reversal_movement)
        self.assertFalse(hasattr(receipt, "reversal_movement"))
        advance.refresh_from_db()
        self.assertEqual(advance.status, TreasuryAdvanceStatus.OPEN)

    def test_cash_to_gl_review_is_independent_idempotent_and_tamper_evident(
        self,
    ) -> None:
        run = run_treasury_gl_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 12, 31),
        )
        with self.assertRaises(PermissionDenied):
            review_treasury_gl_reconciliation(
                organization=self.organization,
                actor=self.owner,
                run=run,
                reason="خودبررسی مجاز نیست",
            )
        review = review_treasury_gl_reconciliation(
            organization=self.organization,
            actor=self.accountant,
            run=run,
            reason="بررسی مستقل شواهد دقیق",
        )
        self.assertEqual(
            review_treasury_gl_reconciliation(
                organization=self.organization,
                actor=self.accountant,
                run=run,
                reason="بررسی مستقل شواهد دقیق",
            ).pk,
            review.pk,
        )
        self.assertEqual(
            verify_treasury_gl_reconciliation_review(
                organization=self.organization, run=run
            ).pk,
            review.pk,
        )
        with self.assertRaises(ValidationError):
            review.delete()
        TreasuryGLReconciliationReview.objects.filter(pk=review.pk).update(
            signed_evidence_hash="0" * 64
        )
        with self.assertRaisesMessage(ValidationError, "سازگار"):
            verify_treasury_gl_reconciliation_review(
                organization=self.organization, run=run
            )

    def _statement_preview(
        self,
        *,
        key: str,
        amount: Decimal = Decimal(100),
        source: bytes = b"opaque-approved-adapter-evidence",
    ) -> BankStatementImport:
        return preview_statement_import(
            organization=self.organization,
            actor=self.owner,
            account=self.bank,
            provider_code="TEST-PROVIDER",
            format_code="TEST-ADAPTER-V1",
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            file_name="statement.test",
            source_bytes=source,
            rows=(
                StatementRowInput(
                    row_number=1,
                    provider_row_id=f"provider-{key}",
                    transaction_date=date(2026, 6, 1),
                    direction="in",
                    amount=amount,
                    reference="exact-reference",
                    raw_evidence={"trace": key},
                ),
            ),
            max_file_bytes=len(source),
            max_rows=1,
            idempotency_key=key,
        )

    def test_statement_import_is_bounded_idempotent_and_policy_checked(self) -> None:
        with self.assertRaises(ValidationError):
            preview_statement_import(
                organization=self.organization,
                actor=self.owner,
                account=self.bank,
                provider_code="TEST",
                format_code="TEST",
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                file_name="statement.test",
                source_bytes=b"x",
                rows=(),
                max_file_bytes=0,
                max_rows=0,
                idempotency_key="unbounded",
            )
        viewer = self._member("p3-statement-viewer", MembershipRole.VIEWER)
        with self.assertRaises(PermissionDenied):
            preview_statement_import(
                organization=self.organization,
                actor=viewer,
                account=self.bank,
                provider_code="TEST",
                format_code="TEST",
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                file_name="denied.test",
                source_bytes=b"denied",
                rows=(
                    StatementRowInput(
                        row_number=1,
                        transaction_date=date(2026, 6, 1),
                        direction="in",
                        amount=Decimal(1),
                    ),
                ),
                max_file_bytes=6,
                max_rows=1,
                idempotency_key="denied",
            )
        preview = self._statement_preview(key="statement-import-1")
        self.assertEqual(
            self._statement_preview(key="statement-import-1").pk, preview.pk
        )
        with self.assertRaises(ValidationError):
            self._statement_preview(
                key="statement-import-duplicate-file",
            )
        self._replace_treasury_approval_policy(allow=False)
        with self.assertRaises(PermissionDenied):
            accept_statement_import(
                organization=self.organization,
                actor=self.owner,
                statement_import=preview,
                reason="self approval denied",
            )
        accepted = accept_statement_import(
            organization=self.organization,
            actor=self.accountant,
            statement_import=preview,
            reason="independent acceptance",
        )
        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(accepted.lines.count(), 1)
        duplicate_row = StatementRowInput(
            row_number=1,
            transaction_date=date(2026, 6, 2),
            direction="in",
            amount=Decimal(33),
            reference="row duplicate",
        )
        preview_statement_import(
            organization=self.organization,
            actor=self.owner,
            account=self.bank,
            provider_code="TEST-PROVIDER",
            format_code="TEST-ADAPTER-V1",
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            file_name="row-a.test",
            source_bytes=b"row-source-a",
            rows=(duplicate_row,),
            max_file_bytes=12,
            max_rows=1,
            idempotency_key="row-a",
        )
        with self.assertRaises(ValidationError):
            preview_statement_import(
                organization=self.organization,
                actor=self.owner,
                account=self.bank,
                provider_code="TEST-PROVIDER",
                format_code="TEST-ADAPTER-V1",
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                file_name="row-b.test",
                source_bytes=b"row-source-b",
                rows=(
                    StatementRowInput(
                        row_number=2,
                        transaction_date=duplicate_row.transaction_date,
                        direction=duplicate_row.direction,
                        amount=duplicate_row.amount,
                        reference=duplicate_row.reference,
                    ),
                ),
                max_file_bytes=12,
                max_rows=1,
                idempotency_key="row-b",
            )
        tampered = self._statement_preview(
            key="statement-tamper", source=b"tamper-source"
        )
        BankStatementLine.objects.filter(statement_import=tampered).update(
            description="tampered"
        )
        with self.assertRaises(ValidationError):
            accept_statement_import(
                organization=self.organization,
                actor=self.accountant,
                statement_import=tampered,
                reason="must detect tamper",
            )

    def test_exact_match_clearing_reversal_and_bank_reconciliation(self) -> None:
        movement = self._post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 6, 1),
                amount=Decimal(100),
                description="statement candidate",
                idempotency_key="statement-movement-1",
                account=self.bank,
            )
        )
        journal_count = movement.journal.__class__.objects.count()
        accepted = accept_statement_import(
            organization=self.organization,
            actor=self.owner,
            statement_import=self._statement_preview(key="statement-match-1"),
            reason="accepted for exact match",
        )
        line = accepted.lines.get()
        proposals = generate_statement_match_suggestions(
            organization=self.organization,
            actor=self.owner,
            statement_line=line,
            idempotency_key="match-generation-1",
        )
        self.assertEqual(len(proposals), 1)
        self.assertTrue(proposals[0].deterministic)
        self.assertEqual(
            generate_statement_match_suggestions(
                organization=self.organization,
                actor=self.owner,
                statement_line=line,
                idempotency_key="match-generation-1",
            )[0].pk,
            proposals[0].pk,
        )
        clearing = confirm_statement_match(
            organization=self.organization,
            actor=self.owner,
            proposal=proposals[0],
            reason="exact facts confirmed",
        )
        run = run_bank_reconciliation(
            organization=self.organization,
            actor=self.owner,
            statement_import=accepted,
            as_of_date=date(2026, 6, 30),
            idempotency_key="bank-recon-1",
        )
        self.assertEqual(run.exceptions, [])
        self.assertEqual(run.statement_in, Decimal(100))
        self.assertEqual(run.cleared_book_in, Decimal(100))
        self.assertEqual(movement.journal.__class__.objects.count(), journal_count)
        reversal = reverse_statement_clearing(
            organization=self.organization,
            actor=self.owner,
            clearing=clearing,
            reason="wrong external row selected",
        )
        self.assertEqual(reversal.clearing_id, clearing.pk)
        replacement_proposal = generate_statement_match_suggestions(
            organization=self.organization,
            actor=self.owner,
            statement_line=line,
            idempotency_key="match-generation-2",
        )[0]
        self.assertNotEqual(replacement_proposal.pk, proposals[0].pk)
        movement.refresh_from_db()
        self.assertEqual(movement.status, TreasuryMovementStatus.POSTED)
        self.assertEqual(movement.journal.__class__.objects.count(), journal_count)
        corrected = run_bank_reconciliation(
            organization=self.organization,
            actor=self.owner,
            statement_import=accepted,
            as_of_date=date(2026, 6, 30),
            idempotency_key="bank-recon-2",
        )
        self.assertTrue(corrected.exceptions)

    def test_ambiguous_exact_candidates_remain_suggestions(self) -> None:
        for index in (1, 2):
            self._post(
                create_movement(
                    organization=self.organization,
                    actor=self.owner,
                    kind="receipt",
                    movement_date=date(2026, 6, 1),
                    amount=Decimal(70),
                    description="ambiguous candidate",
                    idempotency_key=f"ambiguous-movement-{index}",
                    account=self.bank,
                )
            )
        accepted = accept_statement_import(
            organization=self.organization,
            actor=self.owner,
            statement_import=self._statement_preview(
                key="statement-ambiguous", amount=Decimal(70)
            ),
            reason="accepted for ambiguous match",
        )
        proposals = generate_statement_match_suggestions(
            organization=self.organization,
            actor=self.owner,
            statement_line=accepted.lines.get(),
            idempotency_key="ambiguous-generation-1",
        )
        self.assertEqual(len(proposals), 2)
        self.assertFalse(any(proposal.deterministic for proposal in proposals))
        self.assertFalse(BankReconciliationRun.objects.exists())
        self.assertEqual(BankStatementLine.objects.count(), 1)


class TreasuryWorkbenchUiTests(TestCase):
    """Focused UI boundary checks for Treasury evidence and exceptions."""

    setUp = TreasuryFoundationTests.setUp
    _member = TreasuryFoundationTests._member
    _bank = TreasuryFoundationTests._bank
    _activate_policy = TreasuryFoundationTests._activate_policy

    def _activate_client(self, user: User, organization=None) -> None:
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str((organization or self.organization).pk)
        session.save()

    def test_workbenches_are_tenant_scoped_and_accessible(self) -> None:
        self._activate_client(self.owner)
        response = self.client.get(reverse("treasury:workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-labelledby="treasury-title"', html=False)
        self.assertNotContains(response, "IR0000001234")
        response = self.client.get(reverse("treasury:statement_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فقط تطبیق دقیق پیشنهاد می‌شود")

    def test_statement_mutation_requires_csrf(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        session = csrf_client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(
            csrf_client.post(
                reverse("treasury:confirm_match", args=[uuid4()]),
                {"reason": "test"},
            ).status_code,
            403,
        )


class TreasuryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_tenant_account_code_creates_exactly_one_row(self) -> None:
        owner = User.objects.create_user(username="p3-race-owner", password="x")
        organization = create_organization_with_owner(
            owner=owner, name="P3 Race Tenant", slug="p3-race-tenant"
        )

        def create_once() -> str:
            close_old_connections()
            try:
                create_treasury_account(
                    organization=organization,
                    actor=owner,
                    code="RACE-ACCOUNT",
                    name="Race Account",
                    kind=TreasuryAccountKind.BANK,
                    sensitive_identifier="RACE0001",
                )
            except IntegrityError:
                return "conflict"
            finally:
                close_old_connections()
            return "created"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: create_once(), range(2)))
        self.assertCountEqual(results, ["created", "conflict"])
        self.assertEqual(
            TreasuryAccount.objects.filter(organization=organization).count(), 1
        )


class TreasuryStatementConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    setUp = TreasuryFoundationTests.setUp
    _member = TreasuryFoundationTests._member
    _activate_policy = TreasuryFoundationTests._activate_policy
    _bank = TreasuryFoundationTests._bank
    _post = TreasuryFoundationTests._post
    _statement_preview = TreasuryFoundationTests._statement_preview

    def test_concurrent_acceptance_and_clearing_are_single_effect(self) -> None:
        movement = self._post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 6, 1),
                amount=Decimal(100),
                description="concurrent statement candidate",
                idempotency_key="statement-concurrent-movement",
                account=self.bank,
            )
        )
        preview = self._statement_preview(key="statement-concurrent")

        def accept_once(_: int) -> str:
            close_old_connections()
            try:
                result = accept_statement_import(
                    organization=self.organization.__class__.objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.owner.pk),
                    statement_import=BankStatementImport.objects.get(pk=preview.pk),
                    reason="same concurrent acceptance",
                )
                return str(result.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            accepted_ids = list(executor.map(accept_once, range(2)))
        self.assertEqual(len(set(accepted_ids)), 1)
        accepted = BankStatementImport.objects.get(pk=preview.pk)
        proposal = generate_statement_match_suggestions(
            organization=self.organization,
            actor=self.owner,
            statement_line=accepted.lines.get(),
            idempotency_key="concurrent-generation-1",
        )[0]

        def clear_once(_: int) -> str:
            close_old_connections()
            try:
                result = confirm_statement_match(
                    organization=self.organization.__class__.objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.owner.pk),
                    proposal=proposal.__class__.objects.get(pk=proposal.pk),
                    reason="same concurrent clearing",
                )
                return str(result.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            clearing_ids = list(executor.map(clear_once, range(2)))
        self.assertEqual(len(set(clearing_ids)), 1)
        self.assertEqual(
            TreasuryMovementClearing.objects.filter(
                movement=movement, active=True
            ).count(),
            1,
        )


class TreasuryStatementMigrationRehearsalTests(TestCase):
    def test_treasury_statement_migrations_rollback_and_reapply(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("The migration contract targets PostgreSQL.")
        executor = MigrationExecutor(connection)
        for migration_name in (
            "0005_bankstatementimport_bankreconciliationrun_and_more",
            "0006_bankstatementimport_treasury_stmt_import_positive_bounds_and_more",
        ):
            migration = executor.loader.get_migration("treasury", migration_name)
            self.assertTrue(
                all(operation.reversible for operation in migration.operations)
            )
            self.assertIn(
                ("treasury", migration_name), executor.loader.applied_migrations
            )
        tables = set(connection.introspection.table_names())
        self.assertIn("treasury_bankstatementimport", tables)
        self.assertIn("treasury_bankreconciliationrun", tables)


class TreasurySettlementConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    setUp = TreasuryFoundationTests.setUp
    _member = TreasuryFoundationTests._member
    _activate_policy = TreasuryFoundationTests._activate_policy
    _bank = TreasuryFoundationTests._bank
    _post = TreasuryFoundationTests._post

    def test_concurrent_settlements_cannot_overapply_one_advance(self) -> None:
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="EMP-RACE-1",
            first_name="محمد",
            last_name="همزمانی",
            created_by=self.owner,
            updated_by=self.owner,
        )
        request = create_payment_request(
            organization=self.organization,
            actor=self.owner,
            kind="employee_advance",
            amount=Decimal(100),
            purpose="تنخواه همزمانی",
            idempotency_key="advance-race-request",
            employee=employee,
        )
        request = decide_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=submit_payment_request(
                organization=self.organization,
                actor=self.owner,
                request=request,
                reason="ارسال",
            ),
            approve=True,
            reason="تأیید",
        )
        issue = self._post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="disbursement",
                movement_date=date(2026, 10, 1),
                amount=Decimal(100),
                description="پرداخت همزمانی",
                idempotency_key="advance-race-issue",
                account=self.bank,
            )
        )
        request = release_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            movement=issue,
            reason="تخصیص",
        )
        advance = open_advance(
            organization=self.organization, actor=self.owner, request=request
        )
        receipt = self._post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 10, 2),
                amount=Decimal(120),
                description="بازپرداخت همزمانی",
                idempotency_key="advance-race-receipt",
                account=self.bank,
            )
        )
        settlements = []
        for index in (1, 2):
            settlement = create_advance_settlement(
                organization=self.organization,
                actor=self.owner,
                advance=advance,
                receipt_movement=receipt,
                amount=Decimal(60),
                idempotency_key=f"advance-race-settlement-{index}",
            )
            settlements.append(
                submit_advance_settlement(
                    organization=self.organization,
                    actor=self.owner,
                    settlement=settlement,
                    reason="ارسال همزمانی",
                )
            )

        def approve_once(settlement_id) -> str:
            close_old_connections()
            try:
                decide_advance_settlement(
                    organization=self.organization,
                    actor=self.owner,
                    settlement=AdvanceSettlement.objects.get(pk=settlement_id),
                    approve=True,
                    reason="تأیید همزمانی",
                )
            except ValidationError:
                return "conflict"
            finally:
                close_old_connections()
            return "approved"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    approve_once, [settlement.pk for settlement in settlements]
                )
            )
        self.assertCountEqual(results, ["approved", "conflict"])
