"""P9-S12–S15 partner qualification and explainable evaluation facts."""
# ruff: noqa: RUF012

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.documents.models import Document, DocumentVersion
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class QualificationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    UNDER_REVIEW = "under_review", "در بررسی"
    APPROVED = "approved", "تأییدشده"
    RETURNED = "returned", "برگشت‌شده"
    REJECTED = "rejected", "ردشده"
    SUSPENDED = "suspended", "تعلیق‌شده"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class EvaluationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    UNDER_REVIEW = "under_review", "در بررسی"
    PUBLISHED = "published", "منتشرشده"
    RETURNED = "returned", "برگشت‌شده"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class AppealStatus(models.TextChoices):
    OPEN = "open", "باز"
    UPHELD = "upheld", "پذیرفته‌شده"
    DISMISSED = "dismissed", "ردشده"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"


class PartnerProfile(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    party = models.OneToOneField(
        "parties.BusinessParty",
        on_delete=models.PROTECT,
        related_name="partner_profile",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_profiles_created",
    )

    def clean(self) -> None:
        validate_related_organizations(self, party=self.party)


class QualificationRequirement(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    code = models.CharField(max_length=60)
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    category_code = models.CharField(max_length=60)
    source_reference = models.CharField(max_length=300)
    source_version = models.CharField(max_length=100)
    evidence_required = models.BooleanField(default=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_requirements_published",
    )
    canonical_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="partner_requirement_version_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نسخه الزام صلاحیت تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class PartnerQualification(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    profile = models.ForeignKey(
        PartnerProfile, on_delete=models.PROTECT, related_name="qualifications"
    )
    requirement = models.ForeignKey(
        QualificationRequirement,
        on_delete=models.PROTECT,
        related_name="qualifications",
    )
    reference_number = models.CharField(max_length=80)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=QualificationStatus.choices,
        default=QualificationStatus.DRAFT,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="partner_qualifications_submitted",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="partner_qualifications_reviewed",
    )
    replaces = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replacements",
    )
    reason = models.TextField(blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "profile", "reference_number"],
                name="partner_qualification_ref_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "submitted_by", "operation_key"],
                name="partner_qualification_op_uq",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True)
                | Q(valid_from__isnull=True)
                | Q(valid_until__gte=models.F("valid_from")),
                name="partner_qualification_valid_dates",
            ),
        ]

    @property
    def is_expired(self) -> bool:
        return bool(
            self.status == QualificationStatus.APPROVED
            and self.valid_until
            and self.valid_until < timezone.localdate()
        )

    def clean(self) -> None:
        validate_related_organizations(
            self, profile=self.profile, requirement=self.requirement
        )
        if self.replaces_id:
            validate_related_organizations(self, replaces=self.replaces)
            if (
                self.replaces.profile_id != self.profile_id
                or self.replaces.requirement_id != self.requirement_id
            ):
                raise ValidationError(
                    "جایگزین صلاحیت باید همان همکار و الزام را داشته باشد."
                )

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and not getattr(self, "_service_transition", False)
        ):
            raise ValidationError("صلاحیت فقط از طریق سرویس چرخه عمر تغییر می‌کند.")
        self.full_clean()
        super().save(*args, **kwargs)


class PartnerEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    qualification = models.ForeignKey(
        PartnerQualification, on_delete=models.PROTECT, related_name="evidence"
    )
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="partner_evidence"
    )
    document_version = models.ForeignKey(
        DocumentVersion, on_delete=models.PROTECT, related_name="partner_evidence"
    )
    sha256 = models.CharField(max_length=64)
    purpose = models.CharField(max_length=40, default="qualification")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_evidence_linked",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["qualification", "document_version"],
                name="partner_evidence_version_uq",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            qualification=self.qualification,
            document=self.document,
            document_version=self.document_version,
        )
        if (
            self.document_version.document_id != self.document_id
            or self.sha256 != self.document_version.sha256
        ):
            raise ValidationError("سند، نسخه و هش شواهد باید دقیقاً منطبق باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("پیوند شواهد تغییرپذیر نیست.")
        self.sha256 = self.document_version.sha256
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def target(self) -> PartnerQualification:
        return self.qualification

    @property
    def target_type(self) -> str:
        return "partner_qualification"


class PartnerCategoryApproval(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    profile = models.ForeignKey(
        PartnerProfile, on_delete=models.PROTECT, related_name="category_approvals"
    )
    category_code = models.CharField(max_length=60)
    requirements_snapshot = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="not_eligible")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="partner_category_decisions",
    )
    decision_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "profile", "category_code"],
                name="partner_category_approval_uq",
            )
        ]


class PartnerEvaluation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    profile = models.ForeignKey(
        PartnerProfile, on_delete=models.PROTECT, related_name="evaluations"
    )
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    site = models.ForeignKey(
        "projects.ProjectSite", null=True, blank=True, on_delete=models.PROTECT
    )
    period_start = models.DateField()
    period_end = models.DateField()
    criteria_snapshot = models.JSONField(default=list)
    scores = models.JSONField(default=dict)
    total_score = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    explanation_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=20, choices=EvaluationStatus.choices, default=EvaluationStatus.DRAFT
    )
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_evaluations_authored",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="partner_evaluations_published",
    )
    replaces = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successors",
    )
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="partner_evaluation_period_valid",
            ),
            models.UniqueConstraint(
                fields=["organization", "authored_by", "operation_key"],
                name="partner_evaluation_op_uq",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(self, profile=self.profile, project=self.project)
        if self.site_id and (
            self.site.organization_id != self.organization_id
            or self.site.project_id != self.project_id
        ):
            raise ValidationError("کارگاه ارزیابی باید متعلق به پروژه باشد.")
        if self.replaces_id:
            validate_related_organizations(self, replaces=self.replaces)
            if (
                self.replaces.profile_id != self.profile_id
                or self.replaces.project_id != self.project_id
            ):
                raise ValidationError(
                    "ارزیابی جایگزین باید همان همکار و پروژه را داشته باشد."
                )

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and not getattr(self, "_service_transition", False)
        ):
            raise ValidationError("ارزیابی فقط از طریق سرویس چرخه عمر تغییر می‌کند.")
        self.full_clean()
        super().save(*args, **kwargs)


class PartnerEvaluationAppeal(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    evaluation = models.ForeignKey(
        PartnerEvaluation, on_delete=models.PROTECT, related_name="appeals"
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=AppealStatus.choices, default=AppealStatus.OPEN
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_appeals_raised",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="partner_appeals_decided",
    )
    decision_reason = models.TextField(blank=True)


class PartnerLifecycleEvent(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    entity_type = models.CharField(max_length=60)
    entity_id = models.UUIDField()
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_lifecycle_events",
    )
    operation_key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor", "entity_type", "operation_key"],
                name="partner_event_op_uq",
            )
        ]


class PartnerEligibilityProposal(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    profile = models.ForeignKey(
        PartnerProfile, on_delete=models.PROTECT, related_name="proposals"
    )
    target_domain = models.CharField(max_length=50)
    source_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="partner_proposals_created",
    )
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                name="partner_proposal_op_uq",
            )
        ]
