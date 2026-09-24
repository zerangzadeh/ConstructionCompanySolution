import tempfile
from io import StringIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AccountStatus, LoginPageSettings, User


class AuthenticationTests(TestCase):
    def setUp(self) -> None:
        self.password = "test-password"
        self.user = User.objects.create_user(
            username="site-engineer",
            password=self.password,
        )

    def test_login_page_is_available(self) -> None:
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ورود")

    def test_authenticated_user_is_redirected_away_from_login(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:login"))

        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_REDIRECT_URL),
            fetch_redirect_response=False,
        )

    def test_login_page_uses_admin_managed_messages(self) -> None:
        LoginPageSettings.objects.create(
            panel_label="برچسب سفارشی",
            panel_title="عنوان سفارشی",
            panel_description="توضیح سفارشی",
            panel_footer="پیام پایانی سفارشی",
        )

        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, "برچسب سفارشی")
        self.assertContains(response, "عنوان سفارشی")
        self.assertContains(response, "توضیح سفارشی")
        self.assertContains(response, "پیام پایانی سفارشی")

    def test_login_page_uses_admin_managed_background(self) -> None:
        LoginPageSettings.objects.create(background_image="login-page/background.png")

        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, reverse("accounts:login-background"))

    def test_login_page_uses_admin_managed_panel_image(self) -> None:
        LoginPageSettings.objects.create(panel_image="login-page/panel.png")

        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, reverse("accounts:login-panel-image"))

    def test_background_endpoint_serves_only_the_configured_public_image(self) -> None:
        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            settings = LoginPageSettings.objects.create()
            settings.background_image.save(
                "background.png",
                SimpleUploadedFile(
                    "background.png",
                    b"\x89PNG\r\n\x1a\n" + b"test-image-data",
                    content_type="image/png",
                ),
            )

            response = self.client.get(reverse("accounts:login-background"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))

    def test_panel_image_endpoint_serves_only_the_configured_public_image(self) -> None:
        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            settings = LoginPageSettings.objects.create()
            settings.panel_image.save(
                "panel.png",
                SimpleUploadedFile(
                    "panel.png",
                    b"\x89PNG\r\n\x1a\n" + b"test-image-data",
                    content_type="image/png",
                ),
            )

            response = self.client.get(reverse("accounts:login-panel-image"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))

    def test_valid_login_redirects_to_configured_destination(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.user.username,
                "password": self.password,
            },
        )

        self.assertRedirects(
            response,
            resolve_url(settings.LOGIN_REDIRECT_URL),
            fetch_redirect_response=False,
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_login_does_not_authenticate_user(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.user.username,
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post_and_redirects_to_login(self) -> None:
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(post_response, reverse("accounts:login"))
        self.assertFalse(post_response.wsgi_request.user.is_authenticated)

    def test_blocked_user_cannot_authenticate(self) -> None:
        self.user.blocked_at = timezone.now()
        self.user.save(update_fields=["blocked_at", "updated_at"])

        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": self.password},
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, AccountStatus.BLOCKED)
        self.assertFalse(self.user.is_active)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class UserModelTests(TestCase):
    def test_account_status_distinguishes_active_inactive_and_blocked(self) -> None:
        user = User.objects.create_user(username="status-user", password="test-pass")
        self.assertEqual(user.account_status, AccountStatus.ACTIVE)

        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        self.assertEqual(user.account_status, AccountStatus.INACTIVE)

        user.blocked_at = timezone.now()
        user.is_active = True
        user.save(update_fields=["blocked_at", "updated_at"])
        user.refresh_from_db()
        self.assertEqual(user.account_status, AccountStatus.BLOCKED)
        self.assertFalse(user.is_active)

    def test_rejects_a_spoofed_profile_image(self) -> None:
        user = User(
            username="profile-image-user",
            profile_image=SimpleUploadedFile(
                "profile.png",
                b"this-is-not-a-png",
                content_type="image/png",
            ),
        )

        with self.assertRaises(ValidationError):
            user.full_clean()


class PersonalSettingsTests(TestCase):
    def setUp(self) -> None:
        self.password = "current-password-123"
        self.user = User.objects.create_user(
            username="personal-settings-user",
            password=self.password,
            first_name="نام قدیمی",
        )

    def test_settings_page_requires_authentication(self) -> None:
        response = self.client.get(reverse("accounts:settings"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:settings')}",
        )

    def test_authenticated_user_can_view_personal_settings(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تنظیمات شخصی")
        self.assertContains(response, self.user.username)

    def test_user_can_update_only_their_own_profile(self) -> None:
        other_user = User.objects.create_user(
            username="other-user",
            password="other-password",
            first_name="بدون تغییر",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:settings"),
            {
                "action": "profile",
                "profile-first_name": "نام جدید",
                "profile-last_name": "کاربر",
                "profile-email": "USER@EXAMPLE.COM",
                "profile-phone_number": " 09121234567 ",
            },
        )

        self.assertRedirects(response, reverse("accounts:settings"))
        self.user.refresh_from_db()
        other_user.refresh_from_db()
        self.assertEqual(self.user.first_name, "نام جدید")
        self.assertEqual(self.user.email, "user@example.com")
        self.assertEqual(self.user.phone_number, "09121234567")
        self.assertEqual(other_user.first_name, "بدون تغییر")

    def test_user_can_upload_and_privately_view_profile_image(self) -> None:
        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("accounts:settings"),
                {
                    "action": "profile",
                    "profile-first_name": self.user.first_name,
                    "profile-last_name": "",
                    "profile-email": "",
                    "profile-phone_number": "",
                    "profile-profile_image": SimpleUploadedFile(
                        "avatar.png",
                        b"\x89PNG\r\n\x1a\n" + b"profile-image-data",
                        content_type="image/png",
                    ),
                },
            )

            self.assertRedirects(response, reverse("accounts:settings"))
            self.user.refresh_from_db()
            self.assertTrue(self.user.profile_image.name.startswith("profile-images/"))

            settings_response = self.client.get(reverse("accounts:settings"))
            self.assertContains(settings_response, "تصویر پروفایل فعلی ثبت شده است.")
            self.assertContains(
                settings_response, "برای جایگزینی تصویر، فایل جدیدی انتخاب کنید."
            )
            self.assertContains(settings_response, "حذف تصویر فعلی")
            self.assertNotContains(settings_response, self.user.profile_image.name)

            image_response = self.client.get(reverse("accounts:profile-image"))
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response["Content-Type"], "image/png")
            self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")
            self.assertTrue(
                b"".join(image_response.streaming_content).startswith(b"\x89PNG")
            )

    def test_profile_image_endpoint_requires_authentication(self) -> None:
        response = self.client.get(reverse("accounts:profile-image"))

        self.assertEqual(response.status_code, 302)

    def test_password_change_keeps_the_current_session_authenticated(self) -> None:
        self.client.force_login(self.user)
        new_password = "new-secure-password-456"

        response = self.client.post(
            reverse("accounts:settings"),
            {
                "action": "password",
                "password-old_password": self.password,
                "password-new_password1": new_password,
                "password-new_password2": new_password,
            },
        )

        self.assertRedirects(response, reverse("accounts:settings"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertIn("_auth_user_id", self.client.session)

    def test_wrong_current_password_is_rejected(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:settings"),
            {
                "action": "password",
                "password-old_password": "wrong-password",
                "password-new_password1": "new-secure-password-456",
                "password-new_password2": "new-secure-password-456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))


class PopulateUserProfileImagesCommandTests(TestCase):
    def test_population_reaches_the_requested_percentage_idempotently(self) -> None:
        for index in range(5):
            User.objects.create_user(
                username=f"avatar-user-{index}", password="test-password"
            )

        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            call_command(
                "populate_user_profile_images", percentage=80, stdout=StringIO()
            )

            self.assertEqual(User.objects.exclude(profile_image="").count(), 4)
            image_names_before = list(
                User.objects.exclude(profile_image="")
                .order_by("pk")
                .values_list("profile_image", flat=True)
            )

            call_command(
                "populate_user_profile_images", percentage=80, stdout=StringIO()
            )

            self.assertEqual(User.objects.exclude(profile_image="").count(), 4)
            self.assertEqual(
                list(
                    User.objects.exclude(profile_image="")
                    .order_by("pk")
                    .values_list("profile_image", flat=True)
                ),
                image_names_before,
            )


class LoginPageSettingsTests(TestCase):
    def test_rejects_a_file_with_spoofed_image_content(self) -> None:
        settings = LoginPageSettings(
            background_image=SimpleUploadedFile(
                "background.png",
                b"this-is-not-a-png",
                content_type="image/png",
            )
        )

        with self.assertRaises(ValidationError):
            settings.full_clean()

    def test_rejects_a_spoofed_panel_image(self) -> None:
        settings = LoginPageSettings(
            panel_image=SimpleUploadedFile(
                "panel.png",
                b"this-is-not-a-png",
                content_type="image/png",
            )
        )

        with self.assertRaises(ValidationError):
            settings.full_clean()

    def test_settings_are_limited_to_the_singleton_primary_key(self) -> None:
        settings = LoginPageSettings(id=25, panel_title="عنوان")

        settings.save()

        self.assertEqual(settings.pk, 1)
        self.assertEqual(LoginPageSettings.objects.count(), 1)


class RequiredPasswordChangeTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="temporary-password-user",
            password="Temporary-password-2026",
            must_change_password=True,
        )

    def test_user_is_confined_until_personal_password_is_set(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:settings"))
        self.assertRedirects(response, reverse("accounts:required_password_change"))

        response = self.client.post(
            reverse("accounts:required_password_change"),
            {
                "new_password1": "Personal-password-2026",
                "new_password2": "Personal-password-2026",
            },
        )
        self.assertRedirects(response, reverse("organizations:select"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("Personal-password-2026"))
