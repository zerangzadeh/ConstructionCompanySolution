from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationSettings,
    OrganizationStatus,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    accept_organization_invitation,
    create_organization_invitation,
    create_organization_with_owner,
    get_organization_members,
    get_organization_settings,
    get_valid_memberships,
    resolve_active_organization,
    update_organization_settings,
)


class OrganizationTenantIsolationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="site-engineer",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Active Company",
            slug="active-company",
            created_by=self.user,
            updated_by=self.user,
        )
        self.other_organization = Organization.objects.create(
            name="Other Company",
            slug="other-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.other_organization,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.REVOKED,
        )

    def test_valid_memberships_exclude_revoked_memberships(self) -> None:
        memberships = get_valid_memberships(self.user)

        self.assertEqual(
            list(memberships.values_list("organization_id", flat=True)),
            [
                self.organization.id,
            ],
        )

    def test_user_cannot_resolve_another_organization(self) -> None:
        organization = resolve_active_organization(
            self.user,
            self.other_organization.id,
        )

        self.assertIsNone(organization)

    def test_single_membership_is_resolved_as_active_organization(self) -> None:
        organization = resolve_active_organization(self.user)

        self.assertEqual(organization, self.organization)

    def test_member_listing_requires_active_organization_membership(self) -> None:
        memberships = get_organization_members(
            user=self.user,
            organization=self.organization,
        )

        self.assertEqual(
            list(memberships),
            [
                self.user.organization_memberships.get(
                    organization=self.organization,
                )
            ],
        )
        with self.assertRaises(PermissionDenied):
            get_organization_members(
                user=self.other_user,
                organization=self.organization,
            )

    def test_switch_view_rejects_unauthorized_organization(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("organizations:switch"),
            {"organization_id": str(self.other_organization.id)},
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(
            ACTIVE_ORGANIZATION_SESSION_KEY,
            self.client.session,
        )

    def test_switch_view_stores_valid_organization(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("organizations:switch"),
            {"organization_id": str(self.organization.id)},
        )

        self.assertRedirects(response, reverse("organizations:select"))
        self.assertEqual(
            self.client.session[ACTIVE_ORGANIZATION_SESSION_KEY],
            str(self.organization.id),
        )

    def test_selection_view_is_available_to_authenticated_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:select"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.organization.name)

    def test_members_view_requires_active_organization(self) -> None:
        user_without_membership = User.objects.create_user(
            username="without-membership",
            password="test-password",
        )
        self.client.force_login(user_without_membership)

        response = self.client.get(reverse("organizations:members"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_members_view_is_scoped_to_active_organization(self) -> None:
        other_member = User.objects.create_user(
            username="other-member",
            password="test-password",
        )
        OrganizationMembership.objects.create(
            user=other_member,
            organization=self.other_organization,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            user=other_member,
            organization=self.organization,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:members"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)
        self.assertContains(response, other_member.username)
        self.assertNotContains(response, self.other_organization.name)

    def test_suspended_membership_is_not_valid(self) -> None:
        active_membership = self.user.organization_memberships.get(
            organization=self.organization,
        )
        active_membership.status = MembershipStatus.SUSPENDED
        active_membership.save(update_fields=["status"])

        self.assertFalse(get_valid_memberships(self.user).exists())
        self.assertIsNone(resolve_active_organization(self.user))

    def test_suspended_organization_is_not_valid(self) -> None:
        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save(update_fields=["status"])

        self.assertFalse(get_valid_memberships(self.user).exists())
        self.assertIsNone(resolve_active_organization(self.user))

    def test_cancelled_organization_is_not_valid(self) -> None:
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])

        self.assertFalse(get_valid_memberships(self.user).exists())
        self.assertIsNone(resolve_active_organization(self.user))

    def test_archived_organization_is_not_valid(self) -> None:
        self.organization.status = OrganizationStatus.ARCHIVED
        self.organization.save(update_fields=["status"])

        self.assertFalse(get_valid_memberships(self.user).exists())
        self.assertIsNone(resolve_active_organization(self.user))

    def test_soft_deleted_organization_is_not_valid(self) -> None:
        self.organization.deleted_at = timezone.now()
        self.organization.save(update_fields=["deleted_at"])

        self.assertFalse(get_valid_memberships(self.user).exists())
        self.assertIsNone(resolve_active_organization(self.user))

    def test_invalid_session_organization_is_cleared_by_middleware(self) -> None:
        self.client.force_login(self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.other_organization.id)
        session.save()

        response = self.client.get(reverse("organizations:select"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.session[ACTIVE_ORGANIZATION_SESSION_KEY],
            str(self.organization.id),
        )


class OrganizationCreationServiceTests(TestCase):
    def test_create_organization_creates_active_owner_membership(self) -> None:
        owner = User.objects.create_user(
            username="company-owner",
            password="test-password",
        )

        organization = create_organization_with_owner(
            owner=owner,
            name="New Construction Company",
            slug="new-construction-company",
            legal_name="New Construction Company LLC",
            timezone_name="America/New_York",
            currency="USD",
        )

        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=owner,
        )
        self.assertEqual(organization.created_by, owner)
        self.assertEqual(organization.updated_by, owner)
        self.assertEqual(membership.role, MembershipRole.OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertIsNotNone(membership.joined_at)
        self.assertEqual(organization.settings.timezone, "America/New_York")
        self.assertEqual(organization.settings.currency, "USD")

    def test_create_organization_rejects_unauthenticated_owner(self) -> None:
        owner = User(username="inactive-owner")

        with self.assertRaisesMessage(
            ValueError,
            "An authenticated user is required.",
        ):
            create_organization_with_owner(
                owner=owner,
                name="Invalid Company",
                slug="invalid-company",
            )

        self.assertFalse(Organization.objects.filter(slug="invalid-company").exists())


class OrganizationSettingsServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="settings-owner",
            password="test-password",
        )
        self.member = User.objects.create_user(
            username="settings-member",
            password="test-password",
        )
        self.other_owner = User.objects.create_user(
            username="other-settings-owner",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Settings Company",
            slug="settings-company",
            timezone="Asia/Tehran",
            currency="IRR",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Settings Company",
            slug="other-settings-company",
            created_by=self.other_owner,
            updated_by=self.other_owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.other_owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_get_settings_uses_legacy_values_when_compatibility_row_is_missing(
        self,
    ) -> None:
        settings_record = get_organization_settings(organization=self.organization)

        self.assertEqual(settings_record.timezone, "Asia/Tehran")
        self.assertEqual(settings_record.currency, "IRR")
        self.assertEqual(settings_record.fiscal_year_start_month, 1)
        self.assertEqual(
            OrganizationSettings.objects.filter(organization=self.organization).count(),
            1,
        )

    def test_update_is_scoped_and_dual_writes_legacy_values(self) -> None:
        settings_record = update_organization_settings(
            organization=self.organization,
            updated_by=self.owner,
            timezone_name="UTC",
            currency="USD",
            fiscal_year_start_month=4,
        )

        self.organization.refresh_from_db()
        self.assertEqual(settings_record.timezone, "UTC")
        self.assertEqual(settings_record.currency, "USD")
        self.assertEqual(self.organization.timezone, "UTC")
        self.assertEqual(self.organization.currency, "USD")
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                actor=self.owner,
                action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
                entity_id=str(settings_record.pk),
            ).exists()
        )

    def test_member_cannot_update_settings(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied,
            "You cannot update settings for this organization.",
        ):
            update_organization_settings(
                organization=self.organization,
                updated_by=self.member,
                timezone_name="UTC",
                currency="USD",
                fiscal_year_start_month=1,
            )

    def test_owner_cannot_update_another_organization_settings(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied,
            "You cannot update settings for this organization.",
        ):
            update_organization_settings(
                organization=self.other_organization,
                updated_by=self.owner,
                timezone_name="UTC",
                currency="USD",
                fiscal_year_start_month=1,
            )

    def test_suspended_organization_settings_cannot_be_updated(self) -> None:
        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save(update_fields=["status"])

        with self.assertRaisesMessage(
            PermissionDenied, "The organization is not active."
        ):
            update_organization_settings(
                organization=self.organization,
                updated_by=self.owner,
                timezone_name="UTC",
                currency="USD",
                fiscal_year_start_month=1,
            )


class OrganizationCreationViewTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="organization-creator",
            password="test-password",
        )

    def test_create_view_requires_authentication(self) -> None:
        response = self.client.get(reverse("organizations:create"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('organizations:create')}",
        )

    def test_create_view_renders_form_for_authenticated_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create organization")

    def test_create_view_creates_organization_for_current_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("organizations:create"),
            {
                "name": "Created Company",
                "legal_name": "Created Company LLC",
                "slug": "created-company",
                "timezone": "UTC",
                "currency": "USD",
            },
        )

        self.assertRedirects(response, reverse("organizations:select"))
        organization = Organization.objects.get(slug="created-company")
        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=self.user,
        )
        self.assertEqual(organization.created_by, self.user)
        self.assertEqual(membership.role, MembershipRole.OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(
            self.client.session[ACTIVE_ORGANIZATION_SESSION_KEY],
            str(organization.id),
        )


class OrganizationInvitationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="invitation-owner",
            password="test-password",
        )
        self.invitee = User.objects.create_user(
            username="invited-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Invitation Company",
            slug="invitation-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_invitation_stores_only_token_hash(self) -> None:
        invitation, raw_token = create_organization_invitation(
            organization=self.organization,
            invited_by=self.owner,
            invitee=self.invitee,
            role="member",
        )

        self.assertNotEqual(invitation.token_hash, raw_token)
        self.assertEqual(invitation.status, InvitationStatus.PENDING)
        self.assertEqual(len(invitation.token_hash), 64)

    def test_cancelled_organization_cannot_create_invitation(self) -> None:
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])

        with self.assertRaisesMessage(
            PermissionDenied,
            "The organization is not active.",
        ):
            create_organization_invitation(
                organization=self.organization,
                invited_by=self.owner,
                invitee=self.invitee,
            )

    def test_invitation_can_be_accepted_by_intended_user(self) -> None:
        invitation, raw_token = create_organization_invitation(
            organization=self.organization,
            invited_by=self.owner,
            invitee=self.invitee,
        )

        membership = accept_organization_invitation(
            token=raw_token,
            user=self.invitee,
        )

        invitation.refresh_from_db()
        self.assertEqual(membership.organization, self.organization)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)

    def test_invitation_cannot_be_accepted_by_another_user(self) -> None:
        invitation, raw_token = create_organization_invitation(
            organization=self.organization,
            invited_by=self.owner,
            invitee=self.invitee,
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "This invitation belongs to another user.",
        ):
            accept_organization_invitation(token=raw_token, user=self.owner)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.PENDING)

    def test_expired_invitation_is_rejected(self) -> None:
        invitation, raw_token = create_organization_invitation(
            organization=self.organization,
            invited_by=self.owner,
            invitee=self.invitee,
            expires_in=timedelta(days=-1),
        )

        with self.assertRaisesMessage(ValueError, "Invitation has expired."):
            accept_organization_invitation(token=raw_token, user=self.invitee)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.EXPIRED)
