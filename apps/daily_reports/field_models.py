"""P9 Field Operations observations, custody bindings, and proposal evidence."""
# ruff: noqa: RUF012

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.documents.models import AbstractTypedDocumentLink, DocumentVersion
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class FieldObservationKind(models.TextChoices):
    GENERAL = "general", "مشاهده عمومی"
    WEATHER = "weather", "وضعیت آب‌وهوا"
    WORK_FRONT = "work_front", "جبهه کاری"
    VISIT = "visit", "بازدید"
    MEETING = "meeting", "جلسه"
    INSTRUCTION = "instruction", "دستور کار ثبت‌شده"


class FieldObservationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    IN_REVIEW = "in_review", "در بررسی"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    REJECTED = "rejected", "ردشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class FieldLocationPermission(models.TextChoices):
    NOT_REQUESTED = "not_requested", "درخواست‌نشده"
    GRANTED = "granted", "مجاز"
    DENIED = "denied", "ردشده"
    UNAVAILABLE = "unavailable", "در دسترس نیست"


class FieldProposalFamily(models.TextChoices):
    PROGRESS = "progress", "پیشنهاد پیشرفت فیزیکی"
    TIME = "time", "پیشنهاد ثبت زمان"
    EQUIPMENT_USAGE = "equipment_usage", "پیشنهاد کارکرد تجهیز"
    MATERIAL_CONSUMPTION = "material_consumption", "پیشنهاد مصرف مصالح"


class FieldProposalStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    ACCEPTED = "accepted", "پذیرفته‌شده برای تحویل"
    REJECTED = "rejected", "ردشده"


