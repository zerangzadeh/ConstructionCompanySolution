"""Serve synthetic browser fixtures on the isolated regression database only."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.conf import settings

settings.DATABASES["default"]["NAME"] = "test_bonira_platform_completion_01a1b05d"
settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
settings.PRODUCT_SURFACE_PROFILE = "MVP"
settings.SESSION_COOKIE_NAME = "bonira_roles_redesign_test"

import django

django.setup()

from django.core.management import call_command
from apps.accounts.models import User
from apps.organizations.access_services import assign_platform_admin, bootstrap_membership_authorization
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole, BusinessPermission, MembershipRole
from apps.organizations.services import create_organization_with_owner

if not User.objects.filter(username="roles-browser-admin").exists():
    root = User.objects.create_superuser(username="roles-browser-root")
    admin = User.objects.create_user(username="roles-browser-admin", password="roles-browser-local-fixture")
    assign_platform_admin(actor=root, approver=root, target=admin, reason="Isolated UI fixture")
    company = create_organization_with_owner(owner=admin, name="شرکت نمونه بررسی نقش", slug="roles-browser-company")
    create_organization_with_owner(owner=root, name="شرکت نمونه دوم", slug="roles-browser-other")
    for username, role in (("roles-browser-approver", MembershipRole.COMPANY_OWNER), ("roles-browser-member", MembershipRole.MEMBER)):
        user = User.objects.create_user(username=username)
        member = OrganizationMembership.objects.create(organization=company, user=user, status="active", role=role, role_definition=OrganizationRole.objects.get(code=role, organization__isnull=True))
        if role == MembershipRole.COMPANY_OWNER:
            bootstrap_membership_authorization(membership=member, actor=admin, source="bootstrap")
    permission = BusinessPermission.objects.get(code="projects.view")
    for code, name, organization in (("roles-browser-global", "نقش نمونه سراسری", None), ("roles-browser-tenant", "نقش نمونه شرکت", company)):
        role = OrganizationRole.objects.create(code=code, name=name, organization=organization, description="نقش آزمایشی برای بررسی رابط کاربری")
        role.permissions.add(permission)

print("Synthetic role fixtures ready on isolated test database", flush=True)
call_command("runserver", "127.0.0.1:8016", use_reloader=False)
