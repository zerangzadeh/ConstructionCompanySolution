import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from queue import Queue
from threading import Barrier
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import (
    Account,
    AccountType,
    FiscalPeriod,
    FiscalPeriodStatus,
    JournalEntry,
    JournalKind,
    JournalStatus,
    OpeningImportStatus,
    ReconciliationExceptionDisposition,
    ReconciliationExceptionDispositionCode,
    ReconciliationExceptionSnapshot,
    ReconciliationReview,
    ReconciliationRun,
    ReconciliationTieOutSnapshot,
    ReconciliationTieOutType,
)
from apps.accounting.policy_calculations import (
    accounting_rounding_policy_from_version,
    money_precision_policy_from_version,
    preserve_intermediate_calculation,
    require_final_monetary_amount,
    round_final_monetary_amount,
)
from apps.accounting.reconciliation import (
    create_manual_opening_reconciliation_run,
    dispose_reconciliation_exception,
    inspect_manual_opening_reconciliation,
    sign_off_reconciliation_run,
    verify_signed_reconciliation_run,
)
from apps.accounting.services import (
    ACCOUNTING_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    accept_opening_import,
    add_journal_line,
    add_opening_import_line,
    close_period,
    create_account,
    create_fiscal_period,
    create_fiscal_year,
    create_journal,
    create_opening_import,
    create_replacement_journal,
    post_journal,
    reverse_journal,
    submit_journal,
    submit_opening_import,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
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
    PolicyCategory,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE as SPEC_PRECISION_POLICY_CODE,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_ROUNDING_POLICY_CODE as SPEC_ROUNDING_POLICY_CODE,
)
from apps.organizations.policy_specs import (
    get_platform_policy_spec,
    initial_accounting_policy_parameters,
    validate_policy_parameters,
)
from apps.organizations.services import create_organization_with_owner


class AccountingPolicyCalculationTests(SimpleTestCase):
    def _version(self, code: str):
        spec = get_platform_policy_spec(code)
        return SimpleNamespace(
            policy=SimpleNamespace(
                code=code,
                name=spec.name,
                category=spec.category,
                sensitivity=spec.sensitivity,
                tenant_selectable=spec.tenant_selectable,
            ),
            parameters=initial_accounting_policy_parameters(code),
        )

    def test_round_half_up_and_final_boundary_are_deterministic(self) -> None:
        precision = money_precision_policy_from_version(
            self._version(SPEC_PRECISION_POLICY_CODE)
        )
        rounding = accounting_rounding_policy_from_version(
            self._version(SPEC_ROUNDING_POLICY_CODE)
        )
        self.assertEqual(
            round_final_monetary_amount(
                Decimal("1.5"), precision=precision, rounding=rounding
            ),
            Decimal(2),
        )
        self.assertEqual(
            round_final_monetary_amount(
                Decimal("-1.5"), precision=precision, rounding=rounding
            ),
            Decimal(-2),
        )
        with self.assertRaises(ValidationError):
            require_final_monetary_amount(
                Decimal("1.5"), precision=precision, rounding=rounding
            )

    def test_intermediate_value_is_preserved_and_invalid_values_are_rejected(
        self,
    ) -> None:
        precision = money_precision_policy_from_version(
            self._version(SPEC_PRECISION_POLICY_CODE)
        )
        original = Decimal("1.23456789")
        self.assertEqual(
            preserve_intermediate_calculation(original, precision=precision), original
        )
        invalid = initial_accounting_policy_parameters(SPEC_PRECISION_POLICY_CODE)
        invalid["money_scale"] = 1
        with self.assertRaises(ValidationError):
            validate_policy_parameters(
                spec=get_platform_policy_spec(SPEC_PRECISION_POLICY_CODE),
                parameters=invalid,
            )


class AccountingFoundationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p2-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="P2 Tenant", slug="p2-tenant"
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.approver = self._member("p2-approver", MembershipRole.ACCOUNTANT)
        self.other_owner = User.objects.create_user(
            username="other-owner", password="x"
        )
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="Other Tenant", slug="other-tenant"
        )
        self.year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-01",
            name="سال مالی آزمون",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        self.period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            number=1,
            name="دوره اول",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        self.debit_account = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1100",
            name="دارایی افتتاحیه",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        self.credit_account = create_account(
            organization=self.organization,
            actor=self.owner,
            code="3100",
            name="حقوق مالکانه افتتاحیه",
            account_type=AccountType.EQUITY,
            is_posting=True,
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
            reason="P2 test assignment",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P2 test organization scope",
        )
        return user

    def _journal(self):
        journal = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind=JournalKind.OPENING,
            document_date=date(2026, 1, 1),
            accounting_date=date(2026, 1, 1),
            description="مانده افتتاحیه کنترل‌شده",
            source_key="OPENING-2026",
            evidence_reference="evidence://opening/2026",
            reconciliation_reference="reconciliation://opening/2026",
            cutoff_date=date(2025, 12, 31),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(100),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(100),
        )
        return journal

    def _activate_accounting_policy(self, *, code: str, category: str) -> None:
        spec = get_platform_policy_spec(code)
        policy = PlatformPolicy.objects.create(
            code=code,
            name=spec.name,
            category=category,
            sensitivity=spec.sensitivity,
            tenant_selectable=spec.tenant_selectable,
            requires_source_provenance=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        now = timezone.now()
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=1,
            parameters=initial_accounting_policy_parameters(code),
            effective_from=timezone.localdate(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            created_by=self.owner,
            published_by=self.owner,
            published_at=now,
            reason="P2 test policy",
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
            reason="P2 test activation",
        )

    def _activate_posting_policies(self) -> None:
        self._activate_accounting_policy(
            code=ACCOUNTING_PRECISION_POLICY_CODE, category=PolicyCategory.PRECISION
        )
        self._activate_accounting_policy(
            code=ACCOUNTING_ROUNDING_POLICY_CODE, category=PolicyCategory.ROUNDING
        )

    def _posted_journal(self):
        self._activate_posting_policies()
        proposed = submit_journal(
            organization=self.organization, actor=self.owner, journal=self._journal()
        )
        return post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=proposed,
            reason="independent review",
        )

    def test_submit_rejects_fractional_final_manual_line_at_money_scale_zero(
        self,
    ) -> None:
        self._activate_posting_policies()
        journal = self._journal()
        debit_line, credit_line = list(journal.lines.order_by("line_number"))
        debit_line.debit = Decimal("100.5")
        debit_line.save()
        credit_line.credit = Decimal("100.5")
        credit_line.save()

        with self.assertRaisesMessage(ValidationError, "گردکردن ضمنی"):
            submit_journal(
                organization=self.organization, actor=self.owner, journal=journal
            )

    def test_posted_journal_retains_immutable_policy_version_links(self) -> None:
        posted = self._posted_journal()
        precision_version_id = posted.precision_policy_version_id
        rounding_version_id = posted.rounding_policy_version_id
        precision = posted.precision_policy_version
        precision.parameters = {**precision.parameters, "money_scale": 1}

        with self.assertRaises(ValidationError):
            precision.save()

        posted.refresh_from_db()
        self.assertEqual(posted.precision_policy_version_id, precision_version_id)
        self.assertEqual(posted.rounding_policy_version_id, rounding_version_id)

    def test_cross_tenant_account_parent_is_denied(self) -> None:
        other_account = create_account(
            organization=self.other_organization,
            actor=self.other_owner,
            code="1000",
            name="Other account",
            account_type=AccountType.ASSET,
        )
        with self.assertRaises(ValidationError):
            create_account(
                organization=self.organization,
                actor=self.owner,
                code="1110",
                name="Invalid child",
                account_type=AccountType.ASSET,
                parent=other_account,
            )

    def test_fiscal_period_overlap_and_used_date_reinterpretation_are_blocked(
        self,
    ) -> None:
        with self.assertRaises(ValidationError):
            create_fiscal_period(
                organization=self.organization,
                actor=self.owner,
                fiscal_year=self.year,
                number=2,
                name="هم‌پوشان",
                starts_on=date(2026, 1, 15),
                ends_on=date(2026, 2, 15),
            )
        self._journal()
        self.period.ends_on = date(2026, 2, 1)
        with self.assertRaises(ValidationError):
            self.period.save()

    def test_opening_requires_cutoff_evidence_and_reconciliation(self) -> None:
        with self.assertRaises(ValidationError):
            create_journal(
                organization=self.organization,
                actor=self.owner,
                period=self.period,
                kind=JournalKind.OPENING,
                document_date=date(2026, 1, 1),
                accounting_date=date(2026, 1, 1),
                description="Invalid opening",
                source_key="INVALID-OPENING",
                cutoff_date=date(2025, 12, 31),
            )

    def test_submission_fails_closed_without_precision_and_rounding_values(
        self,
    ) -> None:
        with self.assertRaises(ValidationError):
            submit_journal(
                organization=self.organization,
                actor=self.owner,
                journal=self._journal(),
            )

    def test_balanced_opening_posts_once_with_independent_authorization(self) -> None:
        self._activate_posting_policies()
        proposed = submit_journal(
            organization=self.organization, actor=self.owner, journal=self._journal()
        )
        with self.assertRaises(PermissionDenied):
            post_journal(
                organization=self.organization,
                actor=self.owner,
                journal=proposed,
                reason="self approval forbidden",
            )
        posted = post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=proposed,
            reason="independent opening review",
        )
        self.assertEqual(posted.status, JournalStatus.POSTED)
        self.assertEqual(posted.number, 1)
        with self.assertRaises(ValidationError):
            posted.description = "rewrite"
            posted.save()
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.ACCOUNTING_JOURNAL_POSTED,
                entity_id=str(posted.pk),
            ).exists()
        )

    def test_period_close_requires_independent_authorized_memberships(self) -> None:
        approver_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.approver
        )
        with self.assertRaises(PermissionDenied):
            close_period(
                organization=self.organization,
                actor=self.approver,
                period=self.period,
                requested_by=approver_membership,
                reason="same actor",
            )
        with self.assertRaises(ValidationError):
            close_period(
                organization=self.organization,
                actor=self.approver,
                period=self.period,
                requested_by=self.owner_membership,
                reason="period reviewed",
            )

    def test_viewer_cannot_prepare_journal(self) -> None:
        viewer = self._member("p2-viewer", MembershipRole.VIEWER)
        with self.assertRaises(PermissionDenied):
            create_journal(
                organization=self.organization,
                actor=viewer,
                period=self.period,
                kind=JournalKind.MANUAL,
                document_date=date(2026, 1, 2),
                accounting_date=date(2026, 1, 2),
                description="unauthorized",
                source_key="UNAUTHORIZED",
            )

    def test_post_is_idempotent_and_source_key_conflict_is_rejected(self) -> None:
        posted = self._posted_journal()
        retried = post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=posted,
            reason="safe retry",
        )
        self.assertEqual(retried.pk, posted.pk)
        self.assertEqual(
            JournalEntry.objects.filter(
                organization=self.organization, number=posted.number
            ).count(),
            1,
        )
        with self.assertRaises(ValidationError):
            create_journal(
                organization=self.organization,
                actor=self.owner,
                period=self.period,
                kind=JournalKind.OPENING,
                document_date=date(2026, 1, 1),
                accounting_date=date(2026, 1, 1),
                description="changed retry payload",
                source_key="OPENING-2026",
                evidence_reference="evidence://opening/2026",
                reconciliation_reference="reconciliation://opening/2026",
                cutoff_date=date(2025, 12, 31),
            )

    def test_posted_lines_retain_account_snapshot_and_are_immutable(self) -> None:
        posted = self._posted_journal()
        line = posted.lines.select_related("account").order_by("line_number").first()
        assert line is not None
        self.assertEqual(line.account_snapshot["code"], "1100")
        self.debit_account.name = "renamed current master"
        self.debit_account.save()
        line.refresh_from_db()
        self.assertEqual(line.account_snapshot["name"], "دارایی افتتاحیه")
        line.description = "rewrite"
        with self.assertRaises(ValidationError):
            line.save()

    def test_closed_period_blocks_posting_without_partial_number(self) -> None:
        self._activate_posting_policies()
        journal = self._journal()
        approver_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.approver
        )
        with self.assertRaises(ValidationError):
            close_period(
                organization=self.organization,
                actor=self.approver,
                period=self.period,
                requested_by=self.owner_membership,
                reason="draft must block close",
            )
        proposed = submit_journal(
            organization=self.organization, actor=self.owner, journal=journal
        )
        FiscalPeriod.objects.filter(pk=self.period.pk).update(
            status=FiscalPeriodStatus.CLOSED
        )
        with self.assertRaises(ValidationError):
            post_journal(
                organization=self.organization,
                actor=self.approver,
                journal=proposed,
                reason="must stay blocked",
            )
        proposed.refresh_from_db()
        self.assertIsNone(proposed.number)
        self.assertEqual(proposed.status, JournalStatus.PROPOSED)
        self.assertNotEqual(approver_membership.pk, self.owner_membership.pk)

    def test_reversal_is_balanced_linked_immutable_and_idempotent(self) -> None:
        posted = self._posted_journal()
        reversal = reverse_journal(
            organization=self.organization,
            actor=self.approver,
            original=posted,
            requested_by=self.owner_membership,
            accounting_date=date(2026, 1, 3),
            period=self.period,
            reason="correct proven error",
        )
        self.assertEqual(reversal.status, JournalStatus.POSTED)
        self.assertEqual(reversal.kind, JournalKind.REVERSAL)
        self.assertEqual(reversal.reverses_id, posted.pk)
        first = reversal.lines.get(line_number=1)
        self.assertEqual(first.credit, Decimal(100))
        retried = reverse_journal(
            organization=self.organization,
            actor=self.approver,
            original=posted,
            requested_by=self.owner_membership,
            accounting_date=date(2026, 1, 3),
            period=self.period,
            reason="correct proven error",
        )
        self.assertEqual(retried.pk, reversal.pk)
        self.assertEqual(JournalEntry.objects.filter(reverses=posted).count(), 1)

    def test_replacement_requires_and_links_posted_reversal(self) -> None:
        posted = self._posted_journal()
        with self.assertRaises(ValidationError):
            create_replacement_journal(
                organization=self.organization,
                actor=self.owner,
                original=posted,
                period=self.period,
                document_date=date(2026, 1, 4),
                accounting_date=date(2026, 1, 4),
                description="premature replacement",
            )
        reverse_journal(
            organization=self.organization,
            actor=self.approver,
            original=posted,
            requested_by=self.owner_membership,
            accounting_date=date(2026, 1, 3),
            period=self.period,
            reason="replace proven error",
        )
        replacement = create_replacement_journal(
            organization=self.organization,
            actor=self.owner,
            original=posted,
            period=self.period,
            document_date=date(2026, 1, 4),
            accounting_date=date(2026, 1, 4),
            description="corrected replacement",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=replacement,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(90),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=replacement,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(90),
        )
        replacement = submit_journal(
            organization=self.organization,
            actor=self.owner,
            journal=replacement,
        )
        replacement = post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=replacement,
            reason="independent corrected posting",
        )
        self.assertEqual(replacement.replaces_id, posted.pk)
        self.assertEqual(replacement.source_version, posted.source_version + 1)
        self.assertEqual(replacement.kind, JournalKind.REPLACEMENT)

    def test_reviewable_opening_import_posts_without_fabricated_history(self) -> None:
        self._activate_posting_policies()
        opening_import = create_opening_import(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            period=self.period,
            source_reference="legacy-trial-balance-2025",
            cutoff_date=date(2025, 12, 31),
            evidence_reference="evidence://legacy/trial-balance",
            reconciliation_reference="reconciliation://legacy/control-total",
        )
        add_opening_import_line(
            organization=self.organization,
            actor=self.owner,
            opening_import=opening_import,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(250),
        )
        add_opening_import_line(
            organization=self.organization,
            actor=self.owner,
            opening_import=opening_import,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(250),
        )
        proposed = submit_opening_import(
            organization=self.organization,
            actor=self.owner,
            opening_import=opening_import,
        )
        with self.assertRaises(PermissionDenied):
            accept_opening_import(
                organization=self.organization,
                actor=self.owner,
                opening_import=proposed,
                reason="self review forbidden",
            )
        journal = accept_opening_import(
            organization=self.organization,
            actor=self.approver,
            opening_import=proposed,
            reason="reconciled to retained control total",
        )
        opening_import.refresh_from_db()
        self.assertEqual(opening_import.status, OpeningImportStatus.ACCEPTED)
        self.assertEqual(opening_import.accepted_journal_id, journal.pk)
        self.assertEqual(journal.source_uuid, opening_import.pk)
        self.assertEqual(journal.cutoff_date, date(2025, 12, 31))
        self.assertEqual(journal.lines.count(), 2)
        source_line_ids = set(opening_import.lines.values_list("pk", flat=True))
        self.assertEqual(
            set(journal.lines.values_list("source_line_uuid", flat=True)),
            source_line_ids,
        )
        report = inspect_manual_opening_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        self.assertEqual(report.posted_count, 1)
        self.assertEqual(report.source_count, 1)
        self.assertEqual(report.debit_total, Decimal(250))
        self.assertEqual(report.credit_total, Decimal(250))
        self.assertEqual(report.exceptions, ())
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        tie_out = run.tie_outs.get()
        self.assertEqual(tie_out.source_uuid, opening_import.pk)
        self.assertEqual(tie_out.source_line_count, 2)
        self.assertEqual(tie_out.journal_line_count, 2)
        self.assertTrue(tie_out.count_matches)
        self.assertTrue(tie_out.amount_matches)
        self.assertTrue(tie_out.exact_line_matches)
        self.assertTrue(tie_out.dimension_matches)
        first_line = journal.lines.order_by("line_number").first()
        assert first_line is not None
        journal.lines.filter(pk=first_line.pk).update(source_line_uuid=uuid.uuid4())
        broken_report = inspect_manual_opening_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        self.assertIn(
            "opening_line_mismatch",
            {item.code for item in broken_report.exceptions},
        )

    def test_reconciliation_is_tenant_scoped_and_requires_view_permission(self) -> None:
        self._posted_journal()
        report = inspect_manual_opening_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        self.assertEqual(report.journal_count, 1)
        self.assertEqual(report.posted_count, 1)
        self.assertEqual(report.exceptions, ())

        viewer = self._member("p2-reconciliation-viewer", MembershipRole.VIEWER)
        with self.assertRaises(PermissionDenied):
            inspect_manual_opening_reconciliation(
                organization=self.other_organization,
                actor=viewer,
                cutoff_date=date(2026, 1, 31),
            )

    def test_retained_reconciliation_run_is_idempotent_and_tenant_scoped(self) -> None:
        self._posted_journal()
        first = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        retried = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        self.assertEqual(retried.pk, first.pk)
        self.assertEqual(first.scope_version, 2)
        self.assertEqual(len(first.scope_hash), 64)
        self.assertEqual(len(first.input_hash), 64)
        self.assertEqual(len(first.result_hash), 64)
        self.assertEqual(first.posted_count, 1)
        self.assertEqual(first.exception_count, 0)
        tie_out = first.tie_outs.get()
        self.assertEqual(tie_out.tie_out_type, ReconciliationTieOutType.OPENING)
        self.assertEqual(tie_out.source_line_count, 2)
        self.assertEqual(tie_out.journal_line_count, 2)
        self.assertEqual(tie_out.source_debit_total, Decimal(100))
        self.assertEqual(tie_out.journal_credit_total, Decimal(100))
        self.assertTrue(tie_out.source_version_matches)
        self.assertTrue(tie_out.exact_line_matches)
        self.assertTrue(tie_out.dimension_matches)
        self.assertEqual(len(tie_out.evidence_hash), 64)
        self.assertEqual(len(tie_out.evidence["lines"]), 2)
        self.assertEqual(
            ReconciliationRun.objects.filter(organization=self.organization).count(),
            1,
        )
        self.assertFalse(
            ReconciliationRun.objects.filter(
                organization=self.other_organization
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.ACCOUNTING_RECONCILIATION_RUN_CREATED,
                entity_id=str(first.pk),
            ).count(),
            1,
        )
        JournalEntry.objects.filter(organization=self.organization).update(
            source_kind="unapproved", event_kind="unapproved"
        )
        bounded = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        self.assertNotEqual(bounded.pk, first.pk)
        self.assertEqual(bounded.source_count, 0)
        self.assertEqual(bounded.journal_count, 0)

    def test_retained_tie_out_flags_source_version_and_exact_line_mismatch(
        self,
    ) -> None:
        posted = self._posted_journal()
        first_line = posted.lines.order_by("line_number").first()
        assert first_line is not None
        JournalEntry.objects.filter(pk=posted.pk).update(source_version=2)
        posted.lines.filter(pk=first_line.pk).update(source_line_uuid=uuid.uuid4())

        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )

        tie_out = run.tie_outs.get()
        self.assertFalse(tie_out.source_version_matches)
        self.assertFalse(tie_out.exact_line_matches)
        self.assertEqual(
            set(run.exceptions.values_list("code", flat=True)),
            {
                "opening_source_version_mismatch",
                "opening_exact_line_mismatch",
            },
        )

    def test_retained_manual_tie_out_preserves_amount_version_and_lines(self) -> None:
        self._activate_posting_policies()
        journal = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 2),
            accounting_date=date(2026, 1, 2),
            description="manual retained tie-out",
            source_key="MANUAL-TIE-OUT-1",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(75),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(75),
        )
        journal = submit_journal(
            organization=self.organization, actor=self.owner, journal=journal
        )
        post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=journal,
            reason="independent manual review",
        )

        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )

        tie_out = run.tie_outs.get()
        self.assertEqual(tie_out.tie_out_type, ReconciliationTieOutType.MANUAL)
        self.assertEqual(tie_out.source_version, 1)
        self.assertEqual(tie_out.source_line_count, 2)
        self.assertEqual(tie_out.source_debit_total, Decimal(75))
        self.assertEqual(tie_out.journal_credit_total, Decimal(75))
        self.assertTrue(tie_out.exact_line_matches)
        self.assertTrue(tie_out.dimension_matches)
        self.assertEqual(run.exception_count, 0)

    def test_retained_correction_chain_ties_reversal_and_replacement(self) -> None:
        posted = self._posted_journal()
        reverse_journal(
            organization=self.organization,
            actor=self.approver,
            original=posted,
            requested_by=self.owner_membership,
            accounting_date=date(2026, 1, 3),
            period=self.period,
            reason="replace proven error",
        )
        replacement = create_replacement_journal(
            organization=self.organization,
            actor=self.owner,
            original=posted,
            period=self.period,
            document_date=date(2026, 1, 4),
            accounting_date=date(2026, 1, 4),
            description="corrected replacement",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=replacement,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(90),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=replacement,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(90),
        )
        replacement = submit_journal(
            organization=self.organization,
            actor=self.owner,
            journal=replacement,
        )
        post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=replacement,
            reason="independent corrected posting",
        )

        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )

        corrections = list(
            run.tie_outs.filter(tie_out_type=ReconciliationTieOutType.CORRECTION)
        )
        self.assertEqual(len(corrections), 2)
        self.assertTrue(all(item.count_matches for item in corrections))
        self.assertTrue(all(item.amount_matches for item in corrections))
        self.assertTrue(all(item.source_version_matches for item in corrections))
        self.assertTrue(all(item.exact_line_matches for item in corrections))
        self.assertTrue(all(item.dimension_matches for item in corrections))
        self.assertTrue(all(item.correction_chain_matches for item in corrections))
        self.assertEqual(run.exception_count, 0)

    def test_retained_exception_snapshot_and_run_are_immutable(self) -> None:
        posted = self._posted_journal()
        JournalEntry.objects.filter(pk=posted.pk).update(
            kind=JournalKind.MANUAL,
            source_kind="manual",
            event_kind="manual_entry",
            source_uuid=uuid.uuid4(),
            cutoff_date=None,
        )
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        self.assertEqual(run.exception_count, 1)
        snapshot = run.exceptions.get()
        self.assertEqual(snapshot.code, "manual_identity_mismatch")
        self.assertEqual(snapshot.organization_id, self.organization.pk)
        run.pending_count = 99
        with self.assertRaises(ValidationError):
            run.save()
        with self.assertRaises(ValidationError):
            run.delete()
        snapshot.code = "rewritten"
        with self.assertRaises(ValidationError):
            snapshot.save()
        with self.assertRaises(ValidationError):
            snapshot.delete()
        self.assertEqual(ReconciliationExceptionSnapshot.objects.count(), 1)
        tie_out = run.tie_outs.get()
        tie_out.evidence_hash = "0" * 64
        with self.assertRaises(ValidationError):
            tie_out.save()
        with self.assertRaises(ValidationError):
            tie_out.delete()
        self.assertEqual(ReconciliationTieOutSnapshot.objects.count(), 1)

    def test_retained_reconciliation_requires_run_permission(self) -> None:
        viewer = self._member(
            "p2-retained-reconciliation-viewer", MembershipRole.VIEWER
        )
        with self.assertRaises(PermissionDenied):
            create_manual_opening_reconciliation_run(
                organization=self.organization,
                actor=viewer,
                cutoff_date=date(2026, 1, 31),
            )
        self.assertFalse(ReconciliationRun.objects.exists())

    def test_reconciliation_exception_disposition_is_immutable_and_idempotent(
        self,
    ) -> None:
        posted = self._posted_journal()
        JournalEntry.objects.filter(pk=posted.pk).update(
            kind=JournalKind.MANUAL,
            source_kind="manual",
            event_kind="manual_entry",
            source_uuid=uuid.uuid4(),
            cutoff_date=None,
        )
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        exception = run.exceptions.get(code="manual_identity_mismatch")
        original_result_hash = run.result_hash
        original_debits = list(posted.lines.values_list("debit", flat=True))

        disposition = dispose_reconciliation_exception(
            organization=self.organization,
            actor=self.owner,
            exception=exception,
            disposition=ReconciliationExceptionDispositionCode.CORRECTION_REQUIRED,
            reason="Source identity requires a separately controlled correction.",
            evidence_reference="evidence://reconciliation/manual-identity",
        )
        retried = dispose_reconciliation_exception(
            organization=self.organization,
            actor=self.owner,
            exception=exception,
            disposition=ReconciliationExceptionDispositionCode.CORRECTION_REQUIRED,
            reason="Source identity requires a separately controlled correction.",
            evidence_reference="evidence://reconciliation/manual-identity",
        )

        self.assertEqual(retried.pk, disposition.pk)
        self.assertEqual(disposition.organization_id, self.organization.pk)
        self.assertEqual(disposition.disposed_by_id, self.owner_membership.pk)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.ACCOUNTING_RECONCILIATION_EXCEPTION_DISPOSED,
                entity_id=str(disposition.pk),
            ).count(),
            1,
        )
        run.refresh_from_db()
        self.assertEqual(run.result_hash, original_result_hash)
        self.assertEqual(
            list(posted.lines.values_list("debit", flat=True)), original_debits
        )
        with self.assertRaises(ValidationError):
            dispose_reconciliation_exception(
                organization=self.organization,
                actor=self.owner,
                exception=exception,
                disposition=ReconciliationExceptionDispositionCode.NOT_APPLICABLE,
                reason="Conflicting second disposition.",
            )
        disposition.reason = "rewrite"
        with self.assertRaises(ValidationError):
            disposition.save()
        with self.assertRaises(ValidationError):
            disposition.delete()

    def test_reconciliation_exception_disposition_requires_reason_and_permission(
        self,
    ) -> None:
        posted = self._posted_journal()
        JournalEntry.objects.filter(pk=posted.pk).update(
            kind=JournalKind.MANUAL,
            source_kind="manual",
            event_kind="manual_entry",
            source_uuid=uuid.uuid4(),
            cutoff_date=None,
        )
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        exception = run.exceptions.get(code="manual_identity_mismatch")
        viewer = self._member("p2-disposition-viewer", MembershipRole.VIEWER)

        with self.assertRaises(PermissionDenied):
            dispose_reconciliation_exception(
                organization=self.organization,
                actor=viewer,
                exception=exception,
                disposition=ReconciliationExceptionDispositionCode.EXPLAINED_VARIANCE,
                reason="Viewer cannot classify this exception.",
            )
        with self.assertRaises(ValidationError):
            dispose_reconciliation_exception(
                organization=self.organization,
                actor=self.owner,
                exception=exception,
                disposition=ReconciliationExceptionDispositionCode.EXPLAINED_VARIANCE,
                reason=" ",
            )
        with self.assertRaises(PermissionDenied):
            dispose_reconciliation_exception(
                organization=self.other_organization,
                actor=self.other_owner,
                exception=exception,
                disposition=ReconciliationExceptionDispositionCode.NOT_APPLICABLE,
                reason="Cross-Tenant disposition must fail.",
            )
        self.assertFalse(ReconciliationExceptionDisposition.objects.exists())

    def test_reconciliation_sign_off_is_independent_immutable_and_idempotent(
        self,
    ) -> None:
        posted = self._posted_journal()
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        original_lines = list(
            posted.lines.order_by("line_number").values_list("debit", "credit")
        )

        review = sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.approver,
            run=run,
            reason="Independent review confirmed the retained tie-out evidence.",
        )
        retried = sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.approver,
            run=run,
            reason="Independent review confirmed the retained tie-out evidence.",
        )

        self.assertEqual(retried.pk, review.pk)
        self.assertEqual(review.reviewed_by.user_id, self.approver.pk)
        self.assertEqual(review.scope_hash, run.scope_hash)
        self.assertEqual(review.input_hash, run.input_hash)
        self.assertEqual(review.result_hash, run.result_hash)
        self.assertEqual(len(review.disposition_hash), 64)
        self.assertEqual(len(review.signed_evidence_hash), 64)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.ACCOUNTING_RECONCILIATION_SIGNED_OFF,
                entity_id=str(review.pk),
            ).count(),
            1,
        )
        self.assertEqual(
            list(posted.lines.order_by("line_number").values_list("debit", "credit")),
            original_lines,
        )
        review.reason = "rewrite"
        with self.assertRaises(ValidationError):
            review.save()
        with self.assertRaises(ValidationError):
            review.delete()

    def test_reconciliation_empty_totals_survive_database_round_trip(self) -> None:
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=self.period.ends_on,
        )
        original_hash = run.result_hash
        run.refresh_from_db()
        review = sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.approver,
            run=run,
            reason="Verify retained zero totals after database reload.",
        )
        self.assertEqual(run.source_count, 0)
        self.assertEqual(run.result_hash, original_hash)
        self.assertEqual(
            verify_signed_reconciliation_run(
                organization=self.organization, run=run
            ).pk,
            review.pk,
        )

    def test_reconciliation_nonempty_result_with_pending_empty_sources(self) -> None:
        posted = self._posted_journal()
        create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind=JournalKind.MANUAL,
            document_date=self.period.starts_on,
            accounting_date=self.period.starts_on,
            description="Pending empty source alongside posted balances",
            source_key="PENDING-EMPTY-RECONCILIATION",
        )
        create_opening_import(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            period=self.period,
            source_reference="PENDING-EMPTY-OPENING",
            cutoff_date=date(2025, 12, 31),
            evidence_reference="evidence://pending-opening",
            reconciliation_reference="reconciliation://pending-opening",
        )
        original_lines = list(posted.lines.values_list("debit", "credit"))
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=self.period.ends_on,
        )
        original_hash = run.result_hash
        run.refresh_from_db()
        review = sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.approver,
            run=run,
            reason="Verify nonempty cutoff with pending empty sources.",
        )
        self.assertEqual(
            (run.source_count, run.posted_count, run.pending_count), (3, 1, 2)
        )
        self.assertEqual(run.exception_count, 0)
        self.assertEqual(run.debit_total, Decimal(100))
        self.assertEqual(run.credit_total, Decimal(100))
        self.assertEqual(run.result_hash, original_hash)
        self.assertEqual(
            verify_signed_reconciliation_run(
                organization=self.organization, run=run
            ).pk,
            review.pk,
        )
        self.assertEqual(
            list(posted.lines.values_list("debit", "credit")), original_lines
        )
        empty_tie_out = run.tie_outs.get(tie_out_type=ReconciliationTieOutType.MANUAL)
        ReconciliationTieOutSnapshot.objects.filter(pk=empty_tie_out.pk).update(
            journal_debit_total=Decimal(1)
        )
        with self.assertRaisesMessage(ValidationError, "دستکاری شده است"):
            verify_signed_reconciliation_run(organization=self.organization, run=run)

    def test_reconciliation_sign_off_requires_permission_reason_dispositions_and_sod(
        self,
    ) -> None:
        posted = self._posted_journal()
        JournalEntry.objects.filter(pk=posted.pk).update(
            kind=JournalKind.MANUAL,
            source_kind="manual",
            event_kind="manual_entry",
            source_uuid=uuid.uuid4(),
            cutoff_date=None,
        )
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        exception = run.exceptions.get(code="manual_identity_mismatch")
        viewer = self._member("p2-sign-off-viewer", MembershipRole.VIEWER)

        with self.assertRaises(PermissionDenied):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=viewer,
                run=run,
                reason="Viewer has no sign-off authority.",
            )
        with self.assertRaises(PermissionDenied):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=self.owner,
                run=run,
                reason="Run creator cannot self-approve.",
            )
        with self.assertRaises(ValidationError):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=self.approver,
                run=run,
                reason="Undisposed exception must fail closed.",
            )
        dispose_reconciliation_exception(
            organization=self.organization,
            actor=self.approver,
            exception=exception,
            disposition=ReconciliationExceptionDispositionCode.CORRECTION_REQUIRED,
            reason="Correction remains separately controlled.",
        )
        with self.assertRaises(PermissionDenied):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=self.approver,
                run=run,
                reason="Disposer cannot sign the same evidence.",
            )
        independent = self._member("p2-independent-reviewer", MembershipRole.ACCOUNTANT)
        with self.assertRaises(ValidationError):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=independent,
                run=run,
                reason=" ",
            )
        review = sign_off_reconciliation_run(
            organization=self.organization,
            actor=independent,
            run=run,
            reason="Independent reviewer accepted the reasoned disposition.",
        )
        self.assertEqual(review.organization_id, self.organization.pk)
        with self.assertRaises(PermissionDenied):
            sign_off_reconciliation_run(
                organization=self.other_organization,
                actor=self.other_owner,
                run=run,
                reason="Cross-Tenant sign-off must fail.",
            )

    def test_reconciliation_sign_off_detects_retained_evidence_tampering(self) -> None:
        self._posted_journal()
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        original_input_hash = run.input_hash
        ReconciliationRun.objects.filter(pk=run.pk).update(input_hash="0" * 64)
        run.refresh_from_db()
        with self.assertRaises(ValidationError):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=self.approver,
                run=run,
                reason="Tampered input evidence must fail closed.",
            )
        ReconciliationRun.objects.filter(pk=run.pk).update(
            input_hash=original_input_hash
        )
        tie_out = run.tie_outs.get()
        ReconciliationTieOutSnapshot.objects.filter(pk=tie_out.pk).update(
            evidence_hash="f" * 64
        )
        run.refresh_from_db()
        with self.assertRaises(ValidationError):
            sign_off_reconciliation_run(
                organization=self.organization,
                actor=self.approver,
                run=run,
                reason="Tampered tie-out evidence must fail closed.",
            )
        self.assertFalse(ReconciliationReview.objects.exists())

    def test_reconciliation_cutoff_is_stable_when_later_facts_are_added(self) -> None:
        self._posted_journal()
        cutoff = date(2026, 1, 15)
        first = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=cutoff,
        )
        create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 20),
            accounting_date=date(2026, 1, 20),
            description="Fact after retained reconciliation cutoff",
            source_key="AFTER-CUTOFF",
        )
        retried = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=cutoff,
        )
        self.assertEqual(retried.pk, first.pk)
        self.assertEqual(retried.input_hash, first.input_hash)

    def test_posting_account_must_remain_a_leaf(self) -> None:
        with self.assertRaises(ValidationError):
            create_account(
                organization=self.organization,
                actor=self.owner,
                code="1101",
                name="invalid child",
                account_type=AccountType.ASSET,
                parent=self.debit_account,
            )
        parent = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1200",
            name="parent",
            account_type=AccountType.ASSET,
        )
        create_account(
            organization=self.organization,
            actor=self.owner,
            code="1210",
            name="child",
            account_type=AccountType.ASSET,
            parent=parent,
        )
        parent.is_posting = True
        with self.assertRaises(ValidationError):
            parent.save()
        self.assertFalse(Account.objects.get(pk=parent.pk).is_posting)


