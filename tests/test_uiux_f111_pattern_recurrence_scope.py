"""BATCH-07: recurring Project choices and collection share effective authority."""

import re
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.expenses.forms import RecurringExpenseTemplateForm
from apps.expenses.models import Expense, PlatformExpenseGroup, RecurringExpenseTemplate
from apps.expenses.services import (
    create_recurring_expense_template,
    propose_recurring_expense,
)
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project, ProjectSite


class RecurrenceScopeTests(TestCase):
    @classmethod
    def member(cls, user, org, role="project_manager", scope=False):
        member = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=org,
            membership=member,
            role=OrganizationRole.objects.get(code=role),
            reason="Disposable B07",
        )
        if scope:
            MembershipScopeGrant.objects.create(
                organization=org,
                membership=member,
                scope_type="organization",
                reason="Disposable B07",
            )
        return member

    @classmethod
    def setUpTestData(cls):
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "Other"}
        )
        cls.org = Organization.objects.create(name="B07 tenant", slug="b07")
        cls.other = Organization.objects.create(name="B07 foreign", slug="b07-x")
        for org in (cls.org, cls.other):
            OrganizationSettings.objects.create(organization=org, currency="IRR")
        cls.user = User.objects.create_user(username="b07-limited")
        cls.owner = User.objects.create_user(username="b07-owner")
        cls.foreign = User.objects.create_user(username="b07-foreign")
        cls.site_user = User.objects.create_user(username="b07-site")
        cls.viewer = User.objects.create_user(username="b07-viewer")
        cls.limited = cls.member(cls.user, cls.org)
        cls.owner_member = cls.member(cls.owner, cls.org, "company_owner", True)
        cls.foreign_member = cls.member(cls.foreign, cls.other, "company_owner", True)
        cls.site_member = cls.member(cls.site_user, cls.org, "operations_manager")
        cls.viewer_member = cls.member(cls.viewer, cls.org, "viewer", True)
        cls.projects, cls.templates = {}, {}
        for key in "ABCDX":
            org, actor = (
                (cls.other, cls.foreign) if key == "X" else (cls.org, cls.owner)
            )
            project = Project.objects.create(
                organization=org,
                code=f"B07-P-{key}",
                name=f"B07 distinct Project {key}",
            )
            cls.projects[key] = project
            cls.templates[key] = create_recurring_expense_template(
                organization=org,
                project=project,
                actor=actor,
                description=f"B07 distinctive template {key}",
                amount=Decimal("12.50"),
                classification="direct",
                frequency="monthly",
                starts_on=date(2026, 10, 22),
                ends_on=date(2026, 12, 22),
                source_reference_prefix=f"B07-{key}",
            )
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=cls.org,
                    membership=cls.limited,
                    scope_type="project",
                    project=project,
                    reason="Disposable B07 A/B",
                )
        site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.projects["A"],
            code="B07-S",
            name="B07 site",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.site_member,
            scope_type="site",
            project=cls.projects["A"],
            site=site,
            reason="Disposable site only",
        )

    def login(self, user=None):
        self.client.force_login(user or self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def payload(self, key="B"):
        return {
            "project": str(self.projects[key].pk),
            "description": "B07 new template",
            "amount": "10.00",
            "classification": "direct",
            "frequency": "monthly",
            "starts_on": "2026-10-22",
            "ends_on": "2026-12-22",
            "source_reference_prefix": "B07-NEW",
        }

    def snapshot(self):
        return tuple(
            list(m.objects.order_by("pk").values())
            for m in (RecurringExpenseTemplate, Expense, AuditEvent)
        )

    def assert_page(self, response, allowed="AB"):
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            set(response.context["form"].fields["project"].queryset),
            {self.projects[k] for k in allowed},
        )
        self.assertSetEqual(
            set(response.context["templates"]), {self.templates[k] for k in allowed}
        )
        body = re.sub(
            r'href="[^"]*[?&](?:amp;)?next=[^"]*"', "", response.content.decode()
        )
        body = re.sub(r'<input[^>]*name="next"[^>]*>', "", body)
        for key in "ABCDX":
            for token in (
                str(self.projects[key].pk),
                self.projects[key].name,
                str(self.templates[key].pk),
                self.templates[key].description,
            ):
                if key in allowed:
                    self.assertIn(token, body)
                else:
                    # Site navigation may name its authorized parent; that is
                    # context, never a recurring Project choice or template.
                    if (
                        not allowed
                        and key == "A"
                        and token
                        in (str(self.projects[key].pk), self.projects[key].name)
                    ):
                        continue
                    self.assertNotIn(token, body)

    def test_get_and_query_filters_cannot_enumerate(self):
        self.login()
        self.assert_page(self.client.get(reverse("expenses:recurrences")))
        for key in "CDX":
            with self.subTest(key=key):
                # Query parameters are not object authority or an alternate detail reader.
                self.assert_page(
                    self.client.get(
                        reverse("expenses:recurrences"),
                        {
                            "project": str(self.projects[key].pk),
                            "template": str(self.templates[key].pk),
                            "q": self.templates[key].description,
                        },
                    )
                )

    def test_organization_scope_and_inactive_template_predicate_preserved(self):
        self.templates["B"].is_active = False
        self.templates["B"].save()
        self.login(self.owner)
        self.assert_page(self.client.get(reverse("expenses:recurrences")), "ABCD")

    def test_site_only_has_no_project_owned_choices_or_collection(self):
        self.login(self.site_user)
        self.assert_page(self.client.get(reverse("expenses:recurrences")), "")
        before = self.snapshot()
        for key in "ABCDX":
            with self.subTest(key=key):
                self.assert_page(
                    self.client.post(
                        reverse("expenses:recurrences"), self.payload(key)
                    ),
                    "",
                )
                self.assertEqual(self.snapshot(), before)

    def test_manipulated_projects_and_missing_fields_redisplay_safely(self):
        self.login()
        before = self.snapshot()
        cases = [(f"forced {k}", self.payload(k)) for k in "CDX"]
        cases += [("malformed", self.payload() | {"project": "not-a-uuid"})]
        cases += [
            (f"missing {f}", {k: v for k, v in self.payload().items() if k != f})
            for f in self.payload()
            if f != "ends_on"
        ]
        for label, data in cases:
            with self.subTest(case=label):
                response = self.client.post(reverse("expenses:recurrences"), data)
                self.assert_page(response)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(self.snapshot(), before)

    def test_service_error_redisplay_retains_both_scopes(self):
        self.login()
        before = self.snapshot()
        with patch(
            "apps.expenses.views.create_recurring_expense_template",
            side_effect=PermissionDenied("Denied"),
        ):
            response = self.client.post(reverse("expenses:recurrences"), self.payload())
        self.assert_page(response)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertEqual(self.snapshot(), before)

    def test_missing_invalid_wrong_tenant_memberships_fail_closed(self):
        for member in (None, object(), self.foreign_member):
            with self.subTest(member=type(member).__name__):
                form = RecurringExpenseTemplateForm(
                    organization=self.org, membership=member
                )
                self.assertFalse(form.fields["project"].queryset.exists())
        form = RecurringExpenseTemplateForm(membership=self.limited)
        self.assertFalse(form.fields["project"].queryset.exists())

    def test_ineffective_grants_hide_collection_and_options(self):
        now = timezone.now()
        for change in (
            {"revoked_at": now},
            {"starts_at": now - timedelta(days=2), "ends_at": now - timedelta(days=1)},
            {"starts_at": now + timedelta(days=1)},
        ):
            with self.subTest(change=change):
                grants = MembershipScopeGrant.objects.filter(membership=self.limited)
                originals = list(
                    grants.values("pk", "starts_at", "ends_at", "revoked_at")
                )
                grants.update(**change)
                self.login()
                self.assertFalse(
                    RecurringExpenseTemplateForm(
                        organization=self.org, membership=self.limited
                    )
                    .fields["project"]
                    .queryset.exists()
                )
                self.assertEqual(
                    self.client.get(reverse("expenses:recurrences")).status_code, 403
                )
                for row in originals:
                    MembershipScopeGrant.objects.filter(pk=row.pop("pk")).update(**row)
        MembershipScopeGrant.objects.filter(membership=self.limited).delete()
        self.assertEqual(
            self.client.get(reverse("expenses:recurrences")).status_code, 403
        )

    def test_inactive_identity_membership_tenant_and_missing_role_deny(self):
        for obj, field, value in (
            (self.user, "is_active", False),
            (self.limited, "status", "inactive"),
            (self.org, "status", "suspended"),
        ):
            with self.subTest(field=field):
                original = getattr(obj, field)
                type(obj).objects.filter(pk=obj.pk).update(**{field: value})
                member = OrganizationMembership.objects.select_related(
                    "user", "organization"
                ).get(pk=self.limited.pk)
                self.assertFalse(
                    RecurringExpenseTemplateForm(
                        organization=member.organization, membership=member
                    )
                    .fields["project"]
                    .queryset.exists()
                )
                self.login()
                self.assertNotEqual(
                    self.client.get(reverse("expenses:recurrences")).status_code, 200
                )
                type(obj).objects.filter(pk=obj.pk).update(**{field: original})
        MembershipRoleAssignment.objects.filter(membership=self.limited).delete()
        self.login()
        self.assertEqual(
            self.client.get(reverse("expenses:recurrences")).status_code, 403
        )
        self.login(self.viewer)
        self.assertEqual(
            self.client.get(reverse("expenses:recurrences")).status_code, 403
        )

    def test_proposal_action_forbidden_and_mixed_project_query_fail_closed(self):
        self.login()
        before = self.snapshot()
        for key in "CDX":
            with self.subTest(key=key):
                url = reverse(
                    "expenses:recurrence_propose", args=[self.templates[key].pk]
                )
                response = self.client.post(
                    url + f"?project={self.projects['A'].pk}",
                    {"occurrence_on": "2026-10-22"},
                )
                self.assertEqual(response.status_code, 404 if key == "X" else 403)
                for token in (self.templates[key].description, self.projects[key].name):
                    self.assertNotContains(
                        response, token, status_code=response.status_code
                    )
                self.assertEqual(self.snapshot(), before)
        self.login(self.site_user)
        for key in "ABCDX":
            response = self.client.post(
                reverse("expenses:recurrence_propose", args=[self.templates[key].pk]),
                {"occurrence_on": "2026-10-22"},
            )
            self.assertEqual(response.status_code, 404 if key == "X" else 403)
            self.assertEqual(self.snapshot(), before)

    def test_direct_services_preserve_object_tenant_and_capability_denials(self):
        before = self.snapshot()
        for actor, keys in (
            (self.user, "CDX"),
            (self.site_user, "ABCDX"),
            (self.viewer, "AB"),
        ):
            for key in keys:
                with self.subTest(actor=actor.username, key=key):
                    with self.assertRaises(PermissionDenied):
                        propose_recurring_expense(
                            template=self.templates[key],
                            occurrence_on=date(2026, 10, 22),
                            actor=actor,
                        )
                    data = self.payload(key)
                    data.update(
                        project=self.projects[key],
                        starts_on=date(2026, 10, 22),
                        ends_on=None,
                    )
                    with self.assertRaises(PermissionDenied):
                        create_recurring_expense_template(
                            organization=self.org, actor=actor, **data
                        )
                    self.assertEqual(self.snapshot(), before)

    def test_authorized_create_and_proposal_idempotency_no_posting(self):
        from apps.accounting.models import JournalEntry
        from apps.subledgers.models import Obligation
        from apps.treasury.models import TreasuryMovement

        self.login()
        initial = [
            m.objects.count() for m in (JournalEntry, TreasuryMovement, Obligation)
        ]
        response = self.client.post(reverse("expenses:recurrences"), self.payload())
        self.assertRedirects(response, reverse("expenses:recurrences"))
        template = RecurringExpenseTemplate.objects.get(description="B07 new template")
        self.assertEqual(template.project, self.projects["B"])
        first = propose_recurring_expense(
            template=template, occurrence_on=date(2026, 10, 22), actor=self.user
        )
        second = propose_recurring_expense(
            template=template, occurrence_on=date(2026, 10, 22), actor=self.user
        )
        self.assertEqual(first, second)
        self.assertEqual(first.status, "draft")
        self.assertEqual(
            Expense.objects.filter(recurrence_template=template).count(), 1
        )
        self.assertEqual(
            [m.objects.count() for m in (JournalEntry, TreasuryMovement, Obligation)],
            initial,
        )

    def test_recurrence_date_and_active_guards_remain(self):
        before = self.snapshot()
        for day in (date(2026, 10, 21), date(2027, 1, 22), date(2026, 11, 23)):
            with self.subTest(day=day), self.assertRaises(ValueError):
                propose_recurring_expense(
                    template=self.templates["B"], occurrence_on=day, actor=self.user
                )
        self.assertEqual(self.snapshot(), before)
        self.templates["B"].is_active = False
        self.templates["B"].save()
        with self.assertRaises(ValueError):
            propose_recurring_expense(
                template=self.templates["B"],
                occurrence_on=date(2026, 10, 22),
                actor=self.user,
            )

    def test_project_lifecycle_filter_and_get_only_proposal(self):
        self.projects["B"].deleted_at = timezone.now()
        self.projects["B"].save()
        form = RecurringExpenseTemplateForm(
            organization=self.org, membership=self.limited
        )
        self.assertSetEqual(set(form.fields["project"].queryset), {self.projects["A"]})
        # Collection originally has no project-deletion or template-active predicate.
        self.login()
        self.assertContains(
            self.client.get(reverse("expenses:recurrences")),
            self.templates["B"].description,
        )
        self.assertEqual(
            self.client.get(
                reverse("expenses:recurrence_propose", args=[self.templates["A"].pk])
            ).status_code,
            405,
        )
