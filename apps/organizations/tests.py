from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    OrganizationStatus,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    accept_organization_invitation,
    create_organization_by_system_admin,
    create_organization_invitation,
    create_organization_with_owner,
    get_organization_members,
    get_organization_settings,
    get_valid_memberships,
    resolve_active_organization,
    update_organization_membership,
    update_organization_settings,
)
from apps.projects.services import create_project


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
            role=MembershipRole.COMPANY_OWNER,
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


class OrganizationMembershipAccessServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="membership-owner", password="test-password"
        )
        self.member = User.objects.create_user(
            username="membership-member", password="test-password"
        )
        self.outsider = User.objects.create_user(
            username="membership-outsider", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="Membership Company",
            slug="membership-company",
            created_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Membership Company",
            slug="other-membership-company",
            created_by=self.outsider,
        )
        self.owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.member_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_membership = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_owner_can_change_member_role_and_change_is_audited(self) -> None:
        membership = update_organization_membership(
            organization=self.organization,
            actor=self.owner,
            membership=self.member_membership,
            role=MembershipRole.OPERATIONS_MANAGER,
            status=MembershipStatus.ACTIVE,
        )

        self.assertEqual(membership.role, MembershipRole.OPERATIONS_MANAGER)
        event = AuditEvent.objects.get(action=AuditAction.MEMBERSHIP_ROLE_CHANGED)
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.entity_id, str(self.member_membership.pk))
        self.assertEqual(event.metadata["previous_role"], MembershipRole.MEMBER)
        self.assertEqual(event.metadata["new_role"], MembershipRole.OPERATIONS_MANAGER)

    def test_membership_update_rejects_cross_tenant_record(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied, "عضویت متعلق به این سازمان نیست."
        ):
            update_organization_membership(
                organization=self.organization,
                actor=self.owner,
                membership=self.other_membership,
                role=MembershipRole.VIEWER,
                status=MembershipStatus.ACTIVE,
            )

    def test_non_manager_cannot_update_membership(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied, "اجازه مدیریت عضویت‌های این شرکت را ندارید."
        ):
            update_organization_membership(
                organization=self.organization,
                actor=self.member,
                membership=self.member_membership,
                role=MembershipRole.VIEWER,
                status=MembershipStatus.ACTIVE,
            )

    def test_last_active_owner_cannot_be_revoked(self) -> None:
        with self.assertRaisesMessage(
            ValueError, "سازمان باید حداقل یک مالک فعال داشته باشد."
        ):
            update_organization_membership(
                organization=self.organization,
                actor=self.owner,
                membership=self.owner_membership,
                role=MembershipRole.COMPANY_OWNER,
                status=MembershipStatus.REVOKED,
            )


class GlobalRoleAuthorizationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="custom-role-user")
        self.organization = Organization.objects.create(
            name="شرکت نقش سفارشی",
            slug="custom-role-company",
        )
        self.role = OrganizationRole.objects.create(
            code="project_coordinator",
            name="هماهنگ‌کننده پروژه",
        )
        self.permission = BusinessPermission.objects.get(
            code=BusinessPermissionCode.PROJECTS_MANAGE
        )
        self.role.permissions.add(self.permission)
        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role_definition=self.role,
            status=MembershipStatus.ACTIVE,
        )

    def test_permission_catalog_and_protected_roles_are_seeded(self) -> None:
        self.assertSetEqual(
            set(BusinessPermission.objects.values_list("code", flat=True)),
            set(BusinessPermissionCode.values),
        )
        self.assertSetEqual(
            set(
                OrganizationRole.objects.filter(is_system=True).values_list(
                    "code", flat=True
                )
            ),
            set(MembershipRole.values),
        )

    def test_custom_role_grants_implemented_business_permission(self) -> None:
        self.assertTrue(
            has_business_permission(
                user=self.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_MANAGE,
            )
        )
        self.assertFalse(
            has_business_permission(
                user=self.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PAYMENTS_MANAGE,
            )
        )

        project = create_project(
            organization=self.organization,
            actor=self.user,
            code="CUSTOM-ROLE-01",
            name="پروژه نقش سفارشی",
        )

        self.assertEqual(project.organization, self.organization)

    def test_deactivated_role_removes_tenant_access(self) -> None:
        self.role.is_active = False
        self.role.save(update_fields=["is_active", "updated_at"])

        self.assertFalse(
            get_valid_memberships(self.user).filter(pk=self.membership.pk).exists()
        )
        self.assertFalse(
            has_business_permission(
                user=self.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_MANAGE,
            )
        )

    def test_membership_manager_cannot_delegate_a_more_powerful_role(self) -> None:
        actor = User.objects.create_user(username="limited-membership-manager")
        target = User.objects.create_user(username="delegation-target")
        manager_role = OrganizationRole.objects.create(
            code="limited_membership_manager",
            name="مدیر محدود اعضا",
        )
        manager_role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.MEMBERSHIP_MANAGE
            )
        )
        powerful_role = OrganizationRole.objects.create(
            code="payment_operator",
            name="کارشناس پرداخت",
        )
        powerful_role.permissions.add(
            BusinessPermission.objects.get(code=BusinessPermissionCode.PAYMENTS_MANAGE)
        )
        actor_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=actor,
            role_definition=manager_role,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "نمی‌توانید نقشی با اختیارات بیشتر از نقش خود واگذار یا مدیریت کنید.",
        ):
            update_organization_membership(
                organization=self.organization,
                actor=actor,
                membership=self.membership,
                role=powerful_role,
                status=MembershipStatus.ACTIVE,
            )

        with self.assertRaisesMessage(
            PermissionDenied,
            "نمی‌توانید نقشی با اختیارات بیشتر از نقش خود واگذار یا مدیریت کنید.",
        ):
            create_organization_invitation(
                organization=self.organization,
                invited_by=actor,
                invitee=target,
                role=powerful_role,
            )

        actor_membership.refresh_from_db()
        self.assertEqual(actor_membership.role_definition, manager_role)

    def test_system_admin_has_global_tenant_access_without_membership(self) -> None:
        system_admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
        )

        project = create_project(
            organization=self.organization,
            actor=system_admin,
            code="ADMIN-01",
            name="پروژه ادمین سامانه",
        )

        self.assertEqual(project.created_by, system_admin)
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=system_admin,
            ).exists()
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
        self.assertEqual(membership.role, MembershipRole.COMPANY_OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertIsNotNone(membership.joined_at)
        self.assertEqual(organization.settings.timezone, "America/New_York")
        self.assertEqual(organization.settings.currency, "USD")

    def test_create_organization_rejects_unauthenticated_owner(self) -> None:
        owner = User(username="inactive-owner")

        with self.assertRaisesMessage(
            ValueError,
            "کاربر واردشده به سامانه الزامی است.",
        ):
            create_organization_with_owner(
                owner=owner,
                name="Invalid Company",
                slug="invalid-company",
            )

        self.assertFalse(Organization.objects.filter(slug="invalid-company").exists())

    def test_only_system_admin_can_request_organization_creation(self) -> None:
        organization_user = User.objects.create_user(
            username="organization-user",
            password="test-password",
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "فقط ادمین سامانه می‌تواند شرکت جدید ایجاد کند.",
        ):
            create_organization_by_system_admin(
                actor=organization_user,
                owner=organization_user,
                name="Unauthorized Company",
                slug="unauthorized-company",
            )

        self.assertFalse(
            Organization.objects.filter(slug="unauthorized-company").exists()
        )


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
            role=MembershipRole.COMPANY_OWNER,
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
            role=MembershipRole.COMPANY_OWNER,
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
            "اجازه به‌روزرسانی تنظیمات این شرکت را ندارید.",
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
            "به این شرکت دسترسی ندارید.",
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

        with self.assertRaisesMessage(PermissionDenied, "سازمان فعال نیست."):
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
        self.system_admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.test",
            password="test-password",
        )

    def test_create_view_requires_authentication(self) -> None:
        response = self.client.get(reverse("organizations:create"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('organizations:create')}",
        )

    def test_create_view_rejects_authenticated_organization_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:create"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response,
            "فقط ادمین سامانه می‌تواند شرکت جدید ایجاد کند.",
            status_code=403,
        )

    def test_create_view_renders_form_for_system_admin(self) -> None:
        self.client.force_login(self.system_admin)

        response = self.client.get(reverse("organizations:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ایجاد سازمان")

    def test_create_view_rejects_organization_user_post(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("organizations:create"),
            {
                "name": "Unauthorized Company",
                "legal_name": "Unauthorized Company LLC",
                "slug": "unauthorized-company",
                "timezone": "UTC",
                "currency": "USD",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Organization.objects.filter(slug="unauthorized-company").exists()
        )

    def test_create_view_creates_organization_for_system_admin(self) -> None:
        self.client.force_login(self.system_admin)

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
            user=self.system_admin,
        )
        self.assertEqual(organization.created_by, self.system_admin)
        self.assertEqual(membership.role, MembershipRole.COMPANY_OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(
            self.client.session[ACTIVE_ORGANIZATION_SESSION_KEY],
            str(organization.id),
        )

    def test_new_organization_links_are_hidden_from_organization_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:select"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("organizations:create"))
        self.assertContains(
            response,
            "از ادمین سامانه بخواهید شما را به یک شرکت اضافه کند.",
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
            role=MembershipRole.COMPANY_OWNER,
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
            "سازمان فعال نیست.",
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
            "این دعوت‌نامه متعلق به کاربر دیگری است.",
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

        with self.assertRaisesMessage(ValueError, "دعوت‌نامه منقضی شده است."):
            accept_organization_invitation(token=raw_token, user=self.invitee)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.EXPIRED)
