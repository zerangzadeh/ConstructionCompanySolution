"""Approved Development reference discovery preserves platform and data boundaries."""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.services import create_organization_with_owner


@override_settings(DEBUG=True, REFERENCE_PERSONA_CATALOGUE_ENABLED=True)
class ReferencePersonaCatalogueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(
            username="reference-root", email="root@example.test", password="test-only"
        )
        cls.platform_admin = User.objects.create_user(username="reference-platform")
        assign_platform_admin(
            actor=cls.root,
            approver=cls.root,
            target=cls.platform_admin,
            reason="Reference catalogue boundary test",
        )
        cls.owner = User.objects.create_user(username="reference-owner")
        cls.tenant = create_organization_with_owner(
            owner=cls.owner, name="Protected tenant sentinel", slug="reference-tenant"
        )
        cls.url = reverse("organizations:reference_personas")

    def test_all_definitions_readable_without_tenant_data_or_mutation_controls(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get(self.url + "?organization=" + str(self.tenant.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b'data-reference-persona="'), 26)
        for marker in [
            "P-04",
            "P-15",
            "P-21",
            "P-26",
            "NOT_PROVISIONED",
            "BLOCKED",
            "2026-10-21",
        ]:
            self.assertContains(response, marker)
        self.assertNotContains(response, self.tenant.name)
        self.assertNotContains(response, self.owner.username)
        self.assertNotContains(response, 'href="/organizations/members/')
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertContains(response, "پرسوناهای مرجع توسعه")

    def test_platform_assignment_is_required_not_superuser_or_owner(self):
        for user in [self.owner, self.root]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_current_mapped_account_state_is_separate_from_dated_readiness(self):
        reference = User.objects.create_user(username="uiux.audit.project")
        self.client.force_login(self.platform_admin)
        response = self.client.get(self.url)
        self.assertContains(response, "حساب نگاشت‌شده فعال است")
        self.assertContains(response, "حساب نگاشت‌شده یافت نشد")
        self.assertContains(response, "در منبع نگاشت نشده")
        reference.is_active = False
        reference.save(update_fields=["is_active"])
        self.assertContains(self.client.get(self.url), "حساب نگاشت‌شده غیرفعال است")

    def test_revoked_platform_assignment_denies_access(self):
        from django.utils import timezone

        self.platform_admin.platform_role_assignments.update(revoked_at=timezone.now())
        self.client.force_login(self.platform_admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_mutation_methods_are_rejected(self):
        self.client.force_login(self.platform_admin)
        for method in ["post", "put", "patch", "delete"]:
            with self.subTest(method=method):
                self.assertEqual(
                    getattr(self.client, method)(self.url).status_code, 405
                )

    def test_disabled_and_non_development_configuration_fail_closed(self):
        self.client.force_login(self.platform_admin)
        for configuration in [
            {"REFERENCE_PERSONA_CATALOGUE_ENABLED": False},
            {"DEBUG": False},
        ]:
            with (
                self.subTest(configuration=configuration),
                override_settings(**configuration),
            ):
                self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_projection_remains_bound_to_approved_sources(self):
        catalogue = json.loads(
            Path(__file__)
            .with_name("reference_personas.json")
            .read_text(encoding="utf8")
        )
        for source in catalogue["sources"]:
            self.assertEqual(
                hashlib.sha256(
                    (settings.BASE_DIR / source["path"]).read_bytes()
                ).hexdigest(),
                source["sha256"],
            )
        self.assertEqual(
            {p["persona_id"] for p in catalogue["personas"]},
            {f"P-{i:02d}" for i in range(1, 27)},
        )
        allowed = {
            "persona_id",
            "label",
            "target_alias",
            "documented_identity",
            "documented_readiness",
            "authority_shape",
            "context_requirements",
            "scenario_ids",
        }
        self.assertTrue(all(set(p) == allowed for p in catalogue["personas"]))
