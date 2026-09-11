from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import AccountStatus, User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.organizations.services import set_active_organization


class UserDetailAdminTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            username="system-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.user = User.objects.create_user(
            username="site-engineer",
            password="user-password",
            first_name="سارا",
            last_name="احمدی",
            email="sara@example.com",
            phone_number="09120000000",
        )
        self.organization = Organization.objects.create(
            name="شرکت سازه شمال",
            slug="sazeh-shomal",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=MembershipRole.OPERATIONS_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        record_audit_event(
            action=AuditAction.PROJECT_CREATED,
            entity_type="project",
            entity_id="project-1",
            organization=self.organization,
            actor=self.user,
            metadata={"code": "PRJ-001"},
        )

    def test_superuser_detail_displays_required_sections_and_existing_data(
        self,
    ) -> None:
        permission = Permission.objects.get(
            content_type__app_label="projects",
            codename="view_project",
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("admin:accounts_user_change", args=[self.user.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اطلاعات پایه")
        self.assertContains(response, "عضویت‌ها و نقش‌های سازمانی")
        self.assertContains(response, "مجوزها و دسترسی‌ها")
        self.assertContains(response, "تاریخچهٔ فعالیت")
        self.assertContains(response, "سارا احمدی")
        self.assertContains(response, "شرکت سازه شمال")
        self.assertContains(response, "مدیر اجرایی")
        self.assertContains(response, "projects.view_project")
        self.assertContains(response, "پروژه ایجاد شد")
        self.assertContains(response, "دسترسی سطح پروژه در معماری فعلی تعریف نشده است")
        self.assertNotContains(response, self.user.password)

    def test_detail_uses_empty_states_for_missing_optional_data(self) -> None:
        user = User.objects.create_user(username="empty-user", password="test-password")
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("admin:accounts_user_change", args=[user.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام کامل ثبت نشده است")
        self.assertContains(response, "عضویت سازمانی وجود ندارد")
        self.assertContains(response, "مجوز ویژه‌ای تخصیص نیافته است")
        self.assertContains(response, "فعالیت مهمی ثبت نشده است")

    def test_superuser_change_records_status_and_permission_audit_events(self) -> None:
        permission = Permission.objects.get(
            content_type__app_label="projects",
            codename="view_project",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin:accounts_user_change", args=[self.user.pk]),
            {
                "username": self.user.username,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "phone_number": self.user.phone_number,
                "account_status": AccountStatus.BLOCKED,
                "is_staff": "",
                "is_superuser": "",
                "groups": [],
                "user_permissions": [str(permission.pk)],
                "_save": "ذخیره",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, AccountStatus.BLOCKED)
        self.assertFalse(self.user.is_active)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.USER_ACCOUNT_STATUS_CHANGED,
                entity_type="user",
                entity_id=str(self.user.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.USER_PERMISSIONS_CHANGED,
                entity_type="user",
                entity_id=str(self.user.pk),
            ).exists()
        )


class UserDetailAdminTenantIsolationTests(TestCase):
    def setUp(self) -> None:
        self.tenant_admin = User.objects.create_user(
            username="tenant-admin",
            password="test-password",
            is_staff=True,
        )
        self.visible_user = User.objects.create_user(
            username="visible-user", password="test-password"
        )
        self.hidden_user = User.objects.create_user(
            username="hidden-user", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="سازمان قابل مشاهده",
            slug="visible-org",
            created_by=self.tenant_admin,
        )
        self.other_organization = Organization.objects.create(
            name="سازمان محرمانه",
            slug="hidden-org",
            created_by=self.hidden_user,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.tenant_admin,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.visible_user,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.visible_user,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.hidden_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        view_user_permission = Permission.objects.get(
            content_type__app_label="accounts",
            codename="view_user",
        )
        self.tenant_admin.user_permissions.add(view_user_permission)
        record_audit_event(
            action=AuditAction.PROJECT_CREATED,
            entity_type="project",
            entity_id="visible-project",
            organization=self.organization,
            actor=self.visible_user,
        )
        record_audit_event(
            action=AuditAction.PAYMENT_RECORDED,
            entity_type="payment",
            entity_id="hidden-payment",
            organization=self.other_organization,
            actor=self.visible_user,
        )
        self.client.force_login(self.tenant_admin)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

    def test_tenant_admin_sees_only_membership_for_active_organization(self) -> None:
        response = self.client.get(
            reverse("admin:accounts_user_change", args=[self.visible_user.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سازمان قابل مشاهده")
        self.assertNotContains(response, "سازمان محرمانه")
        self.assertContains(response, "پروژه ایجاد شد")
        self.assertNotContains(response, "پرداخت ثبت شد")

    def test_tenant_admin_cannot_view_user_from_another_organization(self) -> None:
        response = self.client.get(
            reverse("admin:accounts_user_change", args=[self.hidden_user.pk])
        )

        self.assertEqual(response.status_code, 302)

    def test_tenant_admin_cannot_mutate_global_user_data(self) -> None:
        response = self.client.post(
            reverse("admin:accounts_user_change", args=[self.visible_user.pk]),
            {"username": "changed-outside-scope"},
        )

        self.assertEqual(response.status_code, 403)
        self.visible_user.refresh_from_db()
        self.assertEqual(self.visible_user.username, "visible-user")
