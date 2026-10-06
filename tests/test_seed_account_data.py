from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.accounts.management.commands.seed_account_data import (
    ACCOUNT_SEEDS,
    DEMO_ADMIN_USERNAME,
    DEMO_PASSWORD,
    P7_DEMO_PAYROLL_ROLE_CODE,
)
from apps.accounts.models import LoginPageSettings, User
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)


@pytest.mark.django_db(transaction=True)
def test_seed_account_data_is_incremental_and_tenant_safe(
    settings: Any, tmp_path: Path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    settings.DEBUG = True
    call_command("seed_demo_data", stdout=StringIO())

    admin = User.objects.get(username=DEMO_ADMIN_USERNAME)
    admin.set_password("previous-password")
    admin.save(update_fields=["password"])
    preserved_user = User.objects.create_user(
        username="preserved-account", password="unchanged-password"
    )
    preserved_organization = Organization.objects.create(
        name="شرکت حفظ‌شده", slug="preserved-organization"
    )
    login_settings = LoginPageSettings.objects.create(
        background_image=SimpleUploadedFile(
            "existing.png",
            b"\x89PNG\r\n\x1a\nexisting-login-image",
            content_type="image/png",
        )
    )
    existing_image_name = login_settings.background_image.name
    global_role_permissions_before = {
        role.code: set(role.permissions.values_list("code", flat=True))
        for role in OrganizationRole.objects.filter(organization__isnull=True)
    }
    permission_count_before = BusinessPermission.objects.count()

    call_command("seed_account_data", stdout=StringIO())

    demo_organizations = Organization.objects.filter(
        slug__startswith="demo-construction-"
    ).order_by("slug")
    assert demo_organizations.count() == 4
    admin.refresh_from_db()
    assert admin.is_superuser
    assert admin.is_staff
    assert admin.check_password(DEMO_PASSWORD)
    assert preserved_user.check_password("unchanged-password")
    assert Organization.objects.get(pk=preserved_organization.pk).name == "شرکت حفظ‌شده"
    login_settings.refresh_from_db()
    assert login_settings.background_image.name == existing_image_name
    assert BusinessPermission.objects.count() == permission_count_before
    assert {
        role.code: set(role.permissions.values_list("code", flat=True))
        for role in OrganizationRole.objects.filter(organization__isnull=True)
    } == global_role_permissions_before
    p7_organization = Organization.objects.get(slug="demo-construction-01")
    p7_role = OrganizationRole.objects.get(
        organization=p7_organization,
        code=P7_DEMO_PAYROLL_ROLE_CODE,
    )
    assert p7_role.permissions.filter(code="payroll_results.view").exists()
    p7_owner = User.objects.get(username="account.demo-construction-01.owner")
    assert MembershipRoleAssignment.objects.filter(
        organization=p7_organization,
        membership__user=p7_owner,
        role=p7_role,
        revoked_at__isnull=True,
    ).exists()

    seeded_usernames = set()
    for organization in demo_organizations:
        for account_seed in ACCOUNT_SEEDS:
            username = f"account.{organization.slug}.{account_seed.key}"
            seeded_usernames.add(username)
            user = User.objects.get(username=username)
            assert user.check_password(DEMO_PASSWORD)
            memberships = OrganizationMembership.objects.filter(user=user)
            assert memberships.count() == 1
            membership = memberships.get()
            assert membership.organization_id == organization.pk
            assert membership.role == account_seed.membership_role

    counts_before = {
        "users": User.objects.count(),
        "memberships": OrganizationMembership.objects.count(),
        "settings": LoginPageSettings.objects.count(),
    }
    call_command("seed_account_data", stdout=StringIO())

    assert User.objects.count() == counts_before["users"]
    assert OrganizationMembership.objects.count() == counts_before["memberships"]
    assert LoginPageSettings.objects.count() == counts_before["settings"]
    assert User.objects.filter(username__in=seeded_usernames).count() == len(
        seeded_usernames
    )
