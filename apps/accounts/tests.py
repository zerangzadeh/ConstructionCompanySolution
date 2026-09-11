from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AccountStatus, User


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

    def test_valid_login_redirects_to_organization_selection(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.user.username,
                "password": self.password,
            },
        )

        self.assertRedirects(response, reverse("organizations:select"))
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
