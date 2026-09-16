from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import (
    AccountStatus,
    LoginPageSettings,
    User,
    validate_iranian_national_id,
)
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.organizations.services import set_active_organization


class NationalIdValidationTests(SimpleTestCase):
    def test_accepts_valid_iranian_national_id(self) -> None:
        validate_iranian_national_id("1234567891")

    def test_rejects_invalid_iranian_national_id(self) -> None:
        with self.assertRaises(ValidationError):
            validate_iranian_national_id("1234567890")


class LoginPageSettingsAdminTests(TestCase):
    def setUp(self) -> None:
        self.superuser = User.objects.create_superuser(
            username="login-settings-admin",
            password="test-password",
        )
        self.staff_user = User.objects.create_user(
            username="ordinary-staff",
            password="test-password",
            is_staff=True,
        )

    def test_superuser_can_create_only_one_settings_record(self) -> None:
        self.client.force_login(self.superuser)
        add_url = reverse("admin:accounts_loginpagesettings_add")

        response = self.client.post(
            add_url,
            {
                "panel_label": "برچسب",
                "panel_title": "عنوان",
                "panel_description": "توضیح",
                "panel_footer": "پایان",
                "_save": "ذخیره",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LoginPageSettings.objects.count(), 1)
        self.assertEqual(self.client.get(add_url).status_code, 403)

    def test_superuser_can_save_empty_login_panel_messages(self) -> None:
        settings = LoginPageSettings.objects.create()
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin:accounts_loginpagesettings_change", args=[settings.pk]),
            {
                "panel_label": "",
                "panel_title": "",
                "panel_description": "",
                "panel_footer": "",
                "_save": "ذخیره",
            },
        )

        self.assertEqual(response.status_code, 302)
        settings.refresh_from_db()
        self.assertEqual(settings.panel_label, "")
        self.assertEqual(settings.panel_title, "")
        self.assertEqual(settings.panel_description, "")
        self.assertEqual(settings.panel_footer, "")

    def test_non_superuser_cannot_access_login_page_settings_admin(self) -> None:
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("admin:accounts_loginpagesettings_changelist")
        )

        self.assertEqual(response.status_code, 403)


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
        self.assertContains(response, "تعیین نقش یا وضعیت")
        self.assertContains(response, "پروژه ایجاد شد")
        self.assertContains(
            response,
            "برای تغییر دسترسی عملیاتی، نقش عضویت سازمانی را تغییر دهید.",
        )
        self.assertContains(response, "دسترسی به پنل مدیریت سامانه")
        self.assertContains(response, "دسترسی کامل فنی سامانه")
        self.assertContains(
            response,
            "اجازه ورود به پنل فنی مدیریت سامانه را می‌دهد و دسترسی عملیاتی "
            "سازمانی ایجاد نمی‌کند.",
        )
        self.assertContains(
            response,
            "فقط برای مدیران فنی مورداعتماد استفاده شود.",
        )
        self.assertContains(response, "گذرواژه تنظیم شده است.")
        self.assertContains(
            response,
            "برای حفظ امنیت، جزئیات گذرواژه نمایش داده نمی‌شود.",
        )
        self.assertContains(response, "تغییر گذرواژه")
        self.assertNotContains(response, "pbkdf2_sha256")
        self.assertNotContains(response, "Reset password")
        self.assertNotContains(response, "Raw passwords are not stored")
        self.assertNotContains(response, "there is no way to see the user’s password")
        self.assertNotContains(response, "projects.view_project")
        self.assertNotContains(response, 'name="user_permissions"')
        self.assertNotContains(response, 'name="groups"')
        self.assertNotContains(response, self.user.password)

    def test_user_list_displays_first_and_last_names(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin:accounts_user_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام")
        self.assertContains(response, "نام خانوادگی")
        self.assertContains(response, self.user.first_name)
        self.assertContains(response, self.user.last_name)

    def test_detail_uses_empty_states_for_missing_optional_data(self) -> None:
        user = User.objects.create_user(username="empty-user", password="test-password")
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("admin:accounts_user_change", args=[user.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام کامل ثبت نشده است")
        self.assertContains(response, "عضویت سازمانی وجود ندارد")
        self.assertContains(
            response,
            "برای تغییر دسترسی عملیاتی، نقش عضویت سازمانی را تغییر دهید.",
        )
        self.assertContains(response, "فعالیت مهمی ثبت نشده است")

    def test_superuser_can_reset_another_users_password(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin:auth_user_password_change", args=[self.user.pk]),
            {
                "password1": "new-secure-password-2026",
                "password2": "new-secure-password-2026",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-secure-password-2026"))

    def test_superuser_creates_active_user_with_selected_company_role(self) -> None:
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "username": "new-company-user",
                "first_name": "علی",
                "last_name": "احمدی",
                "national_id": "1234567891",
                "email": "ali@example.com",
                "phone_number": "09120000001",
                "organization": str(self.organization.pk),
                "role_definition": MembershipRole.COMPANY_MANAGER,
                "usable_password": "true",
                "password1": "secure-initial-password-2026",
                "password2": "secure-initial-password-2026",
                "_save": "ذخیره",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="new-company-user")
        membership = OrganizationMembership.objects.get(
            organization=self.organization,
            user=user,
        )
        self.assertEqual(user.national_id, "1234567891")
        self.assertTrue(user.is_active)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(membership.role, MembershipRole.COMPANY_MANAGER)
        self.assertEqual(membership.assigned_by, self.admin)

    def test_superuser_can_assign_role_to_existing_user_membership(self) -> None:
        pending_user = User.objects.create_user(
            username="pending-role-user",
            password="user-password",
            is_active=False,
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=pending_user,
            role="",
            role_definition=None,
            status=MembershipStatus.PENDING_ROLE,
            assigned_by=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "admin:organizations_organizationmembership_change",
                args=[membership.pk],
            ),
            {
                "role_definition": MembershipRole.OPERATIONS_MANAGER,
                "status": MembershipStatus.ACTIVE,
                "_save": "ذخیره",
            },
        )

        self.assertEqual(response.status_code, 302)
        membership.refresh_from_db()
        pending_user.refresh_from_db()
        self.assertEqual(membership.role, MembershipRole.OPERATIONS_MANAGER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertTrue(pending_user.is_active)

    def test_superuser_change_records_status_audit_event(self) -> None:
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
        self.assertFalse(
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
