import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


PERMISSIONS = {
    "membership.manage": "مدیریت اعضای شرکت",
    "company.settings.manage": "مدیریت تنظیمات شرکت",
    "parties.manage": "مدیریت طرف‌های تجاری",
    "materials.manage": "مدیریت مصالح و واحدها",
    "projects.manage": "مدیریت پروژه‌ها",
    "contracts.manage": "مدیریت قراردادها",
    "estimates.manage": "مدیریت برآوردها",
    "estimates.approve": "تأیید برآوردها",
    "expenses.manage": "مدیریت هزینه‌ها",
    "payments.manage": "مدیریت پرداخت‌ها",
    "documents.manage": "مدیریت اسناد",
    "daily_reports.create": "ثبت گزارش روزانه",
    "daily_reports.manage": "مدیریت گزارش‌های روزانه",
    "workforce.manage": "مدیریت نیروی انسانی",
    "procurement.request": "ثبت درخواست و دریافت خرید",
    "procurement.manage": "مدیریت و تأیید خرید",
    "inventory.movement": "ثبت گردش انبار",
    "inventory.manage": "مدیریت انبار",
    "audit.view": "مشاهده گزارش رویدادها",
}

ALL_PERMISSIONS = set(PERMISSIONS)
ROLE_PERMISSIONS = {
    "company_owner": ALL_PERMISSIONS,
    "company_manager": ALL_PERMISSIONS,
    "operations_manager": ALL_PERMISSIONS
    - {"membership.manage", "company.settings.manage", "estimates.approve"},
    "member": {
        "daily_reports.create",
        "procurement.request",
        "inventory.movement",
        "audit.view",
    },
    "viewer": {"audit.view"},
}
ROLE_METADATA = {
    "company_owner": ("مالک شرکت", True, True),
    "company_manager": ("مدیر شرکت", True, False),
    "operations_manager": ("مدیر اجرایی", True, False),
    "member": ("عضو", True, False),
    "viewer": ("مشاهده‌گر", True, False),
}
LEGACY_ROLE_MAP = {
    "owner": "company_owner",
    "admin": "company_manager",
    "manager": "operations_manager",
    "member": "member",
    "viewer": "viewer",
}


def seed_roles_and_permissions(apps, schema_editor):
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    OrganizationMembership = apps.get_model(
        "organizations", "OrganizationMembership"
    )
    OrganizationInvitation = apps.get_model(
        "organizations", "OrganizationInvitation"
    )

    permissions = {}
    for code, name in PERMISSIONS.items():
        permission, _ = BusinessPermission.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )
        permissions[code] = permission

    roles = {}
    for code, (name, is_system, is_owner) in ROLE_METADATA.items():
        role, _ = OrganizationRole.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "is_active": True,
                "is_system": is_system,
                "is_owner": is_owner,
            },
        )
        role.permissions.set(
            [permissions[permission] for permission in ROLE_PERMISSIONS[code]]
        )
        roles[code] = role

    for old_code, new_code in LEGACY_ROLE_MAP.items():
        OrganizationMembership.objects.filter(role=old_code).update(
            role=new_code,
            role_definition=roles[new_code],
        )
        OrganizationInvitation.objects.filter(role=old_code).update(
            role=new_code,
            role_definition=roles[new_code],
        )
    OrganizationMembership.objects.filter(role_definition__isnull=True).update(
        role="member",
        role_definition=roles["member"],
    )
    OrganizationInvitation.objects.filter(role_definition__isnull=True).update(
        role="member",
        role_definition=roles["member"],
    )


def restore_legacy_role_codes(apps, schema_editor):
    OrganizationMembership = apps.get_model(
        "organizations", "OrganizationMembership"
    )
    OrganizationInvitation = apps.get_model(
        "organizations", "OrganizationInvitation"
    )
    reverse_map = {value: key for key, value in LEGACY_ROLE_MAP.items()}
    for new_code, old_code in reverse_map.items():
        OrganizationMembership.objects.filter(role=new_code).update(role=old_code)
        OrganizationInvitation.objects.filter(role=new_code).update(role=old_code)


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0003_alter_organization_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessPermission",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="زمان آخرین به‌روزرسانی")),
                ("code", models.CharField(max_length=100, unique=True, verbose_name="کد مجوز")),
                ("name", models.CharField(max_length=255, verbose_name="عنوان فارسی")),
                ("description", models.TextField(blank=True, verbose_name="توضیحات")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
            ],
            options={
                "verbose_name": "مجوز کسب‌وکار",
                "verbose_name_plural": "مجوزهای کسب‌وکار",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="OrganizationRole",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="زمان آخرین به‌روزرسانی")),
                ("code", models.SlugField(max_length=64, unique=True, verbose_name="کد نقش")),
                ("name", models.CharField(max_length=255, verbose_name="عنوان فارسی")),
                ("description", models.TextField(blank=True, verbose_name="توضیحات")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="فعال")),
                ("is_system", models.BooleanField(default=False, verbose_name="نقش سیستمی")),
                ("is_owner", models.BooleanField(default=False, verbose_name="نقش مالک شرکت")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="organization_roles_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ایجادکننده",
                    ),
                ),
                (
                    "permissions",
                    models.ManyToManyField(
                        blank=True,
                        related_name="roles",
                        to="organizations.businesspermission",
                        verbose_name="مجوزهای کسب‌وکار",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="organization_roles_updated",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="آخرین ویرایش‌کننده",
                    ),
                ),
            ],
            options={
                "verbose_name": "نقش شرکتی",
                "verbose_name_plural": "نقش‌های شرکتی",
                "ordering": ["name"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_owner", True)),
                        fields=("is_owner",),
                        name="unique_company_owner_role",
                    )
                ],
            },
        ),
        migrations.AlterField(
            model_name="organizationmembership",
            name="role",
            field=models.CharField(
                default="member",
                editable=False,
                max_length=64,
                verbose_name="کد نقش سازگار",
            ),
        ),
        migrations.AlterField(
            model_name="organizationinvitation",
            name="role",
            field=models.CharField(
                default="member",
                editable=False,
                max_length=64,
                verbose_name="کد نقش سازگار",
            ),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="role_definition",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="memberships",
                to="organizations.organizationrole",
                verbose_name="نقش",
            ),
        ),
        migrations.AddField(
            model_name="organizationinvitation",
            name="role_definition",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invitations",
                to="organizations.organizationrole",
                verbose_name="نقش",
            ),
        ),
        migrations.RunPython(seed_roles_and_permissions, restore_legacy_role_codes),
        migrations.AlterField(
            model_name="organizationmembership",
            name="role_definition",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="memberships",
                to="organizations.organizationrole",
                verbose_name="نقش",
            ),
        ),
        migrations.AlterField(
            model_name="organizationinvitation",
            name="role_definition",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invitations",
                to="organizations.organizationrole",
                verbose_name="نقش",
            ),
        ),
    ]
