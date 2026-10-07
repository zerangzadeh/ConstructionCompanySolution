from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class MetricVersionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    IN_REVIEW = "in_review", "در بررسی"
    PUBLISHED = "published", "منتشرشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    RETIRED = "retired", "بازنشسته"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"


class MetricRunStatus(models.TextChoices):
    REQUESTED = "requested", "درخواست‌شده"
    BUILDING = "building", "در حال ساخت"
    SUCCEEDED = "succeeded", "موفق"
    FAILED = "failed", "ناموفق"
    CANCELLED = "cancelled", "لغوشده"


class MetricFreshness(models.TextChoices):
    FRESH = "fresh", "به‌روز"
    STALE = "stale", "قدیمی"
    INCOMPLETE = "incomplete", "ناقص"


class MetricDefinition(UUIDModel, TimeStampedModel):
    code = models.CharField(max_length=80, unique=True)
    persian_name = models.CharField(max_length=255)
    source_domain = models.CharField(max_length=80)
    source_permission = models.CharField(max_length=100)
    sensitivity = models.CharField(max_length=32, default="normal")
    drillthrough_route_name = models.CharField(max_length=160)
    metric_owner = models.CharField(max_length=255)
    source_owner = models.CharField(max_length=255)
    requires_independent_review = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["code"]

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = self.code.strip().lower()
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            governed_fields = (
                "code",
                "persian_name",
                "source_domain",
                "source_permission",
                "sensitivity",
                "drillthrough_route_name",
                "metric_owner",
                "source_owner",
                "requires_independent_review",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in governed_fields
            ):
                raise ValidationError(
                    "تعریف شاخص حاکم‌شده تغییرپذیر نیست؛ نسخه جدید لازم است."
                )
        self.full_clean()
        super().save(*args, **kwargs)