class AccountingTenantUiTests(TestCase):
    """Focused request-level checks for the S23--S27 tenant surface."""

    setUp = AccountingFoundationTests.setUp
    _member = AccountingFoundationTests._member
    _journal = AccountingFoundationTests._journal
    _activate_accounting_policy = AccountingFoundationTests._activate_accounting_policy
    _activate_posting_policies = AccountingFoundationTests._activate_posting_policies
    _posted_journal = AccountingFoundationTests._posted_journal

    def _activate_client(self, user: User, organization=None) -> None:
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str((organization or self.organization).pk)
        session.save()

    def test_accounting_dashboard_and_manual_detail_are_tenant_scoped(self) -> None:
        journal = self._journal()
        self._activate_client(self.owner)

        self.assertEqual(
            self.client.get(reverse("accounting:dashboard")).status_code, 200
        )
        response = self.client.get(
            reverse("accounting:journal_detail", args=[journal.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ردیف‌های سند")

        other_journal = create_journal(
            organization=self.other_organization,
            actor=self.other_owner,
            period=create_fiscal_period(
                organization=self.other_organization,
                actor=self.other_owner,
                fiscal_year=create_fiscal_year(
                    organization=self.other_organization,
                    actor=self.other_owner,
                    code="OTHER-FY",
                    name="Other FY",
                    starts_on=date(2026, 1, 1),
                    ends_on=date(2026, 12, 31),
                    calendar_version=1,
                ),
                number=1,
                name="Other period",
                starts_on=date(2026, 1, 1),
                ends_on=date(2026, 1, 31),
            ),
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 1),
            accounting_date=date(2026, 1, 1),
            description="Other tenant journal",
            source_key="OTHER-UI-1",
        )
        self.assertEqual(
            self.client.get(
                reverse("accounting:journal_detail", args=[other_journal.pk])
            ).status_code,
            404,
        )

    def test_chart_of_accounts_is_a_tenant_scoped_expandable_tree(self) -> None:
        root = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1000",
            name="دارایی‌ها",
            account_type=AccountType.ASSET,
        )
        group = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1010",
            name="دارایی‌های جاری",
            account_type=AccountType.ASSET,
            parent=root,
        )
        leaf = create_account(
            organization=self.organization,
            actor=self.owner,
            code="1011",
            name="صندوق",
            account_type=AccountType.ASSET,
            parent=group,
            is_posting=True,
        )
        create_account(
            organization=self.other_organization,
            actor=self.other_owner,
            code="9999",
            name="حساب سایر مستأجران",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        self._activate_client(self.owner)

        response = self.client.get(reverse("accounting:account_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="درخت کدینگ حساب‌ها"', html=False)
        self.assertContains(response, f'data-account-id="{root.pk}"', html=False)
        self.assertContains(response, f'data-account-id="{group.pk}"', html=False)
        self.assertContains(response, f'data-account-id="{leaf.pk}"', html=False)
        self.assertContains(response, 'class="account-tree-node" open', html=False)
        self.assertContains(response, "data-account-tree", html=False)
        self.assertContains(response, "data-tree-toggle", html=False)
        self.assertContains(
            response, 'details.addEventListener("toggle", sync)', html=False
        )
        self.assertNotContains(response, "حساب سایر مستأجران")
        tree = response.context["account_tree"]
        asset_root = next(node for node in tree if node.account.pk == root.pk)
        self.assertEqual(asset_root.children[0].account.pk, group.pk)
        self.assertEqual(asset_root.children[0].children[0].account.pk, leaf.pk)

    def test_posted_journal_detail_hides_edit_surface_and_source_drillthrough(
        self,
    ) -> None:
        posted = self._posted_journal()
        self._activate_client(self.owner)

        detail = self.client.get(reverse("accounting:journal_detail", args=[posted.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "افزودن ردیف")
        drillthrough = self.client.get(
            reverse("accounting:journal_source", args=[posted.pk])
        )
        self.assertEqual(drillthrough.status_code, 200)
        self.assertContains(drillthrough, str(posted.source_uuid))

    def test_suspended_tenant_and_missing_permission_fail_closed(self) -> None:
        self._activate_client(self.owner)
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status", "updated_at"])
        self.assertEqual(
            self.client.get(reverse("accounting:dashboard")).status_code, 403
        )

        self.organization.status = "active"
        self.organization.save(update_fields=["status", "updated_at"])
        viewer = self._member("p2-ui-viewer", MembershipRole.VIEWER)
        self._activate_client(viewer)
        self.assertEqual(
            self.client.get(reverse("accounting:journal_create")).status_code, 403
        )


class AccountingPostingConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics are required.")
        self.owner = User.objects.create_user(username="p2-race-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="P2 Race Tenant", slug="p2-race-tenant"
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.approver = User.objects.create_user(
            username="p2-race-approver", password="x"
        )
        role = OrganizationRole.objects.get(
            code=MembershipRole.ACCOUNTANT, organization__isnull=True
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.approver,
            role=MembershipRole.ACCOUNTANT,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="P2 race test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P2 race test",
        )
        self._activate_policy(
            ACCOUNTING_PRECISION_POLICY_CODE, PolicyCategory.PRECISION
        )
        self._activate_policy(ACCOUNTING_ROUNDING_POLICY_CODE, PolicyCategory.ROUNDING)
        fiscal_year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-RACE",
            name="race year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=fiscal_year,
            number=1,
            name="race period",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        debit = create_account(
            organization=self.organization,
            actor=self.owner,
            code="R1100",
            name="race debit",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        credit = create_account(
            organization=self.organization,
            actor=self.owner,
            code="R3100",
            name="race credit",
            account_type=AccountType.EQUITY,
            is_posting=True,
        )
        journal = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 2),
            accounting_date=date(2026, 1, 2),
            description="concurrent post",
            source_key="RACE-POST",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=debit,
            line_number=1,
            debit=Decimal(10),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=credit,
            line_number=2,
            credit=Decimal(10),
        )
        self.journal = submit_journal(
            organization=self.organization, actor=self.owner, journal=journal
        )

    def _activate_policy(self, code: str, category: str) -> None:
        spec = get_platform_policy_spec(code)
        policy = PlatformPolicy.objects.create(
            code=code,
            name=spec.name,
            category=category,
            sensitivity=spec.sensitivity,
            tenant_selectable=spec.tenant_selectable,
            requires_source_provenance=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=1,
            parameters=initial_accounting_policy_parameters(code),
            effective_from=timezone.localdate(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            created_by=self.owner,
            published_by=self.owner,
            published_at=timezone.now(),
            reason="P2 race policy",
        )
        TenantPolicySelection.objects.create(
            organization=self.organization,
            policy=policy,
            policy_version=version,
            status=TenantPolicySelectionStatus.ACTIVE,
            approved_by=self.owner_membership,
            approved_at=timezone.now(),
            applied_by=self.owner_membership,
            applied_at=timezone.now(),
            reason="P2 race activation",
        )

    def test_concurrent_identical_post_returns_one_numbered_journal(self) -> None:
        barrier = Barrier(2)
        results: Queue[object] = Queue()

        def runner() -> None:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = post_journal(
                    organization=type(self.organization).objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.approver.pk),
                    journal=JournalEntry.objects.get(pk=self.journal.pk),
                    reason="concurrent retry",
                )
                results.put(result.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(runner) for _ in range(2)]
            for future in futures:
                future.result(timeout=30)

        outcomes = [results.get_nowait(), results.get_nowait()]
        self.assertEqual(outcomes, [self.journal.pk, self.journal.pk])
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.number, 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.ACCOUNTING_JOURNAL_POSTED,
                entity_id=str(self.journal.pk),
            ).count(),
            1,
        )

    def test_concurrent_reconciliation_run_and_sign_off_are_idempotent(self) -> None:
        post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=self.journal,
            reason="post before concurrent reconciliation",
        )
        barrier = Barrier(2)
        run_results: Queue[object] = Queue()

        def create_run() -> None:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = create_manual_opening_reconciliation_run(
                    organization=type(self.organization).objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.owner.pk),
                    cutoff_date=date(2026, 1, 31),
                )
                run_results.put(result.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_run) for _ in range(2)]
            for future in futures:
                future.result(timeout=30)

        run_outcomes = [run_results.get_nowait(), run_results.get_nowait()]
        self.assertEqual(run_outcomes[0], run_outcomes[1])
        run = ReconciliationRun.objects.get(pk=run_outcomes[0])
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_RECONCILIATION_RUN_CREATED,
                entity_id=str(run.pk),
            ).count(),
            1,
        )

        sign_barrier = Barrier(2)
        review_results: Queue[object] = Queue()

        def sign_run() -> None:
            close_old_connections()
            try:
                sign_barrier.wait(timeout=10)
                result = sign_off_reconciliation_run(
                    organization=type(self.organization).objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.approver.pk),
                    run=ReconciliationRun.objects.get(pk=run.pk),
                    reason="concurrent independent reconciliation review",
                )
                review_results.put(result.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(sign_run) for _ in range(2)]
            for future in futures:
                future.result(timeout=30)

        review_outcomes = [review_results.get_nowait(), review_results.get_nowait()]
        self.assertEqual(review_outcomes[0], review_outcomes[1])
        self.assertEqual(ReconciliationReview.objects.filter(run=run).count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_RECONCILIATION_SIGNED_OFF,
                entity_id=str(review_outcomes[0]),
            ).count(),
            1,
        )
