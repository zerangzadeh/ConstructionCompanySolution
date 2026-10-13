import tempfile

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.authorization import has_business_permission
from apps.organizations.forms import (
    ExistingAccountConnectionForm,
    OrganizationAccountCreateForm,
    OrganizationMembershipForm,
    OrganizationSettingsForm,
)
from apps.organizations.models import (
    AccountConnectionRequestStatus,
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    OrganizationStatus,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_account,
    create_organization_by_system_admin,
    create_organization_with_owner,
    get_organization_members,
    get_organization_settings,
    get_valid_memberships,
    provision_user_for_organization,
    request_existing_account_connection,
    reset_organization_member_password,
    resolve_active_organization,
    respond_to_account_connection_request,
    set_active_organization,
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
        owner_membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=owner_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Tenant isolation fixture requires explicit owner scope",
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

        self.assertRedirects(response, reverse("financials:dashboard"))
        self.assertEqual(
            self.client.session[ACTIVE_ORGANIZATION_SESSION_KEY],
            str(self.organization.id),
        )

    def test_account_forms_disable_username_autocomplete(self) -> None:
        create_form = OrganizationAccountCreateForm(allow_owner_role=True)
        connection_form = ExistingAccountConnectionForm(allow_owner_role=True)

        self.assertEqual(
            create_form.fields["username"].widget.attrs["autocomplete"], "off"
        )
        self.assertEqual(
            connection_form.fields["username"].widget.attrs["autocomplete"],
            "off",
        )

    def test_selection_view_is_available_to_authenticated_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:select"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.organization.name)

    def test_legacy_member_update_cannot_assign_a_role(self) -> None:
        pending_user = User.objects.create_user(
            username="pending-member",
            password="test-password",
            is_active=False,
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=pending_user,
            role="",
            role_definition=None,
            status=MembershipStatus.PENDING_ROLE,
            assigned_by=self.user,
        )
        self.client.force_login(self.user)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        response = self.client.post(
            reverse("organizations:member_update", args=[membership.pk]),
            {
                "role_definition": MembershipRole.MEMBER,
                "status": MembershipStatus.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        pending_user.refresh_from_db()
        self.assertEqual(membership.role, "")
        self.assertEqual(membership.status, MembershipStatus.PENDING_ROLE)
        self.assertFalse(pending_user.is_active)

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

    def test_members_view_links_member_name_to_the_edit_page_for_managers(self) -> None:
        membership = self.user.organization_memberships.get(
            organization=self.organization,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("organizations:members"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("organizations:member_update", args=[membership.pk]),
        )
        self.assertNotContains(response, "مدیریت عضویت")

    def test_members_view_displays_a_scoped_member_avatar(self) -> None:
        membership = self.user.organization_memberships.get(
            organization=self.organization,
        )
        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            self.user.profile_image.save(
                "avatar.png",
                SimpleUploadedFile(
                    "avatar.png",
                    b"\x89PNG\r\n\x1a\nmember-avatar",
                    content_type="image/png",
                ),
            )
            self.client.force_login(self.user)

            response = self.client.get(reverse("organizations:members"))

            image_url = reverse(
                "organizations:member_profile_image",
                args=[membership.pk],
            )
            self.assertContains(response, image_url)

            image_response = self.client.get(image_url)

            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response["Content-Type"], "image/png")
            self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")
            self.assertTrue(
                b"".join(image_response.streaming_content).startswith(b"\x89PNG")
            )

    def test_member_avatar_endpoint_is_scoped_to_the_active_organization(self) -> None:
        other_membership = OrganizationMembership.objects.create(
            user=self.other_user,
            organization=self.other_organization,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "organizations:member_profile_image",
                args=[other_membership.pk],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_member_management_page_displays_user_profile_details(self) -> None:
        membership = self.user.organization_memberships.get(
            organization=self.organization,
        )
        self.user.first_name = "سارا"
        self.user.last_name = "احمدی"
        self.user.email = "sara@example.com"
        self.user.phone_number = "09120000000"
        self.user.save(
            update_fields=["first_name", "last_name", "email", "phone_number"]
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("organizations:member_update", args=[membership.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مشخصات کاربر")
        self.assertContains(response, "سارا")
        self.assertContains(response, "احمدی")
        self.assertContains(response, "sara@example.com")
        self.assertContains(response, "09120000000")
        self.assertContains(response, membership.user.account_status_label)
        self.assertContains(response, "آخرین ورود")

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
        self.organization.archived_at = timezone.now()
        self.organization.save(update_fields=["status", "archived_at"])

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
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.owner_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Membership access fixture requires explicit owner scope",
        )

    def test_legacy_membership_service_rejects_role_changes(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied, "تغییر نقش از مسیر سازگار قدیمی غیرفعال است"
        ):
            update_organization_membership(
                organization=self.organization,
                actor=self.owner,
                membership=self.member_membership,
                role=MembershipRole.OPERATIONS_MANAGER,
                status=MembershipStatus.ACTIVE,
            )

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
            PermissionDenied, "تغییر نقش از مسیر سازگار قدیمی غیرفعال است"
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
            code=BusinessPermissionCode.PROJECTS_CREATE
        )
        self.role.permissions.add(self.permission)
        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role_definition=self.role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Custom role fixture requires explicit scope",
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
        self.assertGreaterEqual(len(BusinessPermissionCode.values), 100)
        self.assertFalse(
            BusinessPermission.objects.filter(code="projects.manage").exists()
        )

    def test_builtin_roles_have_english_display_names(self) -> None:
        self.assertDictEqual(
            dict(
                OrganizationRole.objects.filter(is_system=True).values_list(
                    "code", "name"
                )
            ),
            {
                MembershipRole.COMPANY_OWNER: "Company Owner",
                MembershipRole.COMPANY_MANAGER: "Company Manager",
                MembershipRole.OPERATIONS_MANAGER: "Operations Manager",
                MembershipRole.MEMBER: "Member",
                MembershipRole.VIEWER: "Viewer",
                MembershipRole.TENANT_OWNER: "Tenant Owner",
                MembershipRole.TENANT_ADMIN: "Tenant Admin",
                MembershipRole.TENANT_MANAGER: "Tenant Manager",
                MembershipRole.PROJECT_MANAGER: "Project Manager",
                MembershipRole.ACCOUNTANT: "Accountant",
                MembershipRole.SUPERVISOR: "Supervisor",
            },
        )

    def test_membership_role_field_explains_it_is_not_a_job_position(self) -> None:
        form = OrganizationMembershipForm()

        self.assertEqual(
            form.fields["role_definition"].help_text,
            "این مورد سطح دسترسی به سامانه را تعیین می‌کند و سمت شغلی فرد نیست.",
        )

    def test_custom_role_grants_implemented_business_permission(self) -> None:
        self.assertTrue(
            has_business_permission(
                user=self.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_CREATE,
            )
        )
        self.assertFalse(
            has_business_permission(
                user=self.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
            )
        )
        self.assertFalse(
            has_business_permission(
                user=self.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PAYMENTS_CREATE,
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
                permission=BusinessPermissionCode.PROJECTS_CREATE,
            )
        )

    def test_legacy_membership_service_cannot_delegate_roles(self) -> None:
        actor = User.objects.create_user(username="limited-membership-manager")
        manager_role = OrganizationRole.objects.create(
            code="limited_membership_manager",
            name="مدیر محدود اعضا",
        )
        manager_role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE
            )
        )
        powerful_role = OrganizationRole.objects.create(
            code="payment_operator",
            name="کارشناس پرداخت",
        )
        powerful_role.permissions.add(
            BusinessPermission.objects.get(code=BusinessPermissionCode.PAYMENTS_CREATE)
        )
        actor_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=actor,
            role_definition=manager_role,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "تغییر نقش از مسیر سازگار قدیمی غیرفعال است",
        ):
            update_organization_membership(
                organization=self.organization,
                actor=actor,
                membership=self.membership,
                role=powerful_role,
                status=MembershipStatus.ACTIVE,
            )

        actor_membership.refresh_from_db()
        self.assertEqual(actor_membership.role_definition, manager_role)

    def test_system_admin_has_no_tenant_access_without_membership(self) -> None:
        system_admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
        )

        with self.assertRaises(PermissionDenied):
            create_project(
                organization=self.organization,
                actor=system_admin,
                code="ADMIN-01",
                name="پروژه ادمین سامانه",
            )
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=system_admin,
            ).exists()
        )


