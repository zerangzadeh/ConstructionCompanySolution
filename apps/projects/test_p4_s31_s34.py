from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.expenses.services import (
    add_expense_allocation,
    approve_expense,
    create_expense_draft,
    submit_expense,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects import test_p4_budget_preparation as budget_helpers
from apps.projects.services import (
    create_project,
    export_project_control_snapshot,
    get_project_control_comparison,
    get_project_control_exceptions,
)


class ProjectControlPresentationTests(TestCase):
    _draft = budget_helpers.BudgetPreparationTests._draft
    _classify_and_submit = budget_helpers.BudgetPreparationTests._classify_and_submit

    def setUp(self) -> None:
        budget_helpers.BudgetPreparationTests.setUp(self)
        self.budget = self._classify_and_submit(self._draft())
        from apps.projects.services import accept_budget_version

        self.budget = accept_budget_version(
            budget=self.budget,
            actor=self.approver,
            approval_reason="Independent acceptance for P4-S31–S34",
        )

    def _approved_expense(self, *, amount: str, key: str, source: str):
        expense = create_expense_draft(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            description="Controlled expense evidence",
            amount=Decimal(amount),
            incurred_on=date(2026, 10, 1),
            source_reference=source,
            idempotency_key=key,
        )
        add_expense_allocation(
            expense=expense,
            actor=self.preparer,
            project=self.project,
            wbs_node=self.wbs,
            cbs_node=self.cbs,
            cost_center=self.cost_center,
            amount=Decimal(amount),
            allocation_basis_reference="P4-S31 comparison evidence",
        )
        submit_expense(expense=expense, actor=self.preparer)
        approve_expense(expense=expense, actor=self.approver)
        return expense

    def test_comparison_is_same_budget_scoped_and_does_not_activate_cost_producers(self) -> None:
        self._approved_expense(amount="60.00", key="p4-s31-1", source="INV-S31-1")
        comparison = get_project_control_comparison(
            organization=self.organization, project=self.project, actor=self.preparer
        )
        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.currency, "IRR")
        self.assertEqual(len(comparison.lines), 1)
        self.assertEqual(comparison.lines[0].accepted_budget_amount, Decimal("100.00"))
        self.assertEqual(
            comparison.lines[0].approved_or_recorded_expense_amount, Decimal("60.00")
        )
        self.assertEqual(comparison.lines[0].remaining_amount, Decimal("40.00"))
        with self.assertRaises(PermissionDenied):
            get_project_control_comparison(
                organization=self.other_organization,
                project=self.project,
                actor=self.outsider,
            )

    def test_exceptions_are_advisory_and_export_is_scoped_and_audited(self) -> None:
        self._approved_expense(amount="120.00", key="p4-s34-1", source="INV-S34-1")
        snapshot = get_project_control_exceptions(
            organization=self.organization, project=self.project, actor=self.preparer
        )
        self.assertEqual(len(snapshot.advisory_overruns), 1)
        self.assertEqual(snapshot.advisory_overruns[0].control_mode, "advisory_only")
        payload = export_project_control_snapshot(
            organization=self.organization, project=self.project, actor=self.preparer
        )
        self.assertIn(b"accepted_budget_vs_expense", payload)
        self.assertIn(b"advisory_overrun_evidence", payload)
        audit = AuditEvent.objects.get(action=AuditAction.PROJECT_CONTROLS_EXPORTED)
        self.assertEqual(audit.organization, self.organization)
        self.assertEqual(audit.metadata["project_id"], str(self.project.pk))
        self.assertNotIn(b"INV-S34-1", payload)

    def test_http_permissions_and_cross_tenant_export_are_denied(self) -> None:
        self.client.force_login(self.preparer)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("projects:controls_comparison", args=[self.project.pk])
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            reverse("projects:controls_export", args=[self.project.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

        self.client.force_login(self.outsider)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.other_organization.pk)
        session.save()
        response = self.client.get(
            reverse("projects:controls_export", args=[self.project.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_controls_panel_is_visible_with_base_controls_view_only(self) -> None:
        manager = User.objects.create_user(username="p4-controls-view-only")
        self.organization.memberships.create(
            user=manager,
            role=MembershipRole.PROJECT_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.client.force_login(manager)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

        response = self.client.get(
            reverse("projects:controls", args=[self.project.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "شواهد محدود کنترل پروژه")
        self.assertContains(response, "برای مشاهدهٔ این شواهد")
        self.assertNotContains(response, "مشاهده انحرافات بودجه‌ای")

    def test_reconciliation_ui_renders_budget_dimensions_and_localized_variance_label(
        self,
    ) -> None:
        self.client.force_login(self.preparer)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

        controls_response = self.client.get(
            reverse("projects:controls", args=[self.project.pk])
        )
        self.assertContains(controls_response, "مشاهده انحرافات بودجه‌ای")
        self.assertNotContains(controls_response, "استثناهای محدود")

        exceptions_response = self.client.get(
            reverse("projects:controls_exceptions", args=[self.project.pk])
        )
        self.assertContains(exceptions_response, "انحرافات بودجه‌ای کنترل پروژه")
        self.assertContains(exceptions_response, "شواهد انحراف بودجه")

        reconciliation_response = self.client.get(
            reverse("projects:cost_reconciliation", args=[self.project.pk])
        )
        for heading in (
            "CBS",
            "WBS",
            "مرکز هزینه",
            "بودجه",
            "هزینه تأیید/ثبت‌شده",
            "فکت غیرفعال هزینه واقعی",
            "اختلاف حل‌نشده",
            "منابع و پوشش",
            "شواهد حذف‌شده یا غیرقابل‌مقایسه",
        ):
            self.assertContains(reconciliation_response, heading)

    def test_project_scope_cannot_read_another_project_control_export(self) -> None:
        scoped_user = self.preparer.__class__.objects.create_user(
            username="p4-s31-project-scoped"
        )
        membership = self.organization.memberships.create(
            user=scoped_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="P4-S31 test project scope",
        )
        other_project = create_project(
            organization=self.organization,
            actor=self.preparer,
            code="P4-S31-OTHER",
            name="Out-of-scope project",
        )
        self.assertIsNotNone(
            get_project_control_comparison(
                organization=self.organization, project=self.project, actor=scoped_user
            )
        )
        with self.assertRaises(PermissionDenied):
            export_project_control_snapshot(
                organization=self.organization, project=other_project, actor=scoped_user
            )