class MetricDefinitionVersion(UUIDModel, CreatedAtModel):
    definition = models.ForeignKey(
        MetricDefinition, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=MetricVersionStatus.choices,
        default=MetricVersionStatus.DRAFT,
    )
    specification = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64)
    governance_reference = models.CharField(max_length=255)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reporting_metric_versions_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["definition", "version"], name="report_metric_version_uq"
            ),
            models.UniqueConstraint(
                fields=["definition"],
                condition=Q(status=MetricVersionStatus.PUBLISHED),
                name="report_metric_one_published_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                MetricVersionStatus.PUBLISHED,
                MetricVersionStatus.SUPERSEDED,
                MetricVersionStatus.RETIRED,
            }:
                raise ValidationError("نسخه منتشرشده شاخص تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class MetricRefreshRun(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    metric_version = models.ForeignKey(
        MetricDefinitionVersion, on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=16,
        choices=MetricRunStatus.choices,
        default=MetricRunStatus.REQUESTED,
    )
    idempotency_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    source_watermark = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="metric_runs"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="report_run_org_idempotency_uq",
            )
        ]
        indexes: ClassVar[list] = [
            models.Index(
                fields=["organization", "metric_version", "status"],
                name="report_run_org_metric_idx",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, project=self.project)


class MetricResult(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.OneToOneField(
        MetricRefreshRun, on_delete=models.PROTECT, related_name="result"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT
    )
    metric_code = models.CharField(max_length=80)
    value = models.JSONField(default=dict)
    currency = models.CharField(max_length=3, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    as_of = models.DateTimeField()
    freshness = models.CharField(max_length=16, choices=MetricFreshness.choices)
    coverage = models.JSONField(default=dict)
    source_manifest = models.JSONField(default=dict)
    calculation_hash = models.CharField(max_length=64)
    replaces = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replacement",
    )

    class Meta:
        indexes: ClassVar[list] = [
            models.Index(
                fields=["organization", "metric_code", "project", "-created_at"],
                name="report_result_latest_idx",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نتیجه نهایی شاخص تغییرپذیر نیست.")
        validate_related_organizations(self, run=self.run, project=self.project)
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class MetricResultReview(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    result = models.OneToOneField(
        MetricResult, on_delete=models.PROTECT, related_name="review"
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=255)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("شاهد بررسی نتیجه تغییرپذیر نیست.")
        validate_related_organizations(self, result=self.result)
        self.full_clean()
        super().save(*args, **kwargs)


class ReportingSavedView(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    configuration = models.JSONField(default=dict)
    is_shared = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "owner", "name", "revision"],
                name="report_saved_view_revision_uq",
            )
        ]


class MetricExportManifest(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    metric_codes = models.JSONField(default=list)
    result_ids = models.JSONField(default=list)
    content_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=255)
    expires_at = models.DateTimeField()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="report_export_org_idempotency_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("مانیفست خروجی تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationVersionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    IN_REVIEW = "in_review", "در بررسی"
    PUBLISHED = "published", "منتشرشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    RETIRED = "retired", "بازنشسته"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"


class ReconciliationRunStatus(models.TextChoices):
    REQUESTED = "requested", "درخواست‌شده"
    CAPTURING = "capturing", "در حال ثبت منبع"
    COMPARING = "comparing", "در حال تطبیق"
    COMPLETED = "completed", "تکمیل‌شده"
    FAILED = "failed", "ناموفق"
    CANCELLED = "cancelled", "لغوشده"


class ReconciliationOutcome(models.TextChoices):
    MATCHED_EXACT = "matched_exact", "منطبق دقیق"
    MATCHED_WITHIN_TOLERANCE = "matched_within_tolerance", "در محدوده تلرانس"
    MISMATCH = "mismatch", "مغایرت"
    MISSING_LEFT = "missing_left", "سمت چپ مفقود"
    MISSING_RIGHT = "missing_right", "سمت راست مفقود"
    INCOMPLETE = "incomplete", "ناقص"
    UNKNOWN = "unknown", "نامعلوم"
    UNCOMPARABLE = "uncomparable", "غیرقابل مقایسه"
    NOT_APPLICABLE = "not_applicable", "نامرتبط"
    GATED = "gated_not_activated", "فعال‌نشده"


class ReconciliationPairDefinition(UUIDModel, TimeStampedModel):
    code = models.CharField(max_length=80, unique=True)
    persian_name = models.CharField(max_length=255)
    left_authority = models.CharField(max_length=120)
    right_authority = models.CharField(max_length=120)
    sensitivity = models.CharField(max_length=32, default="normal")
    requires_independent_review = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["code"]

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = self.code.strip().lower()
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            governed = (
                "code",
                "persian_name",
                "left_authority",
                "right_authority",
                "sensitivity",
                "requires_independent_review",
            )
            if any(
                getattr(previous, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError(
                    "تعریف جفت تطبیق تغییرپذیر نیست؛ نسخه جدید لازم است."
                )
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationPairVersion(UUIDModel, CreatedAtModel):
    definition = models.ForeignKey(
        ReconciliationPairDefinition, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=ReconciliationVersionStatus.choices,
        default=ReconciliationVersionStatus.DRAFT,
    )
    specification = models.JSONField(default=dict)
    source_owner_approvals = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64)
    governance_reference = models.CharField(max_length=255)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reporting_reconciliation_versions_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["definition", "version"], name="report_recon_pair_version_uq"
            ),
            models.UniqueConstraint(
                fields=["definition"],
                condition=Q(status=ReconciliationVersionStatus.PUBLISHED),
                name="report_recon_pair_one_published_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ReconciliationVersionStatus.PUBLISHED,
                ReconciliationVersionStatus.SUPERSEDED,
                ReconciliationVersionStatus.RETIRED,
            }:
                raise ValidationError("نسخه منتشرشده جفت تطبیق تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationRun(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    pair_version = models.ForeignKey(
        ReconciliationPairVersion, on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=16,
        choices=ReconciliationRunStatus.choices,
        default=ReconciliationRunStatus.REQUESTED,
    )
    cutoff_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    source_watermark = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reconciliation_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    replaces = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replacement",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="report_recon_run_org_idem_uq",
            )
        ]
        indexes: ClassVar[list] = [
            models.Index(
                fields=["organization", "pair_version", "status"],
                name="report_recon_run_pair_idx",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, project=self.project)


class ReconciliationSideSnapshot(UUIDModel, CreatedAtModel):
    class Side(models.TextChoices):
        LEFT = "left", "سمت چپ"
        RIGHT = "right", "سمت راست"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.ForeignKey(
        ReconciliationRun, on_delete=models.PROTECT, related_name="side_snapshots"
    )
    side = models.CharField(max_length=8, choices=Side.choices)
    authority_domain = models.CharField(max_length=120)
    authority_model = models.CharField(max_length=160)
    readiness = models.CharField(max_length=32)
    value = models.JSONField(default=dict)
    source_manifest = models.JSONField(default=dict)
    source_hash = models.CharField(max_length=64)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["run", "side"], name="report_recon_run_side_uq"
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("تصویر منبع تطبیق تغییرپذیر نیست.")
        validate_related_organizations(self, run=self.run)
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationTieOut(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.OneToOneField(
        ReconciliationRun, on_delete=models.PROTECT, related_name="tie_out"
    )
    outcome = models.CharField(max_length=32, choices=ReconciliationOutcome.choices)
    difference = models.JSONField(default=dict, blank=True)
    tolerance_result = models.JSONField(default=dict)
    materiality_result = models.JSONField(default=dict)
    coverage = models.JSONField(default=dict)
    calculation_hash = models.CharField(max_length=64)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نتیجه تطبیق تغییرپذیر نیست.")
        validate_related_organizations(self, run=self.run)
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationRunReview(UUIDModel, CreatedAtModel):
    class Decision(models.TextChoices):
        ACCEPTED = "accepted", "پذیرفته"
        REJECTED = "rejected", "ردشده"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.OneToOneField(
        ReconciliationRun, on_delete=models.PROTECT, related_name="review"
    )
    decision = models.CharField(max_length=16, choices=Decision.choices)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=255)
    evidence_hash = models.CharField(max_length=64)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("بررسی اجرای تطبیق تغییرپذیر نیست.")
        validate_related_organizations(self, run=self.run)
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationException(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.ForeignKey(
        ReconciliationRun, on_delete=models.PROTECT, related_name="exceptions"
    )
    exception_key = models.CharField(max_length=64)
    classification = models.CharField(max_length=48)
    materiality = models.CharField(max_length=24)
    comparison_grain = models.JSONField(default=dict)
    left_lineage = models.JSONField(default=dict)
    right_lineage = models.JSONField(default=dict)
    difference = models.JSONField(default=dict, blank=True)
    evidence_manifest = models.JSONField(default=dict)
    snapshot_hash = models.CharField(max_length=64)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["run", "exception_key"], name="report_recon_exception_key_uq"
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("تصویر مغایرت تغییرپذیر نیست.")
        validate_related_organizations(self, run=self.run)
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationExceptionEvent(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    exception = models.ForeignKey(
        ReconciliationException, on_delete=models.PROTECT, related_name="events"
    )
    action = models.CharField(max_length=32)
    previous_state = models.CharField(max_length=24)
    new_state = models.CharField(max_length=24)
    reason = models.CharField(max_length=500)
    correction_reference = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_reconciliation_exception_events",
    )
    operation_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "operation_key"],
                name="report_recon_event_org_idem_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("رویداد مغایرت تغییرپذیر نیست.")
        validate_related_organizations(self, exception=self.exception)
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationEvidenceLink(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    exception = models.ForeignKey(
        ReconciliationException, on_delete=models.PROTECT, related_name="evidence_links"
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion", on_delete=models.PROTECT
    )
    document_hash = models.CharField(max_length=64)
    evidence_role = models.CharField(max_length=80)
    sensitivity = models.CharField(max_length=32, default="normal")
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["exception", "document_version", "evidence_role"],
                name="report_recon_exception_doc_role_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("پیوند شاهد تطبیق تغییرپذیر نیست.")
        validate_related_organizations(
            self, exception=self.exception, document_version=self.document_version
        )
        if self.document_hash != self.document_version.sha256:
            raise ValidationError("هش نسخه سند با شاهد تطبیق یکسان نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ReconciliationRebuildCheck(UUIDModel, CreatedAtModel):
    class Kind(models.TextChoices):
        EXACT_REPLAY = "exact_replay", "بازپخش دقیق"
        SUCCESSOR = "successor", "محاسبه جانشین"
        PROJECTION_REPAIR = "projection_repair", "ترمیم تصویر"

    class Outcome(models.TextChoices):
        MATCHED = "matched", "منطبق"
        MISMATCHED = "mismatched", "نامنطبق"
        UNVERIFIABLE = "unverifiable", "غیرقابل اثبات"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    original_run = models.ForeignKey(
        ReconciliationRun, on_delete=models.PROTECT, related_name="rebuild_checks"
    )
    successor_run = models.ForeignKey(
        ReconciliationRun,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="predecessor_rebuild_checks",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    original_hash = models.CharField(max_length=64)
    observed_hash = models.CharField(max_length=64, blank=True)
    details = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reconciliation_rebuild_reviews",
    )
    review_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="report_recon_rebuild_org_idem_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("شاهد بازسازی تغییرپذیر نیست.")
        validate_related_organizations(
            self, original_run=self.original_run, successor_run=self.successor_run
        )
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCloseoutProfileStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    IN_REVIEW = "in_review", "در بررسی"
    PUBLISHED = "published", "منتشرشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    RETIRED = "retired", "بازنشسته"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"


class ProjectCloseoutCaseStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    REVIEW_PENDING = "review_pending", "در انتظار بررسی"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"
    REOPENED = "reopened", "بازگشایی‌شده"


class ProjectCloseoutAssessmentStatus(models.TextChoices):
    REQUESTED = "requested", "درخواست‌شده"
    CAPTURING = "capturing", "در حال ثبت منبع"
    ASSESSING = "assessing", "در حال ارزیابی"
    COMPLETED = "completed", "تکمیل‌شده"
    FAILED = "failed", "ناموفق"
    CANCELLED = "cancelled", "لغوشده"


class ProjectCloseoutOutcome(models.TextChoices):
    SATISFIED = "satisfied", "برآورده"
    BLOCKED = "blocked", "مسدود"
    UNKNOWN = "unknown", "نامعلوم"
    INCOMPLETE = "incomplete", "ناقص"
    STALE = "stale", "قدیمی"
    UNVERIFIABLE = "unverifiable", "غیرقابل اثبات"
    NOT_APPLICABLE = "not_applicable", "نامرتبط"
    GATED = "gated_unavailable", "فعال یا در دسترس نیست"


class ProjectCloseoutProfileDefinition(UUIDModel, TimeStampedModel):
    code = models.CharField(max_length=80, unique=True)
    persian_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["code"]

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = self.code.strip().lower()
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if (previous.code, previous.persian_name) != (
                self.code,
                self.persian_name,
            ):
                raise ValidationError(
                    "تعریف الگوی اختتام تغییرپذیر نیست؛ نسخه جدید لازم است."
                )
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCloseoutProfileVersion(UUIDModel, CreatedAtModel):
    definition = models.ForeignKey(
        ProjectCloseoutProfileDefinition,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=ProjectCloseoutProfileStatus.choices,
        default=ProjectCloseoutProfileStatus.DRAFT,
    )
    specification = models.JSONField(default=dict)
    source_owner_approvals = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64)
    governance_reference = models.CharField(max_length=255)
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="project_closeout_profiles_authored",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="project_closeout_profiles_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["definition", "version"], name="report_close_profile_ver_uq"
            ),
            models.UniqueConstraint(
                fields=["definition"],
                condition=Q(status=ProjectCloseoutProfileStatus.PUBLISHED),
                name="report_close_profile_one_pub_uq",
            ),
        ]

    def clean(self) -> None:
        if (
            self.status == ProjectCloseoutProfileStatus.PUBLISHED
            and self.authored_by_id is not None
            and self.authored_by_id == self.published_by_id
        ):
            raise ValidationError("تهیه‌کننده نمی‌تواند همان نسخه الگو را منتشر کند.")
        if self.status == ProjectCloseoutProfileStatus.PUBLISHED and not all(
            key in self.source_owner_approvals
            for key in (
                "project_identity",
                "contract_commercial",
                "billing_claims_settlement",
                "reconciliation_performance",
                "document_completeness",
                "inventory_disposition",
                "equipment_fixed_assets",
                "field_hse_qa",
                "knowledge_lessons",
            )
        ):
            raise ValidationError("تأیید همه مالکان خانواده‌های منبع الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ProjectCloseoutProfileStatus.PUBLISHED,
                ProjectCloseoutProfileStatus.SUPERSEDED,
                ProjectCloseoutProfileStatus.RETIRED,
            }:
                raise ValidationError("نسخه منتشرشده الگوی اختتام تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCloseoutCase(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="closeout_cases"
    )
    profile_version = models.ForeignKey(
        ProjectCloseoutProfileVersion, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=ProjectCloseoutCaseStatus.choices,
        default=ProjectCloseoutCaseStatus.DRAFT,
    )
    revision = models.PositiveIntegerField(default=1)
    current_assessment = models.ForeignKey(
        "ProjectCloseoutAssessment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_for_cases",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_closeout_cases_created",
    )
    create_operation_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "create_operation_key"],
                name="report_close_case_org_idem_uq",
            )
        ]
        indexes: ClassVar[list] = [
            models.Index(
                fields=["organization", "project", "status"],
                name="report_close_case_scope_idx",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, project=self.project, current_assessment=self.current_assessment
        )


class ProjectCloseoutAssessment(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    case = models.ForeignKey(
        ProjectCloseoutCase, on_delete=models.PROTECT, related_name="assessments"
    )
    sequence = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=ProjectCloseoutAssessmentStatus.choices,
        default=ProjectCloseoutAssessmentStatus.REQUESTED,
    )
    cutoff_at = models.DateTimeField()
    source_watermark = models.CharField(max_length=64, blank=True)
    calculation_hash = models.CharField(max_length=64, blank=True)
    coverage = models.JSONField(default=dict)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_closeout_assessments",
    )
    idempotency_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    completed_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["case", "sequence"], name="report_close_assess_seq_uq"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="report_close_assess_org_idem_uq",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, case=self.case, supersedes=self.supersedes
        )


