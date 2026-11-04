"""Own-data header labels must follow tenant, identity and effective dates."""

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts.header_identity import membership_header_identity
from apps.accounts.models import User
from apps.organizations.authorization import get_active_membership
from apps.organizations.context_processors import business_permissions
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.workforce.models import (
    Employee,
    EmployeePositionAssignment,
    EmployeeStatus,
    Person,
    Position,
    PositionAssignmentStatus,
    WorkRelationship,
)


class HeaderIdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="header-fixture", first_name="علی", last_name="رضایی"
        )
        cls.organization = create_organization_with_owner(
            owner=cls.user,
            name="شرکت آزمایشی سربرگ",
            slug="header-identity-fixture",
            timezone_name="Asia/Tehran",
        )
        cls.other = create_organization_with_owner(
            owner=cls.user,
            name="شرکت آزمایشی دیگر",
            slug="header-other-fixture",
        )
        cls.today = timezone.localdate(timezone=ZoneInfo("Asia/Tehran"))
        cls.employee = Employee.objects.create(
            organization=cls.organization,
            user=cls.user,
            employee_number="HEADER-01",
            first_name="علی",
            last_name="رضایی",
        )
        cls.position = Position.objects.create(
            organization=cls.organization, code="HEADER-01", title="سرپرست اجرا"
        )
        cls.assignment = EmployeePositionAssignment.objects.create(
            organization=cls.organization,
            employee=cls.employee,
            position=cls.position,
            start_date=cls.today,
            is_primary=True,
        )

    def identity(self, organization=None):
        return membership_header_identity(
            membership=get_active_membership(
                user=self.user, organization=organization or self.organization
            )
        )

    def canonical_link(self, **changes):
        person = Person.objects.create(
            organization=self.organization,
            user=self.user,
            first_name="علی",
            last_name="رضایی",
        )
        values = {
            "organization": self.organization,
            "person": person,
            "employee_number": "HEADER-01",
            "effective_start": self.today - timedelta(days=3),
            "legacy_employee": self.employee,
        }
        values.update(changes)
        return WorkRelationship.objects.create(**values)

    def test_effective_roles_and_explicit_legacy_position(self):
        identity = self.identity()
        self.assertEqual(identity.role_label, "مالک شرکت")
        self.assertEqual(identity.position_title, self.position.title)

    def test_all_current_roles_exclude_revoked_expired_future_and_inactive(self):
        membership = get_active_membership(
            user=self.user, organization=self.organization
        )
        now = timezone.now()
        for index, (name, changes, active) in enumerate(
            [
                ("نقش جاری", {}, True),
                ("نقش آینده", {"starts_at": now + timedelta(days=1)}, True),
                (
                    "نقش منقضی",
                    {
                        "starts_at": now - timedelta(days=2),
                        "ends_at": now - timedelta(days=1),
                    },
                    True,
                ),
                ("نقش لغوشده", {"revoked_at": now}, True),
                ("نقش غیرفعال", {}, False),
            ]
        ):
            role = OrganizationRole.objects.create(
                organization=self.organization,
                code=f"header-role-{index}",
                name=name,
                is_active=active,
            )
            MembershipRoleAssignment.objects.create(
                organization=self.organization,
                membership=membership,
                role=role,
                reason="Synthetic header fixture",
                **changes,
            )
        label = self.identity().role_label
        self.assertIn("نقش جاری", label)
        self.assertIn("مالک شرکت", label)
        for name in ("نقش آینده", "نقش منقضی", "نقش لغوشده", "نقش غیرفعال"):
            self.assertNotIn(name, label)
        membership.role_assignments.update(revoked_at=now)
        self.assertEqual(self.identity().role_label, "")

    def test_unmigrated_legacy_role_only_and_no_resurrected_role(self):
        membership = OrganizationMembership.objects.get(
            user=self.user, organization=self.organization
        )
        membership.role_assignments.all().delete()
        OrganizationMembership.objects.filter(pk=membership.pk).update(
            authorization_migrated_at=None
        )
        self.assertEqual(self.identity().role_label, "مالک شرکت")
        OrganizationMembership.objects.filter(pk=membership.pk).update(
            authorization_migrated_at=timezone.now()
        )
        self.assertEqual(self.identity().role_label, "")

    def test_header_localization_does_not_rename_catalog_or_custom_role(self):
        membership = get_active_membership(
            user=self.user, organization=self.organization
        )
        original_titles = dict(OrganizationRole.objects.values_list("pk", "name"))
        custom_role = OrganizationRole.objects.create(
            organization=self.organization,
            code="tenant_owner",
            name="Tenant Owner",
            is_system=False,
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=custom_role,
            reason="Synthetic custom-title preservation fixture",
        )
        self.assertCountEqual(
            self.identity().role_label.split("، "), ["مالک شرکت", "Tenant Owner"]
        )
        self.assertEqual(
            dict(
                OrganizationRole.objects.filter(pk__in=original_titles).values_list(
                    "pk", "name"
                )
            ),
            original_titles,
        )

    def test_canonical_person_link_supports_employee_without_login(self):
        self.employee.user = None
        self.employee.save(update_fields=["user"])
        self.canonical_link()
        self.assertEqual(self.identity().position_title, self.position.title)

    def test_expired_or_ambiguous_work_relationship_never_uses_legacy_fallback(self):
        relationship = self.canonical_link(effective_end=self.today - timedelta(days=1))
        self.assertEqual(self.identity().position_title, "")
        WorkRelationship.objects.filter(pk=relationship.pk).update(effective_end=None)
        WorkRelationship.objects.create(
            organization=self.organization,
            person=relationship.person,
            employee_number="HEADER-02",
            effective_start=self.today - timedelta(days=1),
        )
        self.assertEqual(self.identity().position_title, "")

    def test_no_identity_is_inferred_from_matching_name_or_employee_number(self):
        self.employee.user = None
        self.employee.save(update_fields=["user"])
        self.assertEqual(self.identity().position_title, "")

    def test_noncurrent_positions_and_inactive_employee_are_hidden(self):
        for changes in (
            {"start_date": self.today + timedelta(days=1)},
            {"is_primary": False},
            {"status": PositionAssignmentStatus.ENDED, "end_date": self.today},
        ):
            with self.subTest(changes=changes):
                EmployeePositionAssignment.objects.filter(pk=self.assignment.pk).update(
                    start_date=self.today,
                    is_primary=True,
                    status=PositionAssignmentStatus.ACTIVE,
                    end_date=None,
                )
                EmployeePositionAssignment.objects.filter(pk=self.assignment.pk).update(
                    **changes
                )
                self.assertEqual(self.identity().position_title, "")
        EmployeePositionAssignment.objects.filter(pk=self.assignment.pk).update(
            status=PositionAssignmentStatus.ACTIVE, end_date=None
        )
        for changes in (
            {"status": EmployeeStatus.INACTIVE},
            {"status": EmployeeStatus.ACTIVE, "archived_at": timezone.now()},
        ):
            Employee.objects.filter(pk=self.employee.pk).update(**changes)
            self.assertEqual(self.identity().position_title, "")

    def test_archived_inactive_and_foreign_tenant_positions_are_hidden(self):
        for changes in (
            {"is_active": False},
            {"is_active": True, "archived_at": timezone.now()},
            {"archived_at": None, "organization": self.other},
        ):
            with self.subTest(changes=changes):
                Position.objects.filter(pk=self.position.pk).update(**changes)
                self.assertEqual(self.identity().position_title, "")

    def test_switching_company_updates_the_rendered_header_without_leakage(self):
        role = OrganizationRole.objects.create(
            organization=self.other, code="header-other-role", name="نقش شرکت دیگر"
        )
        other_membership = self.other.memberships.get(user=self.user)
        other_membership.role_assignments.update(revoked_at=timezone.now())
        MembershipRoleAssignment.objects.create(
            organization=self.other,
            membership=other_membership,
            role=role,
            reason="Synthetic switching fixture",
        )
        self.client.force_login(self.user)
        for organization in (self.organization, self.other, self.organization):
            session = self.client.session
            session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization.pk)
            session.save()
            response = self.client.get(reverse("home"))
            self.assertEqual(response.status_code, 200)
            identity = response.context["header_identity"]
            if organization == self.organization:
                self.assertEqual(identity.position_title, self.position.title)
                self.assertNotContains(response, role.name)
            else:
                self.assertEqual(identity.position_title, "")
                self.assertEqual(identity.role_label, role.name)
                self.assertNotContains(response, self.position.title)
            self.assertContains(response, "تنظیمات شخصی")

    def test_invalid_membership_anonymous_and_platform_privilege_do_not_leak(self):
        outsider = User.objects.create_user(
            username="header-outsider", is_superuser=True
        )
        request = RequestFactory().get("/")
        request.organization = self.organization
        for user in (outsider, AnonymousUser()):
            request.user = user
            self.assertIsNone(business_permissions(request)["header_identity"])
        OrganizationMembership.objects.filter(
            user=self.user, organization=self.organization
        ).update(status=MembershipStatus.REVOKED)
        request.user = self.user
        self.assertIsNone(business_permissions(request)["header_identity"])

    def test_personal_settings_url_avatar_and_escaped_labels(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.organization = self.organization
        request.resolver_match = resolve("/")
        html = get_template("components/header_profile.html").render(
            {
                "request": request,
                "header_identity": SimpleNamespace(
                    role_label='<script>alert("role")</script>',
                    position_title='<img src=x onerror="alert(1)">',
                ),
            }
        )
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertEqual(html.count(f'href="{reverse("accounts:settings")}"'), 2)
        self.assertIn("h-14 w-14", html)
        self.assertIn("data-header-profile-mobile", html)


class HeaderIdentityBrowserTests(SimpleTestCase):
    def test_real_shared_shell_profile_at_desktop_and_mobile_sizes(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "output/header-identity"
        output.mkdir(parents=True, exist_ok=True)
        request = RequestFactory().get("/")
        request.user = User(
            username="header-browser-fixture",
            first_name="علی",
            last_name="رضایی",
            profile_image="header-fixture.png",
        )
        request.organization = SimpleNamespace(name="شرکت ساختمانی آزمایشی")
        request.resolver_match = resolve("/")
        context = {
            "request": request,
            "product_navigation_groups": [],
            "header_identity": SimpleNamespace(
                role_label="مدیر شرکت", position_title="سرپرست اجرا"
            ),
        }
        for filename, image in (("shell.html", "fixture.png"), ("fallback.html", "")):
            request.user.profile_image = image
            (output / filename).write_text(
                get_template("base.html").render(context), encoding="utf-8"
            )
        (output / "contracts.html").write_text(
            get_template("contracts/list.html").render(context), encoding="utf-8"
        )
        (output / "routes.json").write_text(
            json.dumps(
                {
                    "avatar": reverse("accounts:profile-image"),
                    "settings": reverse("accounts:settings"),
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "node",
                str(root / "scripts/verification/header_identity_browser.mjs"),
                str(output),
            ],
            cwd=root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-5000:])
