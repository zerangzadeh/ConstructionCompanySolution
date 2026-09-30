import uuid
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list[object]] = [
        ("organizations", "0039_p1_s17_party_governance_permission"),
        ("parties", "0003_p1_s16_party_identity_and_restrictions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.CreateModel(
            name="PartyClassification",
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
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("category", "دسته"), ("tag", "برچسب")], max_length=20
                    ),
                ),
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_classifications_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="party_classifications",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ["kind", "name"]},
        ),
        migrations.CreateModel(
            name="PartyClassificationAssignment",
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
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("assigned_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.TextField(blank=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_classifications_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "classification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_assignments",
                        to="parties.partyclassification",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_classification_assignments",
                        to="organizations.organization",
                    ),
                ),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="classification_assignments",
                        to="parties.businessparty",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_classifications_revoked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PartyRepresentative",
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
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                (
                    "authority",
                    models.CharField(
                        choices=[
                            ("representative", "نماینده مجاز"),
                            ("signatory", "امضادار مجاز"),
                        ],
                        max_length=20,
                    ),
                ),
                ("full_name", models.CharField(max_length=255)),
                ("title", models.CharField(blank=True, max_length=120)),
                ("evidence_reference", models.CharField(max_length=255)),
                ("effective_from", models.DateTimeField()),
                ("effective_until", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.TextField(blank=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_representatives",
                        to="organizations.organization",
                    ),
                ),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="representatives",
                        to="parties.businessparty",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_representatives_recorded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_representatives_revoked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["party", "authority", "full_name"]},
        ),
        migrations.CreateModel(
            name="PartyAlias",
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
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                (
                    "alias_type",
                    models.CharField(
                        choices=[
                            ("display_name", "نام نمایشی"),
                            ("legal_name", "نام قانونی"),
                            ("identifier", "شناسه"),
                            ("other", "سایر"),
                        ],
                        max_length=20,
                    ),
                ),
                ("value", models.CharField(max_length=255)),
                (
                    "normalized_value",
                    models.CharField(db_index=True, editable=False, max_length=255),
                ),
                ("reason", models.TextField()),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_aliases",
                        to="organizations.organization",
                    ),
                ),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="aliases",
                        to="parties.businessparty",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_aliases_recorded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["party", "alias_type", "value"],
                "indexes": [
                    models.Index(
                        fields=["organization", "alias_type", "normalized_value"],
                        name="party_alias_lookup_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "organization",
                            "party",
                            "alias_type",
                            "normalized_value",
                        ),
                        name="unique_party_alias_evidence",
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="partyclassification",
            constraint=models.UniqueConstraint(
                fields=("organization", "kind", "code"),
                name="unique_party_classification_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="partyclassificationassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("revoked_at__isnull", True)),
                fields=("party", "classification"),
                name="unique_active_party_classification",
            ),
        ),
        migrations.AddConstraint(
            model_name="partyclassificationassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("revocation_reason", ""),
                        ("revoked_at__isnull", True),
                        ("revoked_by__isnull", True),
                    ),
                    models.Q(
                        ("revocation_reason__gt", ""),
                        ("revoked_at__isnull", False),
                        ("revoked_by__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="party_classification_revocation_evidence",
            ),
        ),
        migrations.AddIndex(
            model_name="partyrepresentative",
            index=models.Index(
                fields=["organization", "party", "authority", "effective_from"],
                name="party_rep_lookup_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="partyrepresentative",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("effective_until__isnull", True),
                    ("effective_until__gt", models.F("effective_from")),
                    _connector="OR",
                ),
                name="party_representative_interval",
            ),
        ),
        migrations.AddConstraint(
            model_name="partyrepresentative",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("revocation_reason", ""),
                        ("revoked_at__isnull", True),
                        ("revoked_by__isnull", True),
                    ),
                    models.Q(
                        ("revocation_reason__gt", ""),
                        ("revoked_at__isnull", False),
                        ("revoked_by__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="party_representative_revocation_evidence",
            ),
        ),
    ]
