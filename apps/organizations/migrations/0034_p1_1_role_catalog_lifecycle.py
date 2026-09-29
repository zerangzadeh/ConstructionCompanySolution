from typing import ClassVar

import django.db.models.deletion
import django.db.models.expressions
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0033_p1_1_platform_admin_protected_operations"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.AddField(
            model_name="organizationrole",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="custom_roles",
                to="organizations.organization",
                verbose_name="شرکت",
            ),
        ),
        migrations.AddField(
            model_name="organizationrole",
            name="archived_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="زمان بایگانی"
            ),
        ),
        migrations.AddField(
            model_name="organizationrole",
            name="archived_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="organization_roles_archived",
                to=settings.AUTH_USER_MODEL,
                verbose_name="بایگانی‌کننده",
            ),
        ),
        migrations.AddField(
            model_name="organizationrole",
            name="archive_reason",
            field=models.TextField(blank=True, verbose_name="دلیل بایگانی"),
        ),
        migrations.AlterField(
            model_name="organizationrole",
            name="code",
            field=models.SlugField(max_length=64, verbose_name="کد نقش"),
        ),
        migrations.AddConstraint(
            model_name="organizationrole",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", True)),
                fields=("code",),
                name="unique_global_organization_role_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationrole",
            constraint=models.UniqueConstraint(
                condition=models.Q(("organization__isnull", False)),
                fields=("organization", "code"),
                name="unique_tenant_organization_role_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationrole",
            constraint=models.CheckConstraint(
                condition=models.Q(("is_system", False))
                | models.Q(("organization__isnull", True)),
                name="system_organization_role_is_global",
            ),
        ),
    ]
