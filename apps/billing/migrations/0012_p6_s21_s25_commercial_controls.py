import uuid
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("billing", "0011_payablecertificate_payablecertificateadjustment_and_more"),
        ("contracts", "0007_p6_s21_s25_retention_release_terms"),
        ("documents", "0009_document_retention_classification_and_more"),
        ("organizations", "0085_p6_s14_s20_payable_permissions"),
        ("parties", "0004_p1_s17_party_governance"),
        ("projects", "0008_p4_s21_s25_schedule_change_controls"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations: ClassVar[list] = [
        migrations.CreateModel(
            name="ContractComplianceEvidence",
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
                ("series_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "revision_action",
                    models.CharField(
                        choices=[
                            ("original", "ثبت اولیه"),
                            ("correction", "اصلاح"),
                            ("renewal", "تمدید"),
                            ("release", "آزادسازی"),
                        ],
                        default="original",
                        max_length=20,
                    ),
                ),
                ("revision_reason", models.TextField()),
                (
                    "evidence_kind",
                    models.CharField(
                        choices=[
                            ("insurance", "شاهد بیمه قراردادی"),
                            ("clearance", "شاهد مفاصاحساب"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reference", models.CharField(max_length=120)),
                ("issuing_authority", models.CharField(max_length=255)),
                ("effective_from", models.DateField()),
                (
                    "expiry_kind",
                    models.CharField(
                        choices=[
                            ("dated", "دارای تاریخ انقضا"),
                            ("open_ended", "بدون تاریخ انقضای قراردادی"),
                        ],
                        max_length=20,
                    ),
                ),
                ("expires_on", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "پیش‌نویس"),
                            ("submitted", "ارسال‌شده"),
                            ("approved", "تأییدشده"),
                            ("returned", "بازگردانده‌شده"),
                            ("superseded", "جایگزین‌شده"),
                            ("expired", "منقضی‌شده"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("submission_snapshot", models.JSONField(blank=True, default=dict)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("decision_reason", models.TextField(blank=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="compliance_evidence",
                        to="contracts.contract",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "document_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence",
                        to="documents.documentversion",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence",
                        to="organizations.organization",
                    ),
                ),
                (
                    "party_identity_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence",
                        to="parties.partyidentitysnapshot",
                    ),
                ),
                (
                    "predecessor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="successor_versions",
                        to="billing.contractcomplianceevidence",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence",
                        to="projects.project",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence_submitted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_compliance_evidence_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["contract_id", "series_id", "version"],
                "indexes": [
                    models.Index(
                        fields=["organization", "status", "expires_on"],
                        name="compliance_expiry_work_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "contract", "series_id", "version"),
                        name="compliance_evidence_series_version_uq",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(status="approved"),
                        fields=("organization", "series_id"),
                        name="compliance_evidence_one_approved_uq",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ContractGuarantee",
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
                ("series_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "revision_action",
                    models.CharField(
                        choices=[
                            ("original", "ثبت اولیه"),
                            ("correction", "اصلاح"),
                            ("renewal", "تمدید"),
                            ("release", "آزادسازی"),
                        ],
                        default="original",
                        max_length=20,
                    ),
                ),
                ("revision_reason", models.TextField()),
                (
                    "guarantee_type",
                    models.CharField(
                        choices=[
                            ("bid", "ضمانت‌نامه شرکت در مناقصه"),
                            ("performance", "ضمانت‌نامه حسن انجام تعهدات"),
                            ("advance_payment", "ضمانت‌نامه پیش‌پرداخت"),
                            ("retention", "ضمانت‌نامه کسور تضمین"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "exposure_side",
                    models.CharField(
                        choices=[
                            ("issued", "صادرشده از طرف سازمان"),
                            ("received", "دریافت‌شده به نفع سازمان"),
                        ],
                        max_length=16,
                    ),
                ),
                ("instrument_reference", models.CharField(max_length=120)),
                ("issuer_name", models.CharField(max_length=255)),
                ("currency_code", models.CharField(max_length=3)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("issued_on", models.DateField()),
                ("effective_from", models.DateField()),
                (
                    "expiry_kind",
                    models.CharField(
                        choices=[
                            ("dated", "دارای تاریخ انقضا"),
                            ("open_ended", "بدون تاریخ انقضای قراردادی"),
                        ],
                        max_length=20,
                    ),
                ),
                ("expires_on", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "پیش‌نویس"),
                            ("submitted", "ارسال‌شده"),
                            ("active", "فعال"),
                            ("returned", "بازگردانده‌شده"),
                            ("superseded", "جایگزین‌شده"),
                            ("expired", "منقضی‌شده"),
                            ("released", "آزادشده"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("submission_snapshot", models.JSONField(blank=True, default=dict)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("decision_reason", models.TextField(blank=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees",
                        to="contracts.contract",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "evidence_document_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contract_guarantee_versions",
                        to="documents.documentversion",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees",
                        to="organizations.organization",
                    ),
                ),
                (
                    "party_identity_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees",
                        to="parties.partyidentitysnapshot",
                    ),
                ),
                (
                    "predecessor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="successor_versions",
                        to="billing.contractguarantee",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees",
                        to="projects.project",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees_submitted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guarantees_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["contract_id", "series_id", "version"],
                "indexes": [
                    models.Index(
                        fields=["organization", "status", "expires_on"],
                        name="guarantee_expiry_work_idx",
                    ),
                    models.Index(
                        fields=["organization", "project", "exposure_side", "status"],
                        name="guarantee_exposure_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "contract", "series_id", "version"),
                        name="guarantee_series_version_uq",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(status="active"),
                        fields=("organization", "series_id"),
                        name="guarantee_one_active_version_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(amount=0, revision_action="release"),
                            models.Q(
                                ~models.Q(revision_action="release"), amount__gt=0
                            ),
                            _connector="OR",
                        ),
                        name="guarantee_amount_action_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="RetentionRelease",
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
                ("release_number", models.PositiveIntegerField()),
                ("revision_number", models.PositiveIntegerField(default=1)),
                (
                    "correction_kind",
                    models.CharField(
                        choices=[
                            ("ordinary", "عادی"),
                            ("replacement", "اصلاح جایگزین"),
                            ("cancellation", "ابطال پیوندخورده"),
                        ],
                        default="ordinary",
                        max_length=20,
                    ),
                ),
                ("correction_reason", models.TextField(blank=True)),
                ("release_date", models.DateField()),
                ("currency_code", models.CharField(max_length=3)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                (
                    "retained_total_snapshot",
                    models.DecimalField(decimal_places=4, max_digits=18),
                ),
                (
                    "prior_release_total_snapshot",
                    models.DecimalField(decimal_places=4, max_digits=18),
                ),
                (
                    "available_amount_snapshot",
                    models.DecimalField(decimal_places=4, max_digits=18),
                ),
                ("calculation_snapshot", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "پیش‌نویس"),
                            ("submitted", "ارسال‌شده"),
                            ("approved", "تأییدشده"),
                            ("returned", "بازگردانده‌شده"),
                            ("superseded", "جایگزین‌شده"),
                            ("cancelled", "باطل‌شده"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("submission_snapshot", models.JSONField(blank=True, default=dict)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("decision_reason", models.TextField(blank=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "clearance_evidence",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases",
                        to="billing.contractcomplianceevidence",
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases",
                        to="contracts.contract",
                    ),
                ),
                (
                    "contract_term_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases",
                        to="contracts.contracttermversion",
                    ),
                ),
                (
                    "corrects",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correction_releases",
                        to="billing.retentionrelease",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "evidence_document_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_release_evidence",
                        to="documents.documentversion",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases",
                        to="organizations.organization",
                    ),
                ),
                (
                    "party_identity_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases",
                        to="parties.partyidentitysnapshot",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases",
                        to="projects.project",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases_submitted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retention_releases_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["contract_id", "release_number", "revision_number"],
                "indexes": [
                    models.Index(
                        fields=["organization", "contract", "status"],
                        name="retention_release_status_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "organization",
                            "contract",
                            "release_number",
                            "revision_number",
                        ),
                        name="retention_release_number_revision_uq",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(status="approved"),
                        fields=("organization", "contract", "release_number"),
                        name="retention_release_one_approved_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(amount=0, correction_kind="cancellation"),
                            models.Q(
                                ~models.Q(correction_kind="cancellation"), amount__gt=0
                            ),
                            _connector="OR",
                        ),
                        name="retention_release_amount_kind_valid",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("retained_total_snapshot__gte", 0),
                            ("prior_release_total_snapshot__gte", 0),
                            ("available_amount_snapshot__gte", 0),
                        ),
                        name="retention_release_snapshots_nonnegative",
                    ),
                ],
            },
        ),
    ]
