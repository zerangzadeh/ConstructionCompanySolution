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
    metric_version = models.ForeignKey(MetricDefinitionVersion, on_delete=models.PROTECT)
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
            raise ValidationError("نتیجه نهایی شاخص تغییرپذیر است.")
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
