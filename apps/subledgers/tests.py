from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import AccountType, JournalEntry
from apps.accounting.services import (
    create_account,
    create_fiscal_period,
    create_fiscal_year,
)
from apps.accounts.models import User
from apps.organizations.authorization import membership_has_permission
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
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
from apps.subledgers.models import Obligation, ObligationDirection
from apps.subledgers.services import (
    allocate_settlement,
    approve_write_off,
    recognize_obligation,
    reverse_settlement,
    review_subledger_reconciliation,
    run_aging,
    run_subledger_reconciliation,
    verify_subledger_reconciliation_review,
)
from apps.treasury.models import TreasuryAccountKind, TreasuryAccountStatus
from apps.treasury.services import (
    approve_and_post_movement,
    create_account_mapping_version,
    create_movement,
    create_treasury_account,
    reverse_posted_movement,
    submit_movement,
    transition_treasury_account,
)


class SubledgerFoundationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p3-sub-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="P3 Subledger", slug="p3-subledger"
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.accountant = self._member("p3-sub-accountant", MembershipRole.ACCOUNTANT)
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
            TREASURY_SELF_APPROVAL_POLICY_CODE, {"allow_self_approval": True}
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-SUB",
            name="سال مالی زیر‌دفتر",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        self.period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=year,
            number=1,
            name="دوره زیر‌دفتر",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        cash_gl = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1110",
            name="بانک زیر‌دفتر",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        clearing_gl = create_account(
            organization=self.organization,
            actor=self.owner,
            code="2190",
            name="وجوه در راه زیر‌دفتر",
            account_type=AccountType.LIABILITY,
            is_posting=True,
        )
        account = create_treasury_account(
            organization=self.organization,
            actor=self.owner,
            code="SUB-BANK",
            name="بانک زیر‌دفتر",
            kind=TreasuryAccountKind.BANK,
            sensitive_identifier="IR0000007766",
        )
        create_account_mapping_version(
            organization=self.organization,
            actor=self.owner,
            account=account,
            cash_ledger_account=cash_gl,
            clearing_ledger_account=clearing_gl,
            effective_from=date(2026, 1, 1),
            reason="نگاشت آزمون زیر‌دفتر",
        )
        self.bank = transition_treasury_account(
            organization=self.organization,
            actor=self.owner,
            account=account,
            to_status=TreasuryAccountStatus.ACTIVE,
            reason="فعال‌سازی آزمون زیر‌دفتر",
        )

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
            reason="P3 subledger test role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P3 subledger test scope",
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
            reason="P3 subledger test policy",
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
            reason="P3 subledger test activation",
        )

    def _obligation(self, amount: Decimal = Decimal(100)) -> Obligation:
        source_id = uuid4()
        return Obligation.objects.create(
            organization=self.organization,
            direction=ObligationDirection.RECEIVABLE,
            source_kind="test.exact-source.v1",
            source_uuid=source_id,
            source_version=1,
            source_line_key="",
            source_status="final",
            source_hash="a" * 64,
            source_snapshot={"source": str(source_id)},
            party_name_snapshot="Exact Customer",
            original_amount=amount,
            recognized_on=date(2026, 5, 1),
            due_date=date(2026, 5, 31),
            idempotency_key=f"OBL:{source_id}",
            payload_hash="b" * 64,
            recognized_by=self.owner_membership,
        )

    def _posted_receipt(self, amount: Decimal = Decimal(100)):
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="receipt",
            movement_date=date(2026, 6, 1),
            amount=amount,
            description="دریافت آزمون زیر‌دفتر",
            idempotency_key=f"SUB-RECEIPT:{uuid4()}",
            account=self.bank,
        )
        movement = submit_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            reason="ارسال آزمون زیر‌دفتر",
        )
        return approve_and_post_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            accounting_preparer=self.accountant_membership,
            period=self.period,
            reason="ثبت آزمون زیر‌دفتر",
        )

    def test_unregistered_source_and_writeoff_authority_fail_closed(self) -> None:
        self.assertFalse(
            membership_has_permission(
                self.owner_membership,
                BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_APPROVE,
            )
        )
        self.assertFalse(
            membership_has_permission(
                self.owner_membership,
                BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_REVERSE,
            )
        )
        with self.assertRaisesMessage(ValidationError, "P3-S27-Q01"):
            recognize_obligation(
                organization=self.organization,
                actor=self.owner,
                source_kind="billing.progress_claim.v1",
                source_uuid=uuid4(),
                source_version=1,
                idempotency_key="UNREGISTERED",
            )
        with self.assertRaisesMessage(ValidationError, "P3-S27-Q03"):
            approve_write_off()

    def test_partial_allocation_caps_reversal_and_as_of_aging(self) -> None:
        obligation = self._obligation()
        receipt = self._posted_receipt()
        allocation = allocate_settlement(
            organization=self.organization,
            actor=self.owner,
            obligation=obligation,
            movement=receipt,
            amount=Decimal(60),
            effective_date=date(2026, 6, 1),
            reason="تخصیص جزئی آزمون",
            idempotency_key="ALLOC-1",
        )
        self.assertEqual(obligation.settlement_status, "partial")
        self.assertEqual(obligation.outstanding_amount, Decimal(40))
        self.assertEqual(
            allocate_settlement(
                organization=self.organization,
                actor=self.owner,
                obligation=obligation,
                movement=receipt,
                amount=Decimal(60),
                effective_date=date(2026, 6, 1),
                reason="تخصیص جزئی آزمون",
                idempotency_key="ALLOC-1",
            ).pk,
            allocation.pk,
        )
        with self.assertRaisesMessage(ValidationError, "idempotency"):
            allocate_settlement(
                organization=self.organization,
                actor=self.owner,
                obligation=obligation,
                movement=receipt,
                amount=Decimal(59),
                effective_date=date(2026, 6, 1),
                reason="تخصیص جزئی آزمون",
                idempotency_key="ALLOC-1",
            )
        with self.assertRaisesMessage(ValidationError, "مانده تعهد"):
            allocate_settlement(
                organization=self.organization,
                actor=self.owner,
                obligation=obligation,
                movement=receipt,
                amount=Decimal(41),
                effective_date=date(2026, 6, 2),
                reason="بیش‌تخصیص آزمون",
                idempotency_key="ALLOC-OVER",
            )
        with self.assertRaisesMessage(ValidationError, "تخصیص فعال AP/AR"):
            reverse_posted_movement(
                organization=self.organization,
                actor=self.owner,
                movement=receipt,
                requested_by=self.accountant_membership,
                accounting_date=date(2026, 6, 5),
                period=self.period,
                reason="نباید با تخصیص فعال برگشت شود",
            )
        reverse_settlement(
            organization=self.organization,
            actor=self.owner,
            allocation=allocation,
            effective_date=date(2026, 6, 10),
            reason="برگشت تخصیص آزمون",
            idempotency_key="ALLOC-REV-1",
        )
        self.assertEqual(obligation.settlement_status, "open")
        before = run_aging(
            organization=self.organization,
            actor=self.owner,
            direction=ObligationDirection.RECEIVABLE,
            as_of_date=date(2026, 6, 5),
            idempotency_key="AGING-BEFORE",
        )
        after = run_aging(
            organization=self.organization,
            actor=self.owner,
            direction=ObligationDirection.RECEIVABLE,
            as_of_date=date(2026, 6, 15),
            idempotency_key="AGING-AFTER",
        )
        self.assertEqual(before.outstanding_total, Decimal(40))
        self.assertEqual(after.outstanding_total, Decimal(100))
        self.assertNotIn("bucket", before.item_snapshots[0])

    def test_tenant_isolation_and_direction_are_enforced(self) -> None:
        obligation = self._obligation()
        receipt = self._posted_receipt()
        other_owner = User.objects.create_user(username="p3-sub-other", password="x")
        other = create_organization_with_owner(
            owner=other_owner, name="Other Subledger", slug="other-subledger"
        )
        with self.assertRaises(PermissionDenied):
            allocate_settlement(
                organization=other,
                actor=other_owner,
                obligation=obligation,
                movement=receipt,
                amount=Decimal(10),
                effective_date=date(2026, 6, 1),
                reason="cross tenant",
                idempotency_key="CROSS",
            )
        payable = Obligation.objects.create(
            organization=self.organization,
            direction=ObligationDirection.PAYABLE,
            source_kind="test.payable.v1",
            source_uuid=uuid4(),
            source_version=1,
            source_status="final",
            source_hash="c" * 64,
            source_snapshot={"kind": "payable"},
            party_name_snapshot="Exact Supplier",
            original_amount=Decimal(10),
            recognized_on=date(2026, 5, 1),
            idempotency_key="PAYABLE-1",
            payload_hash="d" * 64,
            recognized_by=self.owner_membership,
        )
        with self.assertRaisesMessage(ValidationError, "سازگار"):
            allocate_settlement(
                organization=self.organization,
                actor=self.owner,
                obligation=payable,
                movement=receipt,
                amount=Decimal(10),
                effective_date=date(2026, 6, 1),
                reason="جهت ناسازگار",
                idempotency_key="WRONG-DIRECTION",
            )

    def test_reconciliation_retains_missing_mapping_without_accounting_mutation(
        self,
    ) -> None:
        obligation = self._obligation()
        journal_count = JournalEntry.objects.count()
        run = run_subledger_reconciliation(
            organization=self.organization,
            actor=self.owner,
            direction=ObligationDirection.RECEIVABLE,
            as_of_date=date(2026, 6, 30),
            idempotency_key="RECON-1",
        )
        self.assertEqual(run.subledger_outstanding_total, obligation.original_amount)
        self.assertEqual(run.linked_gl_total, Decimal(0))
        self.assertEqual(
            run.exception_snapshots[0]["code"], "MISSING_RECOGNITION_JOURNAL"
        )
        self.assertEqual(JournalEntry.objects.count(), journal_count)

    def test_subledger_reconciliation_review_enforces_maker_checker(self) -> None:
        self._obligation()
        run = run_subledger_reconciliation(
            organization=self.organization,
            actor=self.owner,
            direction=ObligationDirection.RECEIVABLE,
            as_of_date=date(2026, 6, 30),
            idempotency_key="RECON-REVIEW-1",
        )
        with self.assertRaises(PermissionDenied):
            review_subledger_reconciliation(
                organization=self.organization,
                actor=self.owner,
                run=run,
                reason="خودبررسی مجاز نیست",
            )
        review = review_subledger_reconciliation(
            organization=self.organization,
            actor=self.accountant,
            run=run,
            reason="بررسی مستقل مانده و استثناها",
        )
        self.assertEqual(
            review_subledger_reconciliation(
                organization=self.organization,
                actor=self.accountant,
                run=run,
                reason="بررسی مستقل مانده و استثناها",
            ).pk,
            review.pk,
        )
        self.assertEqual(
            verify_subledger_reconciliation_review(
                organization=self.organization, run=run
            ).pk,
            review.pk,
        )
        other_owner = User.objects.create_user(username="review-other", password="x")
        other = create_organization_with_owner(
            owner=other_owner, name="Review Other", slug="review-other"
        )
        with self.assertRaises(PermissionDenied):
            review_subledger_reconciliation(
                organization=other,
                actor=other_owner,
                run=run,
                reason="cross tenant",
            )


