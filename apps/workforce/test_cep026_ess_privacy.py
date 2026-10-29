"""CEP-026 ESS identity, own-scope, masking and direct-route security tests."""

from datetime import timedelta
from html.parser import HTMLParser

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.workforce.ess_services import (
    get_own_profile,
    has_ess_subject,
    resolve_ess_subject,
)
from apps.workforce.models import WorkRelationship
from apps.workforce.person_services import (
    create_person,
    create_work_relationship,
    end_work_relationship,
)


class _NavigationParser(HTMLParser):
    def __init__(self, content: bytes) -> None:
        super().__init__()
        self.entries = []
        self.in_navigation = False
        self.feed(content.decode())

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "nav":
            self.in_navigation = "data-product-navigation" in attributes
        if self.in_navigation and tag == "a" and "href" in attributes:
            self.entries.append((tag, attributes))

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_navigation = False

    def links(self, nav_id):
        return [attrs for tag, attrs in self.entries if attrs.get("data-nav-id") == nav_id]

    def links_to(self, url):
        return [attrs for tag, attrs in self.entries if attrs.get("href") == url]


@override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
class ESSOwnDataPrivacyTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="cep026-owner")
        self.employee_user = User.objects.create_user(
            username="cep026-employee",
            email="employee@example.test",
            national_id="0013547839",
        )
        self.other_user = User.objects.create_user(username="cep026-other")
        self.unlinked_user = User.objects.create_user(
            username="E-026", email="employee@example.test"
        )
        self.organization = create_organization_with_owner(
            owner=self.owner, name="CEP026", slug="cep026"
        )
        viewer_role = OrganizationRole.objects.get(
            code=MembershipRole.VIEWER, organization__isnull=True
        )
        for user in (self.employee_user, self.other_user, self.unlinked_user):
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=viewer_role.code,
                role_definition=viewer_role,
                status=MembershipStatus.ACTIVE,
            )
        self.person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="Ali",
            last_name="Karimi",
            user=self.employee_user,
        )
        self.relationship = create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=self.person,
            employee_number="E-026",
            effective_start=timezone.localdate() - timedelta(days=30),
        )
        other_person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="Sara",
            last_name="Ahmadi",
            user=self.other_user,
        )
        self.other_relationship = create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=other_person,
            employee_number="E-027",
            effective_start=timezone.localdate() - timedelta(days=10),
        )

    def _login(self, user: User) -> None:
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def test_authoritative_user_person_relationship_resolution_allows_own_data(self):
        subject = resolve_ess_subject(
            user=self.employee_user, organization=self.organization
        )
        self.assertEqual(subject.person.pk, self.person.pk)
        self.assertEqual(subject.current_relationship.pk, self.relationship.pk)

        profile = get_own_profile(
            user=self.employee_user, organization=self.organization
        )
        self.assertEqual(profile.relationship.pk, self.relationship.pk)
        self.assertEqual(profile.masked_national_id, "••••••7839")

    def test_username_email_and_employee_number_similarity_never_infer_identity(self):
        with self.assertRaises(PermissionDenied):
            resolve_ess_subject(user=self.unlinked_user, organization=self.organization)

    def test_other_person_and_cross_tenant_relationships_are_denied(self):
        with self.assertRaises(PermissionDenied):
            get_own_profile(
                user=self.employee_user,
                organization=self.organization,
                relationship_id=str(self.other_relationship.pk),
            )

        future_relationship = WorkRelationship.objects.create(
            organization=self.organization,
            person=self.person,
            employee_number="E-026-FUTURE",
            effective_start=timezone.localdate() + timedelta(days=30),
        )
        with self.assertRaises(PermissionDenied):
            get_own_profile(
                user=self.employee_user,
                organization=self.organization,
                relationship_id=str(future_relationship.pk),
            )

        other_owner = User.objects.create_user(username="cep026-other-owner")
        other_organization = create_organization_with_owner(
            owner=other_owner, name="CEP026 Other", slug="cep026-other"
        )
        other_tenant_person = create_person(
            organization=other_organization,
            actor=other_owner,
            first_name="Other",
            last_name="Tenant",
            user=other_owner,
        )
        cross_tenant = create_work_relationship(
            organization=other_organization,
            actor=other_owner,
            person=other_tenant_person,
            employee_number="OT-026",
            effective_start=timezone.localdate() - timedelta(days=1),
        )
        with self.assertRaises(PermissionDenied):
            get_own_profile(
                user=self.employee_user,
                organization=self.organization,
                relationship_id=str(cross_tenant.pk),
            )

    def test_direct_url_masks_sensitive_field_and_discloses_no_other_object(self):
        self._login(self.employee_user)
        own_response = self.client.get(reverse("workforce:ess_profile"))
        self.assertEqual(own_response.status_code, 200)
        self.assertContains(own_response, "••••••7839")
        self.assertNotContains(own_response, "0013547839")
        self.assertNotContains(own_response, 'name="national_id"')

        other_url = reverse(
            "workforce:ess_profile_relationship",
            kwargs={"relationship_id": self.other_relationship.pk},
        )
        missing_url = reverse(
            "workforce:ess_profile_relationship",
            kwargs={"relationship_id": "00000000-0000-0000-0000-000000000001"},
        )
        other_response = self.client.get(other_url)
        missing_response = self.client.get(missing_url)
        self.assertEqual(other_response.status_code, 403)
        self.assertEqual(missing_response.status_code, 403)
        self.assertEqual(other_response.content, missing_response.content)
        self.assertNotContains(other_response, "Sara", status_code=403)
        self.assertNotContains(other_response, "E-027", status_code=403)

    def test_internal_profile_identity_gate_survives_current_navigation(self):
        self._login(self.employee_user)
        self.assertTrue(
            has_ess_subject(user=self.employee_user, organization=self.organization)
        )
        response = self.client.get(reverse("home"))
        self.assertTrue(response.context["ess_subject_available"])
        navigation = _NavigationParser(response.content)
        # MVP-01 replaced the retired NAV-006 menu even in internal verification.
        self.assertEqual(navigation.links_to(reverse("workforce:ess_dashboard")), [])
        dashboard = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertContains(dashboard, "داشبورد خدمات من")
        self.assertEqual(
            dashboard.context["dashboard"].profile.person.pk, self.person.pk
        )
        self.assertNotContains(dashboard, self.other_relationship.employee_number)

        self._login(self.unlinked_user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("workforce:ess_dashboard"))
        self.assertNotContains(response, 'data-nav-id="NAV-006"')
        self.assertEqual(
            self.client.get(reverse("workforce:ess_dashboard")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("workforce:ess_profile")).status_code, 403
        )

    def test_multi_role_employee_retains_other_authorized_navigation(self):
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.employee_user
        )
        for code in (MembershipRole.VIEWER, MembershipRole.ACCOUNTANT):
            MembershipRoleAssignment.objects.create(
                organization=self.organization,
                membership=membership,
                role=OrganizationRole.objects.get(code=code, organization__isnull=True),
                reason="Synthetic ESS navigation regression fixture",
            )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Synthetic ESS navigation regression fixture",
        )
        self._login(self.employee_user)
        response = self.client.get(reverse("home"))
        entries = _NavigationParser(response.content)
        self.assertTrue(response.context["ess_subject_available"])
        self.assertEqual(entries.links_to(reverse("workforce:ess_dashboard")), [])
        for route in ("projects:list", "expenses:list"):
            url = reverse(route)
            self.assertEqual(len(entries.links_to(url)), 2)  # Desktop and mobile.
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("workforce:ess_dashboard")).status_code, 200
        )

    def _assert_ess_navigation_and_direct_url_denied(self):
        self._login(self.employee_user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'data-nav-id="NAV-006"')
        self.assertEqual(
            self.client.get(reverse("workforce:ess_dashboard")).status_code, 403
        )

    def test_expired_identity_hides_entry_and_denies_direct_url(self):
        end_work_relationship(
            organization=self.organization,
            actor=self.owner,
            relationship=self.relationship,
            effective_end=timezone.localdate() - timedelta(days=1),
        )
        self._assert_ess_navigation_and_direct_url_denied()

    def test_ambiguous_identity_hides_entry_and_denies_direct_url(self):
        # Deliberately corrupt synthetic data: the resolver must still fail closed.
        WorkRelationship.objects.create(
            organization=self.organization,
            person=self.person,
            employee_number="E-026-AMBIGUOUS",
            effective_start=timezone.localdate() - timedelta(days=1),
        )
        self._assert_ess_navigation_and_direct_url_denied()

    def test_inactive_membership_is_denied_even_with_authoritative_identity(self):
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.employee_user
        )
        membership.status = MembershipStatus.SUSPENDED
        membership.save(update_fields={"status"})
        with self.assertRaises(PermissionDenied):
            resolve_ess_subject(user=self.employee_user, organization=self.organization)
        self._login(self.employee_user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'data-nav-id="NAV-006"', status_code=403)
        # Re-select the stale tenant: the first rejected request clears it.
        self._login(self.employee_user)
        self.assertEqual(
            self.client.get(reverse("workforce:ess_dashboard")).status_code, 403
        )