class OrganizationProfileAndSettingsValidationTests(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(
            name="شرکت اعتبارسنجی",
            slug="validation-company",
            national_id="NATIONAL-100",
            economic_code="ECONOMIC-100",
        )

    def test_nonblank_identifiers_are_canonical_and_unique(self) -> None:
        duplicate = Organization(
            name="شرکت تکراری",
            slug="duplicate-company",
            national_id="national-100",
            economic_code="different-code",
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.national_id, "NATIONAL-100")

    def test_archive_status_and_timestamp_must_be_consistent(self) -> None:
        self.organization.status = OrganizationStatus.ARCHIVED

        with self.assertRaises(ValidationError):
            self.organization.full_clean()

        self.organization.archived_at = timezone.now()
        self.organization.full_clean()
        self.assertFalse(self.organization.is_active)

    def test_settings_reject_invalid_timezone_and_fiscal_date(self) -> None:
        settings_record = OrganizationSettings(
            organization=self.organization,
            timezone="Invalid/Timezone",
            fiscal_year_start_month=2,
            fiscal_year_start_day=30,
        )

        with self.assertRaises(ValidationError) as context:
            settings_record.full_clean()

        self.assertIn("timezone", context.exception.message_dict)
        self.assertIn("fiscal_year_start_day", context.exception.message_dict)

    def test_logo_form_validates_type_size_and_signature(self) -> None:
        valid_logo = SimpleUploadedFile(
            "logo.png",
            b"\x89PNG\r\n\x1a\nlogo-data",
            content_type="image/png",
        )
        form = OrganizationSettingsForm(
            data={
                "language": "fa",
                "timezone": "Asia/Tehran",
                "currency": "IRR",
                "fiscal_year_start_month": 1,
                "fiscal_year_start_day": 1,
                "project_code_prefix": "PRJ",
                "contract_code_prefix": "CTR",
                "site_code_prefix": "SITE",
                "document_code_prefix": "DOC",
            },
            files={"logo": valid_logo},
        )
        self.assertTrue(form.is_valid(), form.errors)

        invalid_logo = SimpleUploadedFile(
            "logo.png",
            b"not-a-png",
            content_type="image/png",
        )
        invalid_form = OrganizationSettingsForm(
            data={
                "language": "fa",
                "timezone": "Asia/Tehran",
                "currency": "IRR",
                "fiscal_year_start_month": 1,
                "fiscal_year_start_day": 1,
                "project_code_prefix": "PRJ",
                "contract_code_prefix": "CTR",
                "site_code_prefix": "SITE",
                "document_code_prefix": "DOC",
            },
            files={"logo": invalid_logo},
        )
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("logo", invalid_form.errors)


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
            registration_number="REG-2048",
            national_id="national-2048",
            economic_code="economic-2048",
            phone="+982112345678",
            email="office@example.com",
            website="https://example.com",
            province="تهران",
            city="تهران",
            address="خیابان نمونه",
            postal_code="1234567890",
            timezone_name="America/New_York",
            currency="IRR",
        )

        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=owner,
        )
        self.assertEqual(organization.created_by, owner)
        self.assertEqual(organization.updated_by, owner)
        self.assertEqual(organization.registration_number, "REG-2048")
        self.assertEqual(organization.national_id, "NATIONAL-2048")
        self.assertEqual(organization.economic_code, "ECONOMIC-2048")
        self.assertTrue(organization.is_active)
        self.assertEqual(membership.role, MembershipRole.COMPANY_OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertIsNotNone(membership.joined_at)
        self.assertEqual(organization.settings.timezone, "America/New_York")
        self.assertEqual(organization.settings.currency, "IRR")
        self.assertEqual(organization.currency, "USD")
        self.assertEqual(organization.settings.language, "fa")
        self.assertEqual(organization.settings.fiscal_year_start_day, 1)
        self.assertEqual(organization.settings.project_code_prefix, "PRJ")
        self.assertEqual(organization.settings.contract_code_prefix, "CTR")
        self.assertEqual(organization.settings.site_code_prefix, "SITE")
        self.assertEqual(organization.settings.document_code_prefix, "DOC")

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

    def test_only_platform_admin_can_request_organization_creation(self) -> None:
        organization_user = User.objects.create_user(
            username="organization-user",
            password="test-password",
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "فقط ادمین پلتفرم می‌تواند شرکت جدید ایجاد کند.",
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
            currency="USD",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Settings Company",
            slug="other-settings-company",
            created_by=self.other_owner,
            updated_by=self.other_owner,
        )
        owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=owner_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Settings fixture requires explicit owner scope",
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
        OrganizationSettings.objects.create(
            organization=self.organization,
            timezone="Asia/Tehran",
            currency="IRR",
        )
        OrganizationSettings.objects.create(
            organization=self.other_organization,
            timezone="UTC",
            currency="IRR",
        )

    def test_get_settings_does_not_restore_from_legacy_fields(self) -> None:
        self.organization.settings.delete()

        with self.assertRaises(OrganizationSettings.DoesNotExist):
            get_organization_settings(organization=self.organization)

        self.assertFalse(
            OrganizationSettings.objects.filter(organization=self.organization).exists()
        )

    def test_update_uses_settings_authority_without_dual_write(self) -> None:
        settings_record = update_organization_settings(
            organization=self.organization,
            updated_by=self.owner,
            timezone_name="UTC",
            currency="IRR",
            fiscal_year_start_month=4,
            fiscal_year_start_day=6,
            language="en",
            project_code_prefix="SITE",
            contract_code_prefix="CON",
            site_code_prefix="WORK",
            document_code_prefix="FILE",
            profile_data={
                "name": "Updated Settings Company",
                "slug": "updated-settings-company",
                "national_id": "national-900",
                "city": "تهران",
            },
        )

        self.organization.refresh_from_db()
        self.assertEqual(settings_record.timezone, "UTC")
        self.assertEqual(settings_record.currency, "IRR")
        self.assertEqual(settings_record.fiscal_year_start_day, 6)
        self.assertEqual(settings_record.language, "en")
        self.assertEqual(settings_record.project_code_prefix, "SITE")
        self.assertEqual(settings_record.contract_code_prefix, "CON")
        self.assertEqual(settings_record.site_code_prefix, "WORK")
        self.assertEqual(settings_record.document_code_prefix, "FILE")
        self.assertEqual(self.organization.timezone, "Asia/Tehran")
        self.assertEqual(self.organization.currency, "USD")
        self.assertEqual(self.organization.name, "Updated Settings Company")
        self.assertEqual(self.organization.slug, "updated-settings-company")
        self.assertEqual(self.organization.national_id, "NATIONAL-900")
        self.assertEqual(self.organization.city, "تهران")
        event = AuditEvent.objects.get(
            organization=self.organization,
            actor=self.owner,
            action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
            entity_id=str(settings_record.pk),
        )
        self.assertEqual(
            event.metadata["authority"], "organizations.OrganizationSettings"
        )
        self.assertEqual(event.metadata["before"]["timezone"], "Asia/Tehran")
        self.assertEqual(event.metadata["after"]["timezone"], "UTC")
        self.assertIn("timezone", event.metadata["changed_fields"])

    def test_member_cannot_update_settings(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied,
            "اجازه به‌روزرسانی تنظیمات این شرکت را ندارید.",
        ):
            update_organization_settings(
                organization=self.organization,
                updated_by=self.member,
                timezone_name="UTC",
                currency="IRR",
                fiscal_year_start_month=1,
            )

    def test_update_rejects_unsupported_base_currency(self) -> None:
        with self.assertRaises(ValidationError) as context:
            update_organization_settings(
                organization=self.organization,
                updated_by=self.owner,
                timezone_name="UTC",
                currency="USD",
                fiscal_year_start_month=1,
            )

        self.assertIn("currency", context.exception.message_dict)
        self.organization.settings.refresh_from_db()
        self.assertEqual(self.organization.settings.currency, "IRR")

    def test_owner_cannot_update_another_organization_settings(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied,
            "به این شرکت دسترسی ندارید.",
        ):
            update_organization_settings(
                organization=self.other_organization,
                updated_by=self.owner,
                timezone_name="UTC",
                currency="IRR",
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
                currency="IRR",
                fiscal_year_start_month=1,
            )

    def test_settings_view_updates_company_profile_and_configuration(self) -> None:
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("organizations:settings"),
            {
                "profile-name": "شرکت تنظیم‌شده",
                "profile-legal_name": "شرکت تنظیم‌شده ایرانیان",
                "profile-slug": "configured-company",
                "profile-registration_number": "4567",
                "profile-national_id": "NAT-4567",
                "profile-economic_code": "ECO-4567",
                "profile-phone": "+982112345678",
                "profile-email": "company@example.com",
                "profile-website": "https://example.com",
                "profile-province": "تهران",
                "profile-city": "تهران",
                "profile-address": "خیابان نمونه",
                "profile-postal_code": "1234567890",
                "settings-language": "fa",
                "settings-timezone": "Asia/Tehran",
                "settings-currency": "IRR",
                "settings-fiscal_year_start_month": "1",
                "settings-fiscal_year_start_day": "1",
                "settings-project_code_prefix": "PRJ",
                "settings-contract_code_prefix": "CTR",
                "settings-site_code_prefix": "SITE",
                "settings-document_code_prefix": "DOC",
            },
        )

        self.assertRedirects(response, reverse("organizations:settings"))
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "شرکت تنظیم‌شده")
        self.assertEqual(self.organization.national_id, "NAT-4567")
        self.assertEqual(self.organization.settings.timezone, "Asia/Tehran")
        self.assertEqual(self.organization.settings.site_code_prefix, "SITE")
        self.assertEqual(self.organization.settings.document_code_prefix, "DOC")


class OrganizationCreationViewTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="organization-creator",
            password="test-password",
        )
        self.platform_admin = User.objects.create_user(
            username="platform-admin",
            password="test-password",
        )
        actor = User.objects.create_superuser(
            username="platform-role-actor",
            email="admin@example.test",
            password="test-password",
        )
        approver = User.objects.create_superuser(
            username="platform-role-approver",
            email="approver@example.test",
            password="test-password",
        )
        assign_platform_admin(
            actor=actor,
            approver=approver,
            target=self.platform_admin,
            reason="Tenant provisioning duty",
        )
        self.initial_owner = User.objects.create_user(
            username="initial-owner",
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
            "فقط ادمین پلتفرم می‌تواند شرکت جدید ایجاد کند.",
            status_code=403,
        )

    def test_create_view_renders_form_for_platform_admin(self) -> None:
        self.client.force_login(self.platform_admin)

        response = self.client.get(reverse("organizations:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ایجاد شرکت")

    def test_create_view_rejects_organization_user_post(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("organizations:create"),
            {
                "name": "Unauthorized Company",
                "legal_name": "Unauthorized Company LLC",
                "slug": "unauthorized-company",
                "timezone": "UTC",
                "currency": "IRR",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Organization.objects.filter(slug="unauthorized-company").exists()
        )

    def test_create_view_creates_organization_for_platform_admin(self) -> None:
        self.client.force_login(self.platform_admin)

        response = self.client.post(
            reverse("organizations:create"),
            {
                "name": "Created Company",
                "legal_name": "Created Company LLC",
                "slug": "created-company",
                "timezone": "UTC",
                "currency": "IRR",
                "initial_owner_username": self.initial_owner.username,
            },
        )

        self.assertRedirects(response, reverse("organizations:select"))
        organization = Organization.objects.get(slug="created-company")
        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=self.initial_owner,
        )
        self.assertEqual(organization.created_by, self.initial_owner)
        self.assertEqual(membership.role, MembershipRole.COMPANY_OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertNotIn(
            ACTIVE_ORGANIZATION_SESSION_KEY,
            self.client.session,
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


class OrganizationUserProvisioningTests(TestCase):
    def setUp(self) -> None:
        self.system_admin = User.objects.create_superuser(
            username="provisioning-admin",
            password="test-password",
        )
        self.owner = User.objects.create_user(
            username="provisioning-owner",
            password="test-password",
        )
        self.user = User.objects.create_user(
            username="provisioned-user",
            password="test-password",
            is_active=False,
        )
        self.organization = Organization.objects.create(
            name="Provisioning Company",
            slug="provisioning-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_system_admin_cannot_provision_tenant_membership(self) -> None:
        with self.assertRaisesMessage(PermissionDenied, "دسترسی ضمنی"):
            provision_user_for_organization(
                organization=self.organization,
                user=self.user,
                actor=self.system_admin,
            )

    def test_superuser_cannot_bootstrap_a_legacy_pending_membership(self) -> None:
        with self.assertRaisesMessage(PermissionDenied, "دسترسی ضمنی"):
            provision_user_for_organization(
                organization=self.organization,
                user=self.user,
                actor=self.system_admin,
            )

    def test_company_owner_cannot_provision_an_unassigned_global_user(self) -> None:
        with self.assertRaisesMessage(
            PermissionDenied,
            "دسترسی ضمنی",
        ):
            provision_user_for_organization(
                organization=self.organization,
                user=self.user,
                actor=self.owner,
            )


class OwnerAccountManagementTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="owner-account-manager")
        self.organization = Organization.objects.create(
            name="Owner Account Company", slug="owner-account-company"
        )
        self.owner_role = OrganizationRole.objects.get(
            code=MembershipRole.COMPANY_OWNER
        )
        self.member_role = OrganizationRole.objects.get(code=MembershipRole.MEMBER)
        owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role_definition=self.owner_role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=owner_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Account management fixture requires explicit owner scope",
        )
        self.member = User.objects.create_user(
            username="password-reset-member", password="original-password"
        )
        self.member_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role_definition=self.member_role,
            status=MembershipStatus.ACTIVE,
        )

    def test_owner_creates_account_with_temporary_password_restriction(self) -> None:
        user, membership = create_organization_account(
            organization=self.organization,
            actor=self.owner,
            username="New.Worker",
            temporary_password="Temporary-password-2026",
            role=self.member_role,
            first_name="کاربر",
            last_name="جدید",
        )

        self.assertEqual(user.username, "new.worker")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password("Temporary-password-2026"))
        self.assertEqual(membership.organization, self.organization)
        self.assertEqual(membership.role_definition, self.member_role)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.ORGANIZATION_ACCOUNT_CREATED,
                organization=self.organization,
                actor=self.owner,
            ).exists()
        )

    def test_existing_account_requires_target_acceptance(self) -> None:
        target = User.objects.create_user(
            username="existing-global-user", password="existing-password"
        )
        connection = request_existing_account_connection(
            organization=self.organization,
            actor=self.owner,
            username=target.username,
            role=self.member_role,
        )
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization, user=target
            ).exists()
        )

        respond_to_account_connection_request(
            target_user=target, request_record=connection, accept=True
        )

        connection.refresh_from_db()
        self.assertEqual(connection.status, AccountConnectionRequestStatus.ACCEPTED)
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=target,
                status=MembershipStatus.ACTIVE,
            ).exists()
        )

        # A duplicate POST is a safe retry, not a second membership operation.
        self.assertEqual(
            respond_to_account_connection_request(
                target_user=target, request_record=connection, accept=True
            ).pk,
            connection.pk,
        )
        self.assertEqual(
            OrganizationMembership.objects.filter(
                organization=self.organization, user=target
            ).count(),
            1,
        )

    def test_target_rejection_is_audited_without_creating_membership(self) -> None:
        target = User.objects.create_user(
            username="rejecting-global-user", password="existing-password"
        )
        connection = request_existing_account_connection(
            organization=self.organization,
            actor=self.owner,
            username=target.username,
            role=self.member_role,
        )

        respond_to_account_connection_request(
            target_user=target, request_record=connection, accept=False
        )

        connection.refresh_from_db()
        self.assertEqual(connection.status, AccountConnectionRequestStatus.REJECTED)
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization, user=target
            ).exists()
        )
        event = AuditEvent.objects.get(
            action=AuditAction.ACCOUNT_CONNECTION_REJECTED,
            entity_id=str(connection.pk),
        )
        self.assertIsNone(event.actor)
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.metadata["target_user_id"], str(target.pk))

    def test_non_owner_default_role_cannot_create_tenant_accounts(self) -> None:
        manager = User.objects.create_user(username="account-company-manager")
        manager_role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_MANAGER)
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=manager,
            role_definition=manager_role,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            create_organization_account(
                organization=self.organization,
                actor=manager,
                username="forbidden-created-account",
                temporary_password="Temporary-password-2026",
                role=self.member_role,
            )

    def test_owner_can_reset_only_its_member_password_and_reset_is_audited(
        self,
    ) -> None:
        updated_user = reset_organization_member_password(
            organization=self.organization,
            actor=self.owner,
            membership=self.member_membership,
            temporary_password="Replacement-password-2026",
        )

        self.assertEqual(updated_user, self.member)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password("Replacement-password-2026"))
        self.assertTrue(self.member.must_change_password)
        event = AuditEvent.objects.get(
            action=AuditAction.ORGANIZATION_MEMBER_PASSWORD_RESET,
        )
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.entity_id, str(self.member_membership.pk))
        self.assertEqual(event.metadata["target_username"], self.member.username)
        self.assertNotIn("password", event.metadata)

    def test_reset_password_view_is_scoped_to_active_organization(self) -> None:
        other_owner = User.objects.create_user(username="password-reset-outsider")
        other_organization = Organization.objects.create(
            name="Other Password Company",
            slug="other-password-company",
        )
        other_membership = OrganizationMembership.objects.create(
            organization=other_organization,
            user=other_owner,
            role_definition=self.owner_role,
            status=MembershipStatus.ACTIVE,
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        response = self.client.post(
            reverse("organizations:member_password_reset", args=[other_membership.pk]),
            {
                "new_password1": "Replacement-password-2026",
                "new_password2": "Replacement-password-2026",
            },
        )

        self.assertEqual(response.status_code, 403)
        other_owner.refresh_from_db()
        self.assertFalse(other_owner.check_password("Replacement-password-2026"))

    def test_non_owner_cannot_reset_member_password(self) -> None:
        manager = User.objects.create_user(username="password-reset-manager")
        manager_role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_MANAGER)
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=manager,
            role_definition=manager_role,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            reset_organization_member_password(
                organization=self.organization,
                actor=manager,
                membership=self.member_membership,
                temporary_password="Replacement-password-2026",
            )

    def test_other_user_cannot_accept_connection_request(self) -> None:
        target = User.objects.create_user(
            username="connection-target", password="existing-password"
        )
        outsider = User.objects.create_user(
            username="connection-outsider", password="existing-password"
        )
        connection = request_existing_account_connection(
            organization=self.organization,
            actor=self.owner,
            username=target.username,
            role=self.member_role,
        )

        with self.assertRaises(PermissionDenied):
            respond_to_account_connection_request(
                target_user=outsider, request_record=connection, accept=True
            )
