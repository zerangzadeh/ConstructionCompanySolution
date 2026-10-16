"""CEP-026 ESS identity, own-scope, masking and direct-route security tests."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    MembershipRole,
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
from apps.workforce.person_services import create_person, create_work_relationship


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
            resolve_ess_subject(
                user=self.unlinked_user, organization=self.organization
            )

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

    def test_navigation_visibility_follows_identity_but_does_not_grant_access(self):
        self._login(self.employee_user)
        self.assertTrue(
            has_ess_subject(user=self.employee_user, organization=self.organization)
        )
        response = self.client.get(reverse("home"))
        self.assertTrue(response.context["ess_subject_available"])
        self.assertContains(response, reverse("workforce:ess_profile"))

        self._login(self.unlinked_user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("workforce:ess_profile"))
        self.assertContains(response, "خدمات من")
        self.assertEqual(
            self.client.get(reverse("workforce:ess_profile")).status_code, 403
        )

    def test_inactive_membership_is_denied_even_with_authoritative_identity(self):
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.employee_user
        )
        membership.status = MembershipStatus.SUSPENDED
        membership.save(update_fields={"status"})
        with self.assertRaises(PermissionDenied):
            resolve_ess_subject(
                user=self.employee_user, organization=self.organization
            )
