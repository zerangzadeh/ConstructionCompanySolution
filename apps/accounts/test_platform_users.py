import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.messages import get_messages
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail.backends.locmem import EmailBackend
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.recovery import account_recovery_tokens
from apps.accounts.services import initialize_personal_password
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    create_organization_with_owner,
    update_organization_membership,
)


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    EMAIL_HOST="smtp.example.test",
    DEFAULT_FROM_EMAIL="bonira@example.test",
)
class PlatformUserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(
            username="users-root", password="root-fixture"
        )
        cls.operator = User.objects.create_user(
            username="users-operator", password="operator-fixture"
        )
        cls.owner = User.objects.create_user(
            username="users-owner", password="owner-fixture"
        )
        cls.target = User.objects.create_user(
            username="users-member",
            email="member@example.test",
            password="member-fixture",
            first_name="کاربر",
            last_name="آزمایشی",
        )
        assign_platform_admin(
            actor=cls.root, approver=cls.root, target=cls.operator, reason="fixture"
        )
        cls.company = create_organization_with_owner(
            owner=cls.owner, name="شرکت اول", slug="users-company-a"
        )
        cls.other_company = create_organization_with_owner(
            owner=cls.owner, name="شرکت دوم", slug="users-company-b"
        )
        cls.role = OrganizationRole.objects.create(
            name="نقش آزمایشی محدود",
            code="users-restricted-role",
            organization=cls.company,
        )
        for company in (cls.company, cls.other_company):
            OrganizationMembership.objects.create(
                organization=company,
                user=cls.target,
                status=MembershipStatus.ACTIVE,
                role=MembershipRole.MEMBER,
                role_definition=cls.role if company == cls.company else None,
            )

    def setUp(self):
        self.client.force_login(self.operator)

    def url(self, suffix="", user=None):
        if suffix in ("", "_create"):
            return reverse(
                "organizations:platform_users"
                if not suffix
                else "organizations:platform_user_create"
            )
        return reverse(
            f"organizations:platform_user{suffix}", args=[(user or self.target).pk]
        )

    def status_payload(self, status, user=None):
        current = User.objects.get(pk=(user or self.target).pk)
        return {
            "status": status,
            "reason": "fixture reason",
            "expected_updated_at": current.updated_at.isoformat(),
        }

    def temporary_password_payload(self, password, user=None):
        current = User.objects.get(pk=(user or self.target).pk)
        return {
            "new_password1": password,
            "new_password2": password,
            "expected_updated_at": current.updated_at.isoformat(),
        }

    def test_directory_search_filters_counts_and_pagination(self):
        for query in ("کاربر آزمایشی", "USERS-MEMBER", "member@example.test"):
            with self.subTest(query=query):
                page = self.client.get(
                    self.url(), {"q": query, "company": self.company.pk}
                ).context["page_obj"]
                self.assertEqual(
                    [(user.pk, user.membership_count) for user in page],
                    [(self.target.pk, 2)],
                )
        response = self.client.get(
            self.url(), {"platform_admin": "yes", "status": "active"}
        )
        self.assertEqual(
            [user.pk for user in response.context["page_obj"]], [self.operator.pk]
        )
        self.assertContains(response, self.url("_create"))
        User.objects.bulk_create(
            [User(username=f"users-paging-{i}") for i in range(27)]
        )
        response = self.client.get(self.url(), {"q": "users-paging-", "page": 2})
        self.assertEqual(response.context["page_obj"].paginator.count, 27)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 20)
        self.assertEqual(len(response.context["page_obj"].object_list), 7)
        response = self.client.get(
            self.url(), {"q": "users-paging-", "status": "active", "page_size": 10}
        )
        self.assertEqual(len(response.context["page_obj"].object_list), 10)
        next_url = re.search(r'href="([^"]+)" rel="next"', response.content.decode())[1]
        next_params = parse_qs(urlsplit(next_url.replace("&amp;", "&")).query)
        self.assertEqual(
            next_params,
            {
                "q": ["users-paging-"],
                "status": ["active"],
                "page_size": ["10"],
                "page": ["2"],
            },
        )
        self.assertEqual(
            self.client.get(self.url(), {"q": "users-paging-", "page_size": 50})
            .context["page_obj"]
            .end_index(),
            27,
        )
        self.assertFalse(self.operator.organization_memberships.exists())

    def test_directory_counts_and_presents_account_controls_by_authority(self):
        username = "long-account-" + "identifier-" * 10
        inactive = User.objects.create_user(username=username, is_active=False)
        response = self.client.get(self.url(), {"q": username, "status": "inactive"})
        self.assertContains(response, f'dir="ltr" title="{username}"')
        self.assertContains(response, self.url("_detail", inactive))
        self.assertContains(response, self.url("_edit", inactive))
        self.assertContains(response, "فعال‌سازی حساب")
        self.assertNotContains(response, "#platform-account-recovery")
        self.assertEqual(
            [metric["value"] for metric in response.context["user_metrics"]],
            [User.objects.count(), User.objects.filter(is_active=True).count(), 1, 1],
        )
        response = self.client.get(self.url(), {"q": self.root.username})
        self.assertContains(response, self.url("_detail", self.root))
        self.assertNotContains(response, self.url("_edit", self.root))
        self.assertNotContains(response, "#platform-account-status")
        self.assertNotContains(response, "#platform-account-recovery")
        response = self.client.get(self.url(), {"q": self.target.username})
        self.assertContains(response, self.url("_edit"))
        self.assertContains(response, "#platform-account-status")
        self.assertContains(response, "#platform-account-recovery")
        self.assertContains(self.client.get(self.url("_detail", inactive)), "ثبت نشده")

    def test_memberships_visible_but_roles_require_company_authority(self):
        response = self.client.get(self.url("_detail"))
        self.assertContains(response, self.company.name)
        self.assertContains(response, self.other_company.name)
        self.assertContains(response, self.url("_edit"))
        self.assertNotContains(response, self.role.name)
        self.assertNotContains(response, self.target.password)
        restricted_url = reverse(
            "organizations:platform_member_authorization",
            args=[
                self.company.pk,
                self.target.organization_memberships.get(organization=self.company).pk,
            ],
        )
        self.assertNotContains(response, restricted_url)
        authorized = User.objects.create_user(
            username="users-owner-operator", password="fixture"
        )
        company = create_organization_with_owner(
            owner=authorized, name="شرکت سوم", slug="users-company-c"
        )
        assign_platform_admin(
            actor=self.root, approver=self.root, target=authorized, reason="fixture"
        )
        role = OrganizationRole.objects.create(
            name="نقش مجاز برای نمایش", code="users-visible-role", organization=company
        )
        membership = OrganizationMembership.objects.create(
            organization=company,
            user=self.target,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )
        self.client.force_login(authorized)
        response = self.client.get(self.url("_detail"))
        self.assertContains(response, role.name)
        self.assertNotContains(response, self.role.name)
        self.assertNotContains(response, restricted_url)
        self.assertContains(
            response,
            reverse(
                "organizations:platform_member_authorization",
                args=[company.pk, membership.pk],
            ),
        )

    def test_create_edit_and_account_audit(self):
        payload = {
            "username": "  New-Platform-Identity  ",
            "email": "NEW@example.test",
            "first_name": "کاربر",
            "is_superuser": True,
        }
        response = self.client.post(self.url("_create"), payload)
        user = User.objects.get(username="new-platform-identity")
        self.assertRedirects(response, self.url("_detail", user))
        self.assertEqual(user.email, "new@example.test")
        self.assertTrue(user.must_change_password)
        self.assertFalse(
            user.is_superuser or user.is_staff or user.organization_memberships.exists()
        )
        self.assertFalse(user.check_password("new-platform-identity"))
        duplicate = self.client.post(
            self.url("_create"), {**payload, "username": "another-user"}
        )
        self.assertContains(duplicate, "پیش‌تر برای یک حساب ثبت شده")
        update = {
            "first_name": "ویرایش",
            "phone_number": "02100000000",
            "email": "changed@example.test",
            "expected_updated_at": user.updated_at.isoformat(),
        }
        self.assertRedirects(
            self.client.post(self.url("_edit", user), update), self.url("_detail", user)
        )
        user.refresh_from_db()
        self.assertEqual(
            (user.first_name, user.phone_number, user.email),
            ("ویرایش", "02100000000", "new@example.test"),
        )
        self.assertContains(
            self.client.post(self.url("_edit", user), update), "صفحه را تازه‌سازی کنید"
        )
        audit = AuditEvent.objects.filter(entity_id=str(user.pk), actor=self.operator)
        self.assertCountEqual(
            audit.values_list("action", flat=True),
            [AuditAction.USER_ACCOUNT_CREATED, AuditAction.USER_ACCOUNT_UPDATED],
        )
        self.assertContains(
            self.client.get(self.url("_detail", user)),
            AuditAction.USER_ACCOUNT_UPDATED.label,
        )
        self.assertContains(
            self.client.get(reverse("organizations:platform_audit")),
            AuditAction.USER_ACCOUNT_CREATED.label,
        )

    def test_deactivation_revokes_sessions_and_old_tokens_through_reactivation(self):
        immediate, dormant = Client(), Client()
        immediate.force_login(self.target)
        dormant.force_login(self.target)
        self.target.refresh_from_db()
        token = account_recovery_tokens.make_token(self.target)
        status_url = self.url("_status")
        self.assertEqual(self.client.get(status_url).status_code, 405)
        self.assertRedirects(
            self.client.post(status_url, self.status_payload("inactive")),
            self.url("_detail"),
        )
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        settings_url = reverse("accounts:settings")
        self.assertEqual(immediate.get(settings_url).status_code, 302)
        self.assertFalse(
            Client().login(username=self.target.username, password="member-fixture")
        )
        self.assertRedirects(
            self.client.post(status_url, self.status_payload("active")),
            self.url("_detail"),
        )
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertEqual(dormant.get(settings_url).status_code, 302)
        self.assertTrue(
            Client().login(username=self.target.username, password="member-fixture")
        )
        self.assertFalse(account_recovery_tokens.check_token(self.target, token))
        self.assertEqual(self.target.organization_memberships.count(), 2)
        events = AuditEvent.objects.filter(
            action=AuditAction.USER_ACCOUNT_STATUS_CHANGED,
            entity_id=str(self.target.pk),
            actor=self.operator,
        )
        self.assertCountEqual(
            [event.metadata["new_status"] for event in events], ["inactive", "active"]
        )

    def test_last_admin_last_owner_and_technical_account_are_protected(self):
        for user in (self.operator, self.owner, self.root):
            with self.subTest(user=user.username):
                response = self.client.post(
                    self.url("_status", user), self.status_payload("inactive", user)
                )
                self.assertEqual(response.status_code, 403)
                user.refresh_from_db()
                self.assertTrue(user.is_active)
        self.assertEqual(self.client.get(self.url("_edit", self.root)).status_code, 403)
        self.assertEqual(
            self.client.post(self.url("_reset", self.root)).status_code, 403
        )

    def test_tenant_membership_activation_cannot_reactivate_platform_disabled_account(
        self,
    ):
        member = self.target.organization_memberships.get(organization=self.company)
        member.status = MembershipStatus.PENDING_ROLE
        member.save(update_fields=["status"])
        self.assertEqual(
            self.client.post(
                self.url("_status"), self.status_payload("inactive")
            ).status_code,
            302,
        )
        with self.assertRaises(PermissionDenied):
            update_organization_membership(
                organization=self.company,
                actor=self.owner,
                membership=member,
                role=self.role,
                status=MembershipStatus.ACTIVE,
            )
        self.target.refresh_from_db()
        member.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(member.status, MembershipStatus.PENDING_ROLE)

    def test_tenant_users_superuser_without_duty_and_missing_permissions_are_denied(
        self,
    ):
        for user in (self.owner, self.root):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url()).status_code, 403)
            self.assertEqual(self.client.get(self.url("_detail")).status_code, 403)
            self.assertEqual(
                self.client.post(
                    self.url("_status"), self.status_payload("inactive")
                ).status_code,
                403,
            )
        self.client.force_login(self.operator)
        BusinessPermission.objects.filter(
            code=BusinessPermissionCode.PLATFORM_ADMIN_USERS_MANAGE
        ).update(is_active=False)
        response = self.client.get(self.url(), {"q": self.target.username})
        self.assertContains(response, self.url("_detail"))
        self.assertNotContains(response, self.url("_create"))
        self.assertNotContains(response, self.url("_edit"))
        self.assertNotContains(response, "#platform-account-status")
        self.assertEqual(self.client.post(self.url("_create"), {}).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.url("_status"), self.status_payload("inactive")
            ).status_code,
            403,
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.operator)
        self.assertEqual(csrf_client.post(self.url("_reset")).status_code, 403)

    def test_reset_sends_one_use_link_and_audits_without_disclosing_it(self):
        backend = EmailBackend()
        with patch("django.core.mail.get_connection", return_value=backend):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url("_reset"), secure=True)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(len(mail.outbox), 1)
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.url("_reset"), secure=True)
            self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.target.email])
        path = urlsplit(re.search(r"https://[^\s]+", message.body)[0]).path
        self.assertNotContains(self.client.get(self.url("_detail")), path)
        event = AuditEvent.objects.get(
            action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
            entity_id=str(self.target.pk),
        )
        self.assertEqual(event.actor, self.operator)
        self.assertEqual(event.metadata, {"channel": "email", "control_plane": True})
        recipient = Client()
        verify = recipient.get(path)
        self.assertEqual(verify.status_code, 302)
        password = "Fresh-fixture-password-2026!"
        self.assertEqual(
            recipient.post(
                verify.url, {"new_password1": password, "new_password2": password}
            ).status_code,
            302,
        )
        self.assertFalse(Client().get(path).context["validlink"])
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(password))

    @override_settings(EMAIL_HOST="")
    def test_temporary_password_works_without_email_and_requires_a_new_secret(self):
        User.objects.filter(pk=self.target.pk).update(email="")
        existing_session = Client()
        existing_session.force_login(self.target)
        self.target.refresh_from_db()
        old_token = account_recovery_tokens.make_token(self.target)
        reset_url = self.url("_temporary_password")
        self.assertContains(
            self.client.get(self.url(), {"q": self.target.username}), reset_url
        )
        self.assertContains(self.client.get(self.url("_detail")), reset_url)
        reset_form = self.client.get(reset_url)
        for field in ("new_password1", "new_password2"):
            self.assertContains(reset_form, f'<input type="password" name="{field}"')
        temporary = "Fixture-temporary-472!"
        with patch("django.core.mail.EmailMessage.send") as send:
            response = self.client.post(
                reset_url, self.temporary_password_payload(temporary), secure=True
            )
        send.assert_not_called()
        self.assertRedirects(response, self.url("_detail"))
        detail = self.client.get(self.url("_detail"))
        self.assertContains(detail, "گذرواژه موقت تنظیم شد")
        self.assertNotContains(detail, temporary)
        self.target.refresh_from_db()
        self.assertNotEqual(self.target.password, temporary)
        self.assertTrue(self.target.check_password(temporary))
        self.assertTrue(self.target.must_change_password)
        self.assertFalse(account_recovery_tokens.check_token(self.target, old_token))
        profile = reverse("accounts:settings")
        self.assertEqual(existing_session.get(profile).status_code, 302)
        self.assertFalse(
            Client().login(username=self.target.username, password="member-fixture")
        )
        event = AuditEvent.objects.get(
            action=AuditAction.USER_PASSWORD_RESET_COMPLETED,
            entity_id=str(self.target.pk),
        )
        self.assertEqual(event.actor, self.operator)
        self.assertEqual(
            event.metadata, {"control_plane": True, "channel": "temporary_password"}
        )
        self.assertContains(
            self.client.get(reverse("organizations:platform_audit")),
            event.get_action_display(),
        )

        recipient = Client()
        self.assertTrue(
            recipient.login(username=self.target.username, password=temporary)
        )
        change_url = reverse("accounts:required_password_change")
        self.assertRedirects(recipient.get(profile), change_url)
        same = {"new_password1": temporary, "new_password2": temporary}
        self.assertContains(
            recipient.post(change_url, same),
            "گذرواژه شخصی باید با گذرواژه موقت متفاوت باشد",
        )
        personal = "Fixture-personal-753!"
        self.assertRedirects(
            recipient.post(
                change_url, {"new_password1": personal, "new_password2": personal}
            ),
            reverse("organizations:select"),
            fetch_redirect_response=False,
        )
        self.assertEqual(recipient.get(profile).status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)
        self.assertTrue(self.target.check_password(personal))
        self.assertFalse(
            Client().login(username=self.target.username, password=temporary)
        )

    def test_temporary_password_enforces_permission_target_and_csrf(self):
        reset_url = self.url("_temporary_password")
        payload = self.temporary_password_payload("Fixture-temporary-472!")
        self.assertEqual(Client().get(reset_url).status_code, 302)
        for actor in (self.owner, self.root):
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertEqual(self.client.get(reset_url).status_code, 403)
                self.assertEqual(
                    self.client.post(reset_url, payload, secure=True).status_code, 403
                )
        self.client.force_login(self.operator)
        assign_platform_admin(
            actor=self.root, approver=self.root, target=self.owner, reason="fixture"
        )
        for target in (self.operator, self.root, self.owner):
            with self.subTest(target=target.username):
                path = self.url("_temporary_password", target)
                self.assertNotContains(
                    self.client.get(self.url("_detail", target)), path
                )
                self.assertEqual(
                    self.client.post(path, payload, secure=True).status_code, 403
                )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.operator)
        self.assertEqual(
            csrf_client.post(reset_url, payload, secure=True).status_code, 403
        )
        BusinessPermission.objects.filter(
            code=BusinessPermissionCode.PLATFORM_ADMIN_USERS_RECOVER
        ).update(is_active=False)
        self.assertNotContains(self.client.get(self.url("_detail")), reset_url)
        self.assertEqual(
            self.client.post(reset_url, payload, secure=True).status_code, 403
        )

    def test_temporary_password_validation_and_stale_forms_do_not_overwrite_credentials(
        self,
    ):
        reset_url = self.url("_temporary_password")
        payload = self.temporary_password_payload("Fixture-temporary-472!")
        invalid = {**payload, "new_password2": "different-fixture"}
        response = self.client.post(reset_url, invalid, secure=True)
        self.assertTrue(
            response.context["form"].has_error("new_password2", "password_mismatch")
        )
        self.assertNotContains(response, payload["new_password1"])
        response = self.client.post(
            reset_url, self.temporary_password_payload("123456"), secure=True
        )
        self.assertTrue(
            response.context["form"].has_error("new_password2", "password_too_short")
        )
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("member-fixture"))

        self.assertRedirects(
            self.client.post(reset_url, payload, secure=True), self.url("_detail")
        )
        stale_session_user = User.objects.get(pk=self.target.pk)
        newer_password = "Fixture-temporary-583!"
        self.assertRedirects(
            self.client.post(
                reset_url, self.temporary_password_payload(newer_password), secure=True
            ),
            self.url("_detail"),
        )
        self.assertContains(
            self.client.post(reset_url, payload, secure=True), "صفحه را تازه‌سازی کنید"
        )
        with self.assertRaisesMessage(ValidationError, "اعتبار ورود تغییر کرده است"):
            initialize_personal_password(
                user=stale_session_user, new_password="Fixture-stale-personal-846!"
            )
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(newer_password))

    @override_settings(EMAIL_HOST="")
    def test_unavailable_mail_is_reported_without_sending(self):
        with patch("django.core.mail.EmailMessage.send") as send:
            response = self.client.post(self.url("_reset"), follow=True)
        self.assertContains(response, "پیوندی ارسال نشد")
        self.assertContains(
            response, "ارسال پیوند بازیابی به پیکربندی سرویس ایمیل نیاز دارد"
        )
        self.assertContains(response, "پیوند ارسال نشد؛ سرویس ایمیل در دسترس نبود")
        self.assertNotContains(response, self.url("_reset"))
        send.assert_not_called()
        event = AuditEvent.objects.get(
            action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
            entity_id=str(self.target.pk),
        )
        self.assertEqual(event.metadata["delivery"], "unavailable")

    def test_transport_failure_does_not_claim_delivery(self):
        with (
            patch(
                "django.core.mail.EmailMessage.send",
                side_effect=OSError("synthetic transport failure"),
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(self.url("_reset"), secure=True)
        self.assertTrue(
            any(
                "ارسال پیوند بازیابی را تأیید نکرد" in str(message)
                for message in get_messages(response.wsgi_request)
            )
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
                entity_id=str(self.target.pk),
                actor=self.operator,
            ).exists()
        )