class FieldObservation(UUIDModel, TimeStampedModel):
    """Tenant-scoped descriptive field evidence; never a downstream source fact."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="field_observations"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="field_observations"
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        related_name="field_observations",
        null=True,
        blank=True,
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        on_delete=models.PROTECT,
        related_name="field_observations",
        null=True,
        blank=True,
    )
    activity = models.ForeignKey(
        "projects.Activity",
        on_delete=models.PROTECT,
        related_name="field_observations",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=30, choices=FieldObservationKind.choices)
    title = models.CharField(max_length=160)
    summary = models.TextField(blank=True)
    structured_payload = models.JSONField(default=dict, blank=True)
    payload_schema_version = models.PositiveSmallIntegerField(default=1)
    manual_context = models.CharField(max_length=500, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    captured_timezone_offset_minutes = models.SmallIntegerField(null=True, blank=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    location_permission = models.CharField(
        max_length=20,
        choices=FieldLocationPermission.choices,
        default=FieldLocationPermission.NOT_REQUESTED,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    horizontal_accuracy_meters = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    location_captured_at = models.DateTimeField(null=True, blank=True)
    location_mismatch_note = models.CharField(max_length=500, blank=True)
    client_context = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=FieldObservationStatus.choices,
        default=FieldObservationStatus.DRAFT,
        db_index=True,
    )
    revision = models.PositiveIntegerField(default=1)
    canonical_hash = models.CharField(max_length=64, blank=True)
    create_operation_key = models.UUIDField()
    create_payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="field_observations_created"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="field_observations_submitted",
        null=True,
        blank=True,
    )
    submitted_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="field_observations_submitted",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="field_observations_review_started",
        null=True,
        blank=True,
    )
    review_started_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="field_observations_reviewed",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)
    replaces = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="replacement_candidates",
        null=True,
        blank=True,
    )
    correction_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "created_by", "create_operation_key"],
                name="fieldobs_create_operation_uq",
            ),
            models.UniqueConstraint(
                fields=["replaces"],
                condition=Q(status=FieldObservationStatus.ACCEPTED),
                name="fieldobs_one_accepted_successor_uq",
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1), name="fieldobs_revision_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "project", "site", "status"], name="fieldobs_scope_status_idx"),
            models.Index(fields=["organization", "status", "-created_at"], name="fieldobs_org_status_idx"),
        ]
        ordering = ["-created_at"]

    def clean(self) -> None:
        super().clean()
        relations = {"project": self.project}
        if self.site_id:
            relations["site"] = self.site
            if self.site.project_id != self.project_id:
                raise ValidationError({"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."})
        if self.phase_id:
            relations["phase"] = self.phase
            if not self.site_id or self.phase.site_id != self.site_id:
                raise ValidationError({"phase": "فاز باید متعلق به کارگاه انتخاب‌شده باشد."})
        if self.activity_id:
            relations["activity"] = self.activity
            if self.activity.project_id != self.project_id:
                raise ValidationError({"activity": "فعالیت باید متعلق به پروژه انتخاب‌شده باشد."})
        if self.submitted_membership_id:
            relations["submitted_membership"] = self.submitted_membership
        validate_related_organizations(self, **relations)
        self.title = self.title.strip()
        self.manual_context = self.manual_context.strip()
        self.location_mismatch_note = self.location_mismatch_note.strip()
        if not self.title:
            raise ValidationError({"title": "عنوان مشاهده الزامی است."})
        coordinates = self.latitude is not None or self.longitude is not None
        if coordinates:
            if self.latitude is None or self.longitude is None:
                raise ValidationError("مختصات باید کامل باشند.")
            if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
                raise ValidationError("مختصات مکانی معتبر نیست.")
            if (
                self.location_permission != FieldLocationPermission.GRANTED
                or self.horizontal_accuracy_meters is None
                or self.location_captured_at is None
            ):
                raise ValidationError("مختصات به مجوز، دقت و زمان ثبت نیاز دارد.")
        elif self.horizontal_accuracy_meters is not None or self.location_captured_at is not None:
            raise ValidationError("دقت و زمان مکان فقط همراه مختصات مجاز است.")
        if self.replaces_id:
            validate_related_organizations(self, replaces=self.replaces)
            if self.replaces_id == self.pk:
                raise ValidationError({"replaces": "مشاهده نمی‌تواند جایگزین خودش باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            immutable_after_submission = (
                "organization_id", "project_id", "site_id", "phase_id", "activity_id", "kind",
                "title", "summary", "structured_payload", "payload_schema_version", "manual_context",
                "captured_at", "captured_timezone_offset_minutes", "effective_at", "location_permission",
                "latitude", "longitude", "horizontal_accuracy_meters", "location_captured_at",
                "location_mismatch_note", "client_context", "canonical_hash", "create_operation_key",
                "create_payload_hash", "created_by_id", "replaces_id", "correction_reason",
            )
            original = type(self).objects.filter(pk=self.pk).values(*immutable_after_submission, "status").first()
            if original and original["status"] != FieldObservationStatus.DRAFT:
                current = {field: getattr(self, field) for field in immutable_after_submission}
                if any(original[field] != current[field] for field in immutable_after_submission):
                    raise ValidationError("مشاهده ارسال‌شده قابل ویرایش نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("مشاهده میدانی بخشی از سابقه است و حذف نمی‌شود.")


class FieldObservationEvidenceLink(AbstractTypedDocumentLink):
    """Append-only pin of one DMS version and its recorded integrity hash."""

    target_field_name = "field_observation"
    field_observation = models.ForeignKey(
        FieldObservation, on_delete=models.PROTECT, related_name="evidence_links"
    )
    document_version = models.ForeignKey(
        DocumentVersion, on_delete=models.PROTECT, related_name="field_observation_links"
    )
    sha256 = models.CharField(max_length=64, default="")
    operation_key = models.UUIDField(default=uuid.uuid4)
    payload_hash = models.CharField(max_length=64, default="")

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["field_observation", "document_version"],
                name="fieldobs_evidence_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                name="fieldobs_evidence_operation_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "document"], name="fieldobsev_org_doc_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, field_observation=self.field_observation, document_version=self.document_version
        )
        if self.document_version.document_id != self.document_id:
            raise ValidationError("نسخه سند باید متعلق به سند پیوندشده باشد.")
        if self.sha256 != self.document_version.sha256:
            raise ValidationError("هش سند با نسخه DMS مطابقت ندارد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.document_version_id:
            self.sha256 = self.document_version.sha256
            if not self.payload_hash:
                self.payload_hash = str(self.document_version.sha256)
        if self.pk and not self._state.adding:
            immutable_fields = (
                "organization_id", "document_id", "field_observation_id",
                "document_version_id", "sha256", "created_by_id", "operation_key",
                "payload_hash",
            )
            original = type(self).objects.filter(pk=self.pk).values(*immutable_fields).first()
            if original and original != {
                field: getattr(self, field) for field in immutable_fields
            }:
                raise ValidationError("پیوند شواهد تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("پیوند شواهد بخشی از سابقه است و حذف نمی‌شود.")


class FieldObservationTransition(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    observation = models.ForeignKey(FieldObservation, on_delete=models.PROTECT, related_name="transitions")
    from_status = models.CharField(max_length=20, choices=FieldObservationStatus.choices)
    to_status = models.CharField(max_length=20, choices=FieldObservationStatus.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reason = models.TextField(blank=True)
    canonical_hash = models.CharField(max_length=64, blank=True)
    operation_key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor", "to_status", "operation_key"],
                name="fieldobs_transition_operation_uq",
            )
        ]
        ordering = ["created_at"]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, observation=self.observation)
        if self.actor and self.observation.organization_id != self.organization_id:
            raise ValidationError("تاریخچه مشاهده باید در همان سازمان باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("تاریخچه وضعیت مشاهده تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("تاریخچه وضعیت مشاهده حذف نمی‌شود.")


class FieldObservationDraftRevision(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    observation = models.ForeignKey(FieldObservation, on_delete=models.PROTECT, related_name="draft_revisions")
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    operation_key = models.UUIDField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["observation", "revision"], name="fieldobs_draft_revision_uq"),
            models.UniqueConstraint(
                fields=["organization", "actor", "operation_key"],
                name="fieldobs_draft_operation_uq",
            ),
        ]
        ordering = ["revision"]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, observation=self.observation)
        if self.observation.organization_id != self.organization_id:
            raise ValidationError("نسخه پیش‌نویس باید در همان سازمان باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نسخه پیش‌نویس مشاهده تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("نسخه پیش‌نویس مشاهده حذف نمی‌شود.")


class FieldDownstreamProposal(UUIDModel, TimeStampedModel):
    """Reviewed source envelope only; no receiving-domain mutation is permitted."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="field_proposals")
    observation = models.ForeignKey(FieldObservation, on_delete=models.PROTECT, related_name="proposals")
    family = models.CharField(max_length=30, choices=FieldProposalFamily.choices)
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="field_proposals")
    site = models.ForeignKey("projects.ProjectSite", on_delete=models.PROTECT, related_name="field_proposals", null=True, blank=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    lines = models.JSONField(default=list)
    source_canonical_hash = models.CharField(max_length=64)
    proposal_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=FieldProposalStatus.choices, default=FieldProposalStatus.DRAFT)
    create_operation_key = models.UUIDField()
    create_payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="field_proposals_created")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="field_proposals_submitted", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="field_proposals_reviewed", null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "created_by", "create_operation_key"],
                name="fieldproposal_create_operation_uq",
            )
        ]
        indexes = [models.Index(fields=["organization", "project", "status"], name="fieldproposal_scope_status_idx")]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, observation=self.observation, project=self.project)
        if self.observation.project_id != self.project_id:
            raise ValidationError("پیشنهاد باید متعلق به پروژه مشاهده باشد.")
        if self.site_id:
            validate_related_organizations(self, site=self.site)
            if self.site.project_id != self.project_id:
                raise ValidationError("کارگاه پیشنهاد باید متعلق به پروژه باشد.")
        if self.source_canonical_hash != self.observation.canonical_hash:
            raise ValidationError("هش منبع پیشنهاد با مشاهده پذیرفته‌شده مطابقت ندارد.")
        if not isinstance(self.lines, list) or not self.lines:
            raise ValidationError({"lines": "حداقل یک سطر پیشنهاد الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            protected = ("organization_id", "observation_id", "family", "project_id", "site_id", "effective_at", "lines", "source_canonical_hash", "proposal_hash", "create_operation_key", "create_payload_hash", "created_by_id")
            original = type(self).objects.filter(pk=self.pk).values(*protected, "status").first()
            if original and original["status"] != FieldProposalStatus.DRAFT and any(
                original[field] != getattr(self, field) for field in protected
            ):
                raise ValidationError("پیشنهاد ارسال‌شده قابل ویرایش نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("پیشنهاد تحویل بخشی از سابقه است و حذف نمی‌شود.")


class FieldProposalTransition(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    proposal = models.ForeignKey(FieldDownstreamProposal, on_delete=models.PROTECT, related_name="transitions")
    from_status = models.CharField(max_length=20, choices=FieldProposalStatus.choices)
    to_status = models.CharField(max_length=20, choices=FieldProposalStatus.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reason = models.TextField(blank=True)
    proposal_hash = models.CharField(max_length=64, blank=True)
    operation_key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor", "to_status", "operation_key"],
                name="fieldproposal_transition_operation_uq",
            )
        ]
        ordering = ["created_at"]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, proposal=self.proposal)
        if self.proposal.organization_id != self.organization_id:
            raise ValidationError("تاریخچه پیشنهاد باید در همان سازمان باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("تاریخچه پیشنهاد تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("تاریخچه پیشنهاد حذف نمی‌شود.")
