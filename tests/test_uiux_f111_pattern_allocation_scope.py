"""BATCH-06 allocation choices and the existing financial validation boundary."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.estimates.services import add_estimate_item, approve_estimate, create_estimate
from apps.expenses.forms import ExpenseAllocationForm
from apps.expenses.models import Expense, ExpenseAllocation, PlatformExpenseGroup
from apps.expenses.services import add_expense_allocation, create_expense_draft
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Activity, Project, ProjectSite, WBSNode
from apps.projects.services import (
    BudgetAllocationInput,
    accept_budget_version,
    add_cbs_node,
    add_cost_center,
    classify_budget_manifest_line,
    create_activity,
    create_budget_draft_from_estimate,
    create_cost_structure_version,
    create_wbs_node,
    lock_cost_structure_version,
    submit_budget_version,
)


def canonical_coding(*, organization, project, actor, approver, key):
    """Synthetic coding through existing services, also reused by live preparation."""
    wbs = create_wbs_node(
        organization=organization,
        project=project,
        actor=actor,
        code=f"B06-W-{key}",
        title=f"B06 synthetic WBS {key}",
    )
    activity = create_activity(
        organization=organization,
        project=project,
        wbs_node=wbs,
        actor=actor,
        code=f"B06-A-{key}",
        name=f"B06 synthetic Activity {key}",
    )
    structure = create_cost_structure_version(
        organization=organization,
        actor=actor,
        code=f"B06-S-{key}",
        version=1,
        name=f"B06 synthetic structure {key}",
        governance_reference="B06-DEV-ONLY",
    )
    cbs = add_cbs_node(
        structure=structure, actor=actor, code="C1", name="Synthetic direct"
    )
    center = add_cost_center(
        structure=structure, actor=actor, code="CC1", name="Synthetic center"
    )
    lock_cost_structure_version(structure=structure, actor=actor)
    estimate = create_estimate(
        organization=organization,
        project=project,
        actor=actor,
        estimate_number=f"B06-E-{key}",
        title=f"B06 synthetic estimate {key}",
    )
    add_estimate_item(
        estimate=estimate,
        actor=actor,
        description="Synthetic source",
        quantity=Decimal(1),
        unit_price=Decimal(100),
    )
    approve_estimate(estimate=estimate, actor=actor)
    estimate.refresh_from_db()
    budget = create_budget_draft_from_estimate(
        organization=organization,
        project=project,
        actor=actor,
        estimate_revision=estimate.current_revision,
        structure=structure,
        handoff_id=f"B06-H-{key}",
        submission_version=1,
        governance_reference="B06-DEV-ONLY",
        rounding_policy_reference="IRR-DECIMAL-2",
        cost_center_required=True,
        reason="Synthetic Development selector control",
    )
    classify_budget_manifest_line(
        line=budget.source_manifest.lines.get(),
        actor=actor,
        allocations=(
            BudgetAllocationInput(
                amount=Decimal(100),
                cbs_node=cbs,
                wbs_node=wbs,
                cost_center=center,
                allocation_basis_reference="Synthetic mapping",
            ),
        ),
    )
    budget = submit_budget_version(budget=budget, actor=actor)
    budget = accept_budget_version(
        budget=budget,
        actor=approver,
        approval_reason="Independent synthetic Development acceptance",
    )
    return {
        "project": project,
        "wbs_node": wbs,
        "activity": activity,
        "cbs_node": cbs,
        "cost_center": center,
        "budget": budget,
    }


class AllocationScopeTests(TestCase):
    @classmethod
    def member(cls, user, org, role="company_owner", scope=False):
        m = OrganizationMembership.objects.create(
            organization=org,
            user=user,
            role=role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=org,
            membership=m,
            role=OrganizationRole.objects.get(code=role),
            reason="Disposable B06",
        )
        if scope:
            MembershipScopeGrant.objects.create(
                organization=org,
                membership=m,
                scope_type="organization",
                reason="Disposable B06",
            )
        return m

    @classmethod
    def setUpTestData(cls):
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "Other"}
        )
        cls.org = Organization.objects.create(name="B06 tenant", slug="b06")
        cls.other = Organization.objects.create(name="B06 other", slug="b06-x")
        OrganizationSettings.objects.create(organization=cls.org, currency="IRR")
        OrganizationSettings.objects.create(organization=cls.other, currency="IRR")
        cls.owner = User.objects.create_user(username="b06-owner")
        cls.approver = User.objects.create_user(username="b06-approver")
        cls.foreign = User.objects.create_user(username="b06-foreign")
        cls.foreign_approver = User.objects.create_user(username="b06-foreign-approver")
        cls.user = User.objects.create_user(username="b06-limited")
        cls.site_user = User.objects.create_user(username="b06-site")
        cls.viewer = User.objects.create_user(username="b06-viewer")
        cls.owner_member = cls.member(cls.owner, cls.org, scope=True)
        cls.member(cls.approver, cls.org, scope=True)
        cls.foreign_member = cls.member(cls.foreign, cls.other, scope=True)
        cls.member(cls.foreign_approver, cls.other, scope=True)
        cls.limited = cls.member(cls.user, cls.org, "project_manager")
        cls.site_member = cls.member(cls.site_user, cls.org, "operations_manager")
        cls.viewer_member = cls.member(cls.viewer, cls.org, "viewer", scope=True)
        cls.sources = {}
        for key in "ABCDX":
            org, actor, approver = (
                (cls.other, cls.foreign, cls.foreign_approver)
                if key == "X"
                else (cls.org, cls.owner, cls.approver)
            )
            project = Project.objects.create(
                organization=org,
                code=f"B06-P-{key}",
                name=f"B06 distinct Project {key}",
            )
            cls.sources[key] = canonical_coding(
                organization=org,
                project=project,
                actor=actor,
                approver=approver,
                key=key,
            )
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=org,
                    membership=cls.limited,
                    scope_type="project",
                    project=project,
                    reason="Disposable A/B",
                )
        site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.sources["A"]["project"],
            code="B06-SITE",
            name="B06 site",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.site_member,
            scope_type="site",
            site=site,
            project=site.project,
            reason="Disposable site",
        )
        cls.expense = create_expense_draft(
            organization=cls.org,
            project=cls.sources["A"]["project"],
            actor=cls.owner,
            description="B06 synthetic parent",
            amount=Decimal(60),
            incurred_on=date(2026, 10, 22),
            source_reference="B06-INVOICE",
            idempotency_key="B06-draft",
        )

    def setUp(self):
        self.login(self.user)

    def login(self, actor):
        self.client.force_login(actor)
        s = self.client.session
        s[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        s.save()

    def form(self, data=None, membership="default", **kwargs):
        return ExpenseAllocationForm(
            data=data,
            organization=self.org,
            membership=self.limited if membership == "default" else membership,
            expense=self.expense,
            **kwargs,
        )

    def payload(self, key="B"):
        return {
            f: str(self.sources[key][f].pk)
            for f in ("project", "wbs_node", "activity", "cbs_node", "cost_center")
        } | {"amount": "10.00", "allocation_basis_reference": "B06 synthetic split"}

    def counts(self):
        return ExpenseAllocation.objects.count(), AuditEvent.objects.count()

    def detail(self, keys="AB"):
        response = self.client.get(reverse("expenses:detail", args=[self.expense.pk]))
        self.assertEqual(response.status_code, 200)
        form = response.context["allocation_form"]
        for field in ("project", "wbs_node", "activity"):
            self.assertSetEqual(
                set(form.fields[field].queryset.values_list("pk", flat=True)),
                {self.sources[k][field].pk for k in keys},
            )
            for key in (k for k in "ABCDX" if k not in keys):
                for token in (
                    str(self.sources[key][field].pk),
                    str(self.sources[key][field]),
                ):
                    self.assertNotContains(response, token)
        return response

    def test_get_authorized_projects_and_all_children_with_tenant_masters(self):
        response = self.detail()
        for field in ("cbs_node", "cost_center"):
            self.assertSetEqual(
                set(
                    response.context["allocation_form"]
                    .fields[field]
                    .queryset.values_list("pk", flat=True)
                ),
                {self.sources[k][field].pk for k in "ABCD"},
            )
        self.login(self.owner)
        self.detail("ABCD")

    def test_missing_invalid_membership_and_effective_grant_states_fail_closed(self):
        for m in (None, object(), self.foreign_member):
            with self.subTest(member=str(m)):
                for f in ("project", "wbs_node", "activity"):
                    self.assertFalse(
                        self.form(membership=m).fields[f].queryset.exists()
                    )
        unscoped_user = User.objects.create_user(username="b06-unscoped")
        unscoped = self.member(unscoped_user, self.org, "project_manager")
        for field in ("project", "wbs_node", "activity"):
            self.assertFalse(
                self.form(membership=unscoped).fields[field].queryset.exists()
            )
        for state in ("revoked", "expired", "future"):
            with self.subTest(state=state):
                grants = MembershipScopeGrant.objects.filter(membership=self.limited)
                grants.update(
                    revoked_at=None,
                    starts_at=timezone.now() - timedelta(days=2),
                    ends_at=None,
                )
                if state == "revoked":
                    grants.update(revoked_at=timezone.now())
                elif state == "expired":
                    grants.update(ends_at=timezone.now() - timedelta(days=1))
                else:
                    grants.update(starts_at=timezone.now() + timedelta(days=1))
                for field in ("project", "wbs_node", "activity"):
                    self.assertFalse(self.form().fields[field].queryset.exists())

    def test_inactive_membership_user_tenant_fail_closed(self):
        for obj, field, value in (
            (self.limited, "status", "suspended"),
            (self.user, "is_active", False),
            (self.org, "status", "suspended"),
        ):
            with self.subTest(field=field):
                original = getattr(obj, field)
                setattr(obj, field, value)
                obj.save()
                for f in ("project", "wbs_node", "activity"):
                    self.assertFalse(self.form().fields[f].queryset.exists())
                setattr(obj, field, original)
                obj.save()

    def test_site_only_does_not_promote_parent_authority(self):
        form = self.form(membership=self.site_member)
        for f in ("project", "wbs_node", "activity"):
            self.assertFalse(form.fields[f].queryset.exists())
        self.login(self.site_user)
        self.assertEqual(
            self.client.get(
                reverse("expenses:detail", args=[self.expense.pk])
            ).status_code,
            404,
        )

    def test_unauthorized_forced_ids_bare_400_then_safe_get_no_mutation(self):
        before = self.counts()
        for key in "CDX":
            for f in ("project", "wbs_node", "activity"):
                with self.subTest(source=key, field=f):
                    data = (
                        self.payload(key)
                        if f == "project"
                        else self.payload() | {f: str(self.sources[key][f].pk)}
                    )
                    form = self.form(data)
                    self.assertFalse(form.is_valid())
                    self.assertIn(f, form.errors)
                    response = self.client.post(
                        reverse("expenses:allocate", args=[self.expense.pk]), data
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.content, b"")
                    self.detail()
                    self.assertEqual(before, self.counts())

    def test_authorized_cross_project_and_same_project_wrong_wbs_rejected(self):
        before = self.counts()
        extra = create_wbs_node(
            organization=self.org,
            project=self.sources["B"]["project"],
            actor=self.owner,
            code="B06-W2",
            title="B06 sibling WBS",
        )
        before = self.counts()
        for patch in (
            {"wbs_node": str(self.sources["A"]["wbs_node"].pk)},
            {"activity": str(self.sources["A"]["activity"].pk)},
            {"wbs_node": str(extra.pk)},
        ):
            with self.subTest(patch=patch):
                response = self.client.post(
                    reverse("expenses:allocate", args=[self.expense.pk]),
                    self.payload() | patch,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.content, b"")
                self.assertEqual(before, self.counts())

    def test_missing_required_and_malformed_values_fail_safely(self):
        before = self.counts()
        for field in ("project", "wbs_node", "amount", "allocation_basis_reference"):
            with self.subTest(field=field):
                data = self.payload()
                data.pop(field)
                self.assertEqual(
                    self.client.post(
                        reverse("expenses:allocate", args=[self.expense.pk]), data
                    ).status_code,
                    400,
                )
        for field in ("project", "wbs_node", "activity"):
            with self.subTest(malformed=field):
                self.assertFalse(
                    self.form(self.payload() | {field: "not-a-uuid"}).is_valid()
                )
        self.assertEqual(before, self.counts())

    def test_authorized_multi_project_allocation_uses_existing_model_and_service(self):
        form = self.form(self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        response = self.client.post(
            reverse("expenses:allocate", args=[self.expense.pk]), self.payload()
        )
        self.assertEqual(response.status_code, 302)
        allocation = ExpenseAllocation.objects.get(expense=self.expense)
        self.assertEqual(allocation.project_id, self.sources["B"]["project"].pk)
        self.assertNotEqual(allocation.project_id, self.expense.project_id)
        self.assertEqual(allocation.governing_budget_id, self.sources["B"]["budget"].pk)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.EXPENSE_ALLOCATION_ADDED, entity_id=self.expense.pk
            ).count(),
            1,
        )

    def test_existing_budget_structure_amount_and_status_guards(self):
        before = self.counts()
        for patch in (
            {"cbs_node": str(self.sources["A"]["cbs_node"].pk)},
            {"cost_center": str(self.sources["A"]["cost_center"].pk)},
            {"amount": "61"},
            {"amount": "0"},
            {"cost_center": ""},
        ):
            with self.subTest(patch=patch):
                self.assertEqual(
                    self.client.post(
                        reverse("expenses:allocate", args=[self.expense.pk]),
                        self.payload() | patch,
                    ).status_code,
                    400,
                )
        self.assertEqual(before, self.counts())
        Expense.objects.filter(pk=self.expense.pk).update(status="returned")
        self.detail()
        self.assertEqual(
            self.client.post(
                reverse("expenses:allocate", args=[self.expense.pk]), self.payload()
            ).status_code,
            302,
        )
        Expense.objects.filter(pk=self.expense.pk).update(status="submitted")
        response = self.client.get(reverse("expenses:detail", args=[self.expense.pk]))
        self.assertNotContains(response, 'id="id_wbs_node"')
        before = self.counts()
        self.assertEqual(
            self.client.post(
                reverse("expenses:allocate", args=[self.expense.pk]), self.payload()
            ).status_code,
            400,
        )
        self.assertEqual(before, self.counts())

    def test_capability_absence_and_role_revocation_deny_entry(self):
        self.login(self.viewer)
        response = self.client.get(reverse("expenses:detail", args=[self.expense.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="id_wbs_node"')
        self.assertEqual(
            self.client.post(
                reverse("expenses:allocate", args=[self.expense.pk]), self.payload()
            ).status_code,
            403,
        )
        MembershipRoleAssignment.objects.filter(membership=self.limited).update(
            revoked_at=timezone.now()
        )
        self.login(self.user)
        self.assertEqual(
            self.client.get(
                reverse("expenses:detail", args=[self.expense.pk])
            ).status_code,
            403,
        )

    def test_existing_direct_service_project_tenant_capability_denials(self):
        before = self.counts()
        for actor, keys in (
            (self.user, "CDX"),
            (self.site_user, "ABCDX"),
            (self.viewer, "B"),
        ):
            for key in keys:
                with (
                    self.subTest(actor=actor.username, key=key),
                    self.assertRaises(PermissionDenied),
                ):
                    args = {k: v for k, v in self.sources[key].items() if k != "budget"}
                    add_expense_allocation(
                        expense=self.expense,
                        actor=actor,
                        amount=Decimal(10),
                        allocation_basis_reference="negative",
                        **args,
                    )
        self.assertEqual(before, self.counts())

    def test_original_lifecycle_predicates_and_missing_budget(self):
        WBSNode.objects.filter(pk=self.sources["A"]["wbs_node"].pk).update(
            is_active=False
        )
        Activity.objects.filter(pk=self.sources["A"]["activity"].pk).update(
            archived_at=timezone.now()
        )
        Project.objects.filter(pk=self.sources["A"]["project"].pk).update(
            deleted_at=timezone.now()
        )
        form = self.form()
        for field in ("project", "wbs_node", "activity"):
            self.assertNotIn(self.sources["A"][field], form.fields[field].queryset)
        self.sources["B"]["project"].budget_control.delete()
        form = self.form(self.payload())
        self.assertFalse(form.is_valid())
        self.assertIn("accepted governing budget", str(form.errors))