class SubledgerWorkbenchUiTests(TestCase):
    """Request-level coverage for the bounded P3-S28--S29 workbench."""

    setUp = SubledgerFoundationTests.setUp
    _member = SubledgerFoundationTests._member
    _activate_policy = SubledgerFoundationTests._activate_policy
    _obligation = SubledgerFoundationTests._obligation
    _posted_receipt = SubledgerFoundationTests._posted_receipt

    def _activate_client(self, user: User, organization=None) -> None:
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str((organization or self.organization).pk)
        session.save()

    def test_workbench_is_rtl_and_hides_unimplemented_paths(self) -> None:
        self._obligation()
        self._activate_client(self.owner)

        response = self.client.get(reverse("subledgers:workbench"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"', html=False)
        self.assertContains(response, "بدون بازه‌بندی")
        self.assertContains(response, "تأیید و برگشت سوخت فعال نیست")
        self.assertNotContains(response, "حساب نقدی")

    def test_allocation_rejects_cross_tenant_movement(self) -> None:
        obligation = self._obligation()
        other_owner = User.objects.create_user(username="ui-other", password="x")
        other = create_organization_with_owner(
            owner=other_owner, name="Other UI", slug="other-ui"
        )
        self._activate_client(self.owner)

        response = self.client.post(
            reverse("subledgers:allocate", args=[obligation.pk]),
            {
                "treasury_movement_id": uuid4(),
                "amount": "1",
                "effective_date": "2026-06-01",
                "reason": "test",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(other.slug, "other-ui")

    def test_mutation_requires_csrf_and_suspended_tenant_cannot_read(self) -> None:
        obligation = self._obligation()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        session = csrf_client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(
            csrf_client.post(
                reverse("subledgers:propose_writeoff", args=[obligation.pk]),
                {"amount": "1", "effective_date": "2026-06-01", "reason": "test"},
            ).status_code,
            403,
        )
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        self._activate_client(self.owner)
        self.assertEqual(self.client.get(reverse("subledgers:workbench")).status_code, 403)


class SubledgerConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    setUp = SubledgerFoundationTests.setUp
    _member = SubledgerFoundationTests._member
    _activate_policy = SubledgerFoundationTests._activate_policy
    _obligation = SubledgerFoundationTests._obligation
    _posted_receipt = SubledgerFoundationTests._posted_receipt

    def test_concurrent_partial_allocations_cannot_overapply(self) -> None:
        obligation = self._obligation()
        receipt = self._posted_receipt()

        def allocate_once(index: int) -> str:
            close_old_connections()
            try:
                allocate_settlement(
                    organization=self.organization.__class__.objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.owner.pk),
                    obligation=Obligation.objects.get(pk=obligation.pk),
                    movement=receipt.__class__.objects.get(pk=receipt.pk),
                    amount=Decimal(60),
                    effective_date=date(2026, 6, index),
                    reason="تخصیص همزمان آزمون",
                    idempotency_key=f"ALLOC-RACE-{index}",
                )
            except ValidationError:
                return "conflict"
            finally:
                close_old_connections()
            return "allocated"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(allocate_once, (1, 2)))
        self.assertCountEqual(results, ["allocated", "conflict"])
        self.assertEqual(
            obligation.settlement_allocations.filter(reversal__isnull=True).count(), 1
        )


class SubledgerMigrationRehearsalTests(TransactionTestCase):
    reset_sequences = True

    def test_subledger_initial_migration_rolls_back_and_reapplies(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("The migration contract targets PostgreSQL.")
        latest = ("subledgers", "0001_initial")
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("subledgers", None)])
            self.assertNotIn(
                "subledgers_obligation", connection.introspection.table_names()
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([latest])
        self.assertIn("subledgers_obligation", connection.introspection.table_names())
        call_command("check", verbosity=0)
