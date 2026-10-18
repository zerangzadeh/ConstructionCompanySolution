"""CEP-030: real source delegation, granular authority and tenant-safe UI."""

import os
from pathlib import Path
from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)

from . import services
from .models import BusinessParty, PartyRestriction
from .presentation import GOVERNANCE_PERMISSIONS


class PartySurfaceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="شرکت آزمایشی بنیرا", slug="cep030"
        )
        OrganizationSettings.objects.create(
            organization=self.organization, timezone="Asia/Tehran"
        )
        self.other = Organization.objects.create(name="Other", slug="cep030-other")
        self.owner = self.member("steward", {P.PARTIES_VIEW, *GOVERNANCE_PERMISSIONS})
        self.reader = self.member("reader", {P.PARTIES_VIEW})
        self.party = services.create_business_party(
            actor=self.owner,
            organization=self.organization,
            party_kind="company",
            display_name="شرکت سازه پارس",
            tax_identifier="SYNTHETIC-030",
        )
        self.foreign = BusinessParty.objects.create(
            organization=self.other,
            party_kind="company",
            display_name="PRIVATE-FOREIGN",
        )
        self.login(self.owner)

    def member(self, name, codes, *, scoped=True):
        user = User.objects.create_user(username="cep030-" + name)
        role = OrganizationRole.objects.create(code="cep030-" + name, name=name)
        role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status="active",
        )
        if scoped:
            MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=membership,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="Synthetic CEP030",
            )
        return user

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def url(self, name="governance_detail", party=None, **kwargs):
        if name in {
            "governance_detail",
            "governance_action",
            "detail",
            "archive",
            "role_create",
            "contact_create",
        }:
            kwargs["party_id"] = (party or self.party).pk
        return reverse("parties:" + name, kwargs=kwargs)

    def action(self, name, data, party=None):
        return self.client.post(
            self.url("governance_action", party, action=name),
            {f"{name}-{key}": value for key, value in data.items()},
        )

    def capture(self, name, response):
        if root := os.environ.get("CEP030_CAPTURE_DIR"):
            path = Path(root)
            path.mkdir(parents=True, exist_ok=True)
            import re

            html = re.sub(
                r'(<input[^>]+name="csrfmiddlewaretoken"[^>]+value=")[^"]+',
                r"\1SYNTHETIC",
                response.content.decode(),
            )
            (path / f"{name}.html").write_text(html, encoding="utf-8")

    def test_operational_filters_and_sort_use_source_fields(self):
        self.login(self.reader)
        response = self.client.get(
            self.url("list"),
            {"kind": "company", "tax_id": "SYNTHETIC", "sort": "tax_id"},
        )
        self.assertContains(response, self.party.display_name)
        self.assertNotContains(response, self.foreign.display_name)
        self.assertNotContains(response, self.url("governance"))
        self.capture("operational", response)

    def test_operational_detail_is_read_only(self):
        self.login(self.reader)
        response = self.client.get(self.url("detail"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            'method="post"',
            response.content.decode().split("<main", 1)[1].split("</main>", 1)[0],
        )
        self.assertNotContains(response, "تاریخچه نسخه‌های هویت")

    def test_reader_cannot_enter_or_mutate_master(self):
        self.login(self.reader)
        for name in ("governance", "governance_detail"):
            response = self.client.get(self.url(name))
            self.assertEqual(response.status_code, 403)
            self.capture("denied", response)
        self.assertEqual(
            self.client.post(
                self.url("detail"), {"display_name": "ATTACK"}
            ).status_code,
            403,
        )
        self.assertEqual(self.action("alias", {"value": "ATTACK"}).status_code, 403)
        self.party.refresh_from_db()
        self.assertEqual(self.party.display_name, "شرکت سازه پارس")
        self.assertFalse(self.party.aliases.exists())

    def test_master_entry_needs_view_and_explicit_scope(self):
        for user in (
            self.member("no-view", {P.PARTY_GOVERNANCE_MANAGE}),
            self.member(
                "no-scope", {P.PARTIES_VIEW, P.PARTY_GOVERNANCE_MANAGE}, scoped=False
            ),
        ):
            self.login(user)
            self.assertEqual(self.client.get(self.url("governance")).status_code, 403)

    def test_granular_permissions_do_not_imply_one_another(self):
        user = self.member("merge-only", {P.PARTIES_VIEW, P.PARTIES_MERGE})
        self.login(user)
        response = self.client.get(self.url())
        self.assertContains(response, self.url("governance_action", action="merge"))
        for action in (
            "alias",
            "restriction",
            "representative",
            "classification_create",
        ):
            self.assertNotContains(
                response, self.url("governance_action", action=action)
            )
            self.assertEqual(self.action(action, {}).status_code, 403)
        self.assertNotContains(response, "تاریخچه نسخه‌های هویت")

    def test_missing_and_foreign_master_are_indistinguishable(self):
        foreign = self.client.get(self.url(party=self.foreign))
        missing = self.client.get(
            reverse("parties:governance_detail", kwargs={"party_id": uuid4()})
        )
        self.assertEqual(foreign.status_code, 403)
        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertTemplateUsed(foreign, "parties/unavailable.html")
        self.assertTemplateUsed(missing, "parties/unavailable.html")
        self.assertNotContains(missing, "PRIVATE-FOREIGN", status_code=403)
        self.assertNotContains(foreign, "PRIVATE-FOREIGN", status_code=403)
        self.assertEqual(
            self.action("alias", {"value": "ATTACK"}, self.foreign).status_code, 403
        )

    def test_alias_delegates_audited_source_and_ignores_posted_tenant(self):
        response = self.action(
            "alias",
            {
                "alias_type": "other",
                "value": "نام پیشین",
                "reason": "شاهد آزمایشی",
                "organization": str(self.other.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        alias = self.party.aliases.get()
        self.assertEqual(alias.organization_id, self.organization.pk)
        self.assertEqual(alias.recorded_by_id, self.owner.pk)
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(alias.pk)).exists())

    def test_classification_lifecycle_uses_source_history(self):
        self.assertEqual(
            self.action(
                "classification_create",
                {"kind": "tag", "code": "SYNTHETIC", "name": "همکار آزمایشی"},
            ).status_code,
            302,
        )
        classification = self.organization.party_classifications.get()
        self.assertEqual(
            self.action(
                "classification_assign", {"classification": str(classification.pk)}
            ).status_code,
            302,
        )
        assignment = self.party.classification_assignments.get()
        self.assertEqual(
            self.action(
                "classification_revoke",
                {"assignment": str(assignment.pk), "reason": "پایان انتساب"},
            ).status_code,
            302,
        )
        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.revoked_at)

    def test_representative_evidence_jalali_timezone_and_revocation(self):
        response = self.action(
            "representative",
            {
                "authority": "signatory",
                "full_name": "نماینده آزمایشی",
                "evidence_reference": "SYNTHETIC-EVIDENCE",
                "effective_from": "1405/01/02 09:30",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = self.party.representatives.get()
        self.assertEqual(row.effective_from.utcoffset().total_seconds(), 0)
        self.assertEqual(row.effective_from.hour, 6)
        self.assertEqual(
            self.action(
                "representative_revoke",
                {"representative": str(row.pk), "reason": "پایان اختیار"},
            ).status_code,
            302,
        )
        row.refresh_from_db()
        self.assertIsNotNone(row.revoked_at)

    def test_tenant_restriction_revoke_preserves_record(self):
        self.assertEqual(
            self.action(
                "restriction",
                {
                    "code": "SYNTHETIC",
                    "effect": "information_only",
                    "reason": "شاهد آزمایشی",
                },
            ).status_code,
            302,
        )
        row = self.party.restrictions.get()
        self.assertEqual(row.scope, "tenant")
        self.assertEqual(
            self.action(
                "restriction_revoke", {"restriction": str(row.pk), "reason": "پایان"}
            ).status_code,
            302,
        )
        row.refresh_from_db()
        self.assertIsNotNone(row.revoked_at)

    def test_platform_restriction_is_never_exposed_or_revocable(self):
        from django.utils import timezone

        row = PartyRestriction.objects.create(
            organization=self.organization,
            party=self.party,
            scope="platform",
            code="PRIVATE-PLATFORM",
            effect="information_only",
            reason="PRIVATE-PLATFORM-REASON",
            effective_from=timezone.now(),
            created_by=self.owner,
        )
        response = self.client.get(self.url())
        self.assertNotContains(response, "PRIVATE-PLATFORM")
        self.assertEqual(
            self.action(
                "restriction_revoke", {"restriction": str(row.pk), "reason": "ATTACK"}
            ).status_code,
            400,
        )
        row.refresh_from_db()
        self.assertIsNone(row.revoked_at)

    def test_related_choices_reject_foreign_and_wrong_party(self):
        self.assertEqual(
            self.action(
                "merge",
                {"survivor": str(self.foreign.pk), "reason": "ATTACK", "confirm": "on"},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.action(
                "classification_assign", {"classification": str(uuid4())}
            ).status_code,
            400,
        )
        second = services.create_business_party(
            actor=self.owner,
            organization=self.organization,
            party_kind="company",
            display_name="دوم",
        )
        alias = services.record_party_representative(
            actor=self.owner,
            organization=self.organization,
            party=second,
            authority="representative",
            full_name="Private second",
            evidence_reference="SYNTHETIC",
        )
        self.assertEqual(
            self.action(
                "representative_revoke",
                {"representative": str(alias.pk), "reason": "ATTACK"},
            ).status_code,
            400,
        )

    def test_merge_requires_confirmation_and_preserves_source_identity(self):
        target = services.create_business_party(
            actor=self.owner,
            organization=self.organization,
            party_kind="company",
            display_name="طرف مرجع",
        )
        data = {"survivor": str(target.pk), "reason": "تأیید هویت یکسان"}
        self.assertEqual(self.action("merge", data).status_code, 400)
        self.assertEqual(
            self.action("merge", data | {"confirm": "on"}).status_code, 302
        )
        self.party.refresh_from_db()
        self.assertEqual(self.party.merged_into_id, target.pk)
        self.assertIsNotNone(self.party.archived_at)
        self.assertTrue(self.party.identity_snapshots.exists())
        self.capture("merged", self.client.get(self.url()))
        self.assertNotContains(
            self.client.get(self.url("list")), self.party.display_name
        )

    def test_identity_revision_legacy_post_uses_single_service(self):
        response = self.client.post(
            self.url("detail"),
            {
                "party_kind": "company",
                "display_name": "نام جدید",
                "legal_name": "",
                "tax_identifier": "SYNTHETIC-030",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.party.refresh_from_db()
        self.assertEqual(self.party.display_name, "نام جدید")
        self.assertEqual(self.party.identity_snapshots.count(), 2)

    def test_invalid_and_empty_states_are_explicit(self):
        response = self.action(
            "alias", {"alias_type": "other", "value": "", "reason": ""}
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["actions"][0]["form"].errors)
        self.capture("validation", response)
        empty = self.client.get(self.url("list"), {"name": "NO-SYNTHETIC-MATCH"})
        self.assertContains(empty, "طرف تجاری مجازی برای نمایش موجود نیست")
        self.capture("empty", empty)

    def test_governance_layout_dates_cache_and_navigation(self):
        response = self.client.get(self.url())
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "تاریخچه نسخه‌های هویت")
        self.assertContains(response, 'data-nav-id="NAV-043"')
        self.assertIn("private, no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
        self.capture("governance", response)
        self.capture("master-list", self.client.get(self.url("governance")))

    def test_csrf_and_method_restrictions(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        session = secure.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(
            secure.post(self.url("governance_action", action="alias"), {}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(self.url("governance_action", action="alias")).status_code,
            405,
        )
        self.assertEqual(self.action("unknown", {}).status_code, 404)

    def test_suspended_tenant_and_inactive_membership_cannot_mutate(self):
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        self.assertEqual(
            self.action(
                "alias", {"alias_type": "other", "value": "ATTACK", "reason": "ATTACK"}
            ).status_code,
            403,
        )
        self.assertFalse(self.party.aliases.exists())

    def test_existing_create_role_contact_and_archive_routes(self):
        response = self.client.post(
            self.url("create"),
            {
                "party_kind": "individual",
                "display_name": "شخص آزمایشی",
                "legal_name": "",
                "tax_identifier": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.post(self.url("role_create"), {"role": "supplier"}).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                self.url("contact_create"),
                {
                    "contact_type": "email",
                    "value": "synthetic@example.invalid",
                    "label": "آزمایشی",
                    "is_primary": "on",
                },
            ).status_code,
            302,
        )
        self.assertEqual(self.party.roles.get().role, "supplier")
        self.assertEqual(self.party.contacts.get().value, "synthetic@example.invalid")
        self.assertEqual(self.client.post(self.url("archive")).status_code, 302)
        self.party.refresh_from_db()
        self.assertIsNotNone(self.party.archived_at)
        self.assertEqual(
            self.action(
                "alias", {"alias_type": "other", "value": "ATTACK", "reason": "ATTACK"}
            ).status_code,
            400,
        )

    def test_reader_cannot_use_existing_mutation_routes(self):
        self.login(self.reader)
        for name in ("create", "archive", "role_create", "contact_create"):
            self.assertEqual(self.client.post(self.url(name), {}).status_code, 403)

    def test_revoked_membership_and_missing_session_fail_closed(self):
        OrganizationMembership.objects.filter(
            user=self.owner, organization=self.organization
        ).update(status="inactive")
        self.assertEqual(self.action("alias", {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_governance_grant_does_not_imply_merge_or_restriction(self):
        self.login(
            self.member("governance-only", {P.PARTIES_VIEW, P.PARTY_GOVERNANCE_MANAGE})
        )
        self.assertEqual(
            self.action(
                "alias",
                {"alias_type": "other", "value": "آزمایشی", "reason": "آزمایشی"},
            ).status_code,
            302,
        )
        self.assertEqual(self.action("merge", {}).status_code, 403)
        self.assertEqual(self.action("restriction", {}).status_code, 403)