class ProjectCloseoutItemSnapshot(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    assessment = models.ForeignKey(
        ProjectCloseoutAssessment, on_delete=models.PROTECT, related_name="items"
    )
    family_code = models.CharField(max_length=80)
    authority_domain = models.CharField(max_length=160)
    authority_models = models.JSONField(default=list)
    source_permissions = models.JSONField(default=list)
    outcome = models.CharField(max_length=24, choices=ProjectCloseoutOutcome.choices)
    summary = models.JSONField(default=dict)
    source_manifest = models.JSONField(default=dict)
    source_hash = models.CharField(max_length=64)
    sensitivity = models.CharField(max_length=40, default="normal")
    fresh_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["assessment", "family_code"],
                name="report_close_item_family_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("تصویر قلم اختتام تغییرپذیر نیست.")
        validate_related_organizations(self, assessment=self.assessment)
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCloseoutEvent(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    case = models.ForeignKey(
        ProjectCloseoutCase, on_delete=models.PROTECT, related_name="events"
    )
    assessment = models.ForeignKey(
        ProjectCloseoutAssessment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="events",
    )
    action = models.CharField(max_length=32)
    previous_state = models.CharField(max_length=20)
    new_state = models.CharField(max_length=20)
    reason = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_project_closeout_events",
    )
    operation_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "operation_key"],
                name="report_close_event_org_idem_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("رویداد اختتام تغییرپذیر نیست.")
        validate_related_organizations(
            self, case=self.case, assessment=self.assessment
        )
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCloseoutEvidenceLink(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    case = models.ForeignKey(
        ProjectCloseoutCase, on_delete=models.PROTECT, related_name="evidence_links"
    )
    item = models.ForeignKey(
        ProjectCloseoutItemSnapshot,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidence_links",
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion", on_delete=models.PROTECT
    )
    document_hash = models.CharField(max_length=64)
    evidence_role = models.CharField(max_length=80)
    sensitivity = models.CharField(max_length=40, default="normal")
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["case", "document_version", "evidence_role"],
                name="report_close_case_doc_role_uq",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            case=self.case,
            item=self.item,
            document_version=self.document_version,
        )
        if self.document_hash != self.document_version.sha256:
            raise ValidationError("هش نسخه سند با شاهد اختتام یکسان نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("پیوند شاهد اختتام تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCloseoutExportManifest(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    case = models.ForeignKey(ProjectCloseoutCase, on_delete=models.PROTECT)
    assessment = models.ForeignKey(ProjectCloseoutAssessment, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=120)
    request_fingerprint = models.CharField(max_length=64)
    item_ids = models.JSONField(default=list)
    content_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=255)
    expires_at = models.DateTimeField()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="report_close_export_org_idem_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("مانیفست خروجی اختتام تغییرپذیر نیست.")
        validate_related_organizations(
            self, case=self.case, assessment=self.assessment
        )
        self.full_clean()
        super().save(*args, **kwargs)
