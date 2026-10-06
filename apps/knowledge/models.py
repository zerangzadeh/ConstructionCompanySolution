"""P9-S21–S24 reviewed derivative knowledge; never source-domain authority."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import CreatedAtModel, TimeStampedModel, UUIDModel


class KnowledgeScope(models.TextChoices):
    TENANT = "tenant", "Tenant"
    PLATFORM = "platform", "Platform"


class KnowledgeAuthority(models.TextChoices):
    ADVISORY = "advisory", "راهنمایی"
    RECOMMENDED = "recommended_practice", "روش پیشنهادی"
    CONTROLLED = "controlled_guidance", "راهنمایی کنترل‌شده داخلی"


class KnowledgeSensitivity(models.TextChoices):
    INTERNAL = "internal", "داخلی"
    SENSITIVE = "sensitive", "حساس"


class CandidateStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    IN_REVIEW = "in_review", "در بررسی"
    CHANGES_REQUESTED = "changes_requested", "نیازمند اصلاح"
    RECOMMENDED = "recommended", "توصیه‌شده برای انتشار"
    APPROVED = "approved_for_publication", "تأییدشده برای انتشار"
    REJECTED = "rejected", "ردشده"
    WITHDRAWN = "withdrawn_candidate", "پس‌گرفته‌شده"


class PublicationStatus(models.TextChoices):
    CURRENT = "published_current", "منتشرشده و جاری"
    REVIEW_DUE = "review_due", "نیازمند بازبینی"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"
    ARCHIVED = "archived", "بایگانی‌شده"


class RecurrenceStatus(models.TextChoices):
    VALID = "valid", "معتبر"
    INVALIDATED = "invalidated", "بی‌اعتبارشده"
    REPLACED = "replaced", "جایگزین‌شده"


class ReuseType(models.TextChoices):
    REFERENCED = "referenced", "ارجاع"
    ATTACHED = "attached_by_reference", "پیوست با ارجاع"
    ADOPTED = "adopted", "پذیرفته‌شده"
    TEMPLATE = "template_used", "استفاده از الگو"
    CITED = "cited_in_decision", "استناد در تصمیم"
    ACKNOWLEDGED = "acknowledged", "دریافت/مطالعه تأییدشده"


class ReuseStatus(models.TextChoices):
    VALID = "valid", "معتبر"
    REVERSAL = "reversal", "برگشت"
    REPLACEMENT = "replacement", "جایگزین"


class PublicationEventType(models.TextChoices):
    PUBLISHED = "published", "انتشار"
    SUPERSEDED = "superseded", "جایگزینی"
    WITHDRAWN = "withdrawn", "پس‌گرفتن"


class PromotionStatus(models.TextChoices):
    REQUESTED = "requested", "درخواست‌شده"
    RECOMMENDED = "recommended", "توصیه‌شده"
    REJECTED = "rejected", "ردشده"
    APPROVED = "approved", "تأییدشده"
    PUBLISHED = "published", "منتشرشده"


class ImmutableKnowledgeQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("تاریخچه دانش تغییرپذیر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("تاریخچه دانش حذف‌پذیر نیست.")


class ImmutableKnowledgeManager(
    models.Manager.from_queryset(ImmutableKnowledgeQuerySet)
):
    pass


class KnowledgeCandidate(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_candidates",
    )
    scope = models.CharField(max_length=12, choices=KnowledgeScope.choices)
    source_organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_promotions",
    )
    title = models.CharField(max_length=240)
    body = models.TextField()
    knowledge_type = models.CharField(max_length=40)
    authority_classification = models.CharField(
        max_length=30, choices=KnowledgeAuthority.choices
    )
    sensitivity = models.CharField(
        max_length=20,
        choices=KnowledgeSensitivity.choices,
        default=KnowledgeSensitivity.INTERNAL,
    )
    audience = models.CharField(max_length=80)
    category_code = models.CharField(max_length=80)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=32,
        choices=CandidateStatus.choices,
        default=CandidateStatus.DRAFT,
        db_index=True,
    )
    revision = models.PositiveIntegerField(default=1)
    content_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_candidates_created",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_candidates_submitted",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_candidates_reviewed",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_candidates_approved",
    )
    tenant_disclosure_authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_promotions_authorized",
    )
    operation_key = models.UUIDField(default=uuid.uuid4)
    corrects_version = models.ForeignKey(
        "KnowledgePublicationVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_candidates",
    )
    correction_reason = models.TextField(blank=True)

    class Meta:
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=(
                    Q(
                        scope=KnowledgeScope.TENANT,
                        organization__isnull=False,
                        source_organization__isnull=True,
                    )
                    | Q(scope=KnowledgeScope.PLATFORM, organization__isnull=True)
                ),
                name="knowledge_candidate_scope_owner_ck",
            ),
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                condition=Q(scope=KnowledgeScope.TENANT),
                name="knowledge_candidate_tenant_op_uq",
            ),
        ]

    def clean(self) -> None:
        if self.scope == KnowledgeScope.PLATFORM and bool(
            self.source_organization_id
        ) != bool(self.tenant_disclosure_authorized_by_id):
            raise ValidationError(
                "منشأ Tenant و مجوز افشای آن باید برای ترویج Platform هم‌زمان ثبت شوند."
            )
        if self.authority_classification not in KnowledgeAuthority.values:
            raise ValidationError("طبقه اختیار دانش معتبر نیست.")
        if bool(self.corrects_version_id) != bool(self.correction_reason.strip()):
            raise ValidationError(
                "اصلاح انتشار باید نسخه پیشین و دلیل صریح داشته باشد."
            )
        if self.corrects_version_id and self.scope != KnowledgeScope.TENANT:
            raise ValidationError(
                "اصلاح انتشار Tenant باید در همان دامنه Tenant بماند."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and not getattr(self, "_knowledge_transition", False)
        ):
            raise ValidationError("کاندید دانش فقط از طریق سرویس چرخه عمر تغییر می‌کند.")
        self.full_clean()
        super().save(*args, **kwargs)


class KnowledgeCandidateRevision(UUIDModel, CreatedAtModel):
    candidate = models.ForeignKey(
        KnowledgeCandidate, on_delete=models.PROTECT, related_name="revisions"
    )
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_revisions_submitted",
    )
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["candidate", "revision"], name="knowledge_candidate_revision_uq"
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه ارسال‌شده قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgeSourcePin(UUIDModel, CreatedAtModel):
    candidate_revision = models.ForeignKey(
        KnowledgeCandidateRevision, on_delete=models.PROTECT, related_name="source_pins"
    )
    source_organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    source_type = models.CharField(max_length=48)
    source_id = models.UUIDField()
    source_version = models.CharField(max_length=80)
    source_status = models.CharField(max_length=48)
    document = models.ForeignKey(
        "documents.Document", null=True, blank=True, on_delete=models.PROTECT
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion", null=True, blank=True, on_delete=models.PROTECT
    )
    sha256 = models.CharField(max_length=64, blank=True)
    citation_purpose = models.CharField(max_length=160)
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=[
                    "candidate_revision",
                    "source_type",
                    "source_id",
                    "source_version",
                ],
                name="knowledge_source_pin_uq",
            )
        ]

    def clean(self) -> None:
        if bool(self.document_id) != bool(self.document_version_id):
            raise ValidationError("سند و نسخه دقیق سند باید هم‌زمان ثبت شوند.")
        if self.document_version_id and (
            self.document_version.document_id != self.document_id
            or self.document_version.organization_id != self.source_organization_id
            or self.sha256 != self.document_version.sha256
        ):
            raise ValidationError("پین سند، نسخه و هش باید دقیقاً منطبق باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("پین منبع قابل تغییر نیست.")
        if self.document_version_id:
            self.sha256 = self.document_version.sha256
        self.full_clean()
        super().save(*args, **kwargs)


class KnowledgeReview(UUIDModel, CreatedAtModel):
    candidate_revision = models.ForeignKey(
        KnowledgeCandidateRevision, on_delete=models.PROTECT, related_name="reviews"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_reviews",
    )
    outcome = models.CharField(max_length=24)
    reason = models.TextField(blank=True)
    operation_key = models.UUIDField()
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["candidate_revision", "reviewer", "operation_key"],
                name="knowledge_review_op_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("بررسی دانش قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgePublication(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_publications",
    )
    scope = models.CharField(max_length=12, choices=KnowledgeScope.choices)
    source_candidate = models.OneToOneField(
        KnowledgeCandidate, on_delete=models.PROTECT, related_name="publication"
    )
    current_version = models.ForeignKey(
        "KnowledgePublicationVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_for_publications",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=(
                    Q(scope=KnowledgeScope.TENANT, organization__isnull=False)
                    | Q(scope=KnowledgeScope.PLATFORM, organization__isnull=True)
                ),
                name="knowledge_publication_scope_owner_ck",
            )
        ]


class KnowledgePublicationVersion(UUIDModel, CreatedAtModel):
    publication = models.ForeignKey(
        KnowledgePublication, on_delete=models.PROTECT, related_name="versions"
    )
    candidate_revision = models.ForeignKey(
        KnowledgeCandidateRevision,
        on_delete=models.PROTECT,
        related_name="publication_versions",
    )
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=240)
    body = models.TextField()
    metadata = models.JSONField(default=dict)
    manifest_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=24,
        choices=PublicationStatus.choices,
        default=PublicationStatus.CURRENT,
        db_index=True,
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_versions_published",
    )
    published_at = models.DateTimeField()
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successors",
    )
    withdrawal_reason = models.TextField(blank=True)
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["publication", "version_number"],
                name="knowledge_publication_version_uq",
            ),
            models.UniqueConstraint(
                fields=["supersedes"],
                condition=Q(supersedes__isnull=False),
                name="knowledge_publication_single_successor_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding and not getattr(self, "_knowledge_transition", False):
            raise ValidationError("نسخه منتشرشده قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgePublicationEvent(UUIDModel, CreatedAtModel):
    publication_version = models.ForeignKey(
        KnowledgePublicationVersion,
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    event_type = models.CharField(max_length=16, choices=PublicationEventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_publication_events",
    )
    reason = models.TextField(blank=True)
    related_version = models.ForeignKey(
        KnowledgePublicationVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="related_lifecycle_events",
    )
    operation_key = models.UUIDField(default=uuid.uuid4)
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["actor", "operation_key"],
                name="knowledge_publication_event_op_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("رویداد چرخه انتشار قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgeRecurrenceEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="knowledge_recurrences",
    )
    recurrence_key = models.CharField(max_length=120)
    scope_description = models.CharField(max_length=240)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=16, choices=RecurrenceStatus.choices, default=RecurrenceStatus.VALID
    )
    manifest_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_recurrences_created",
    )
    candidate_proposal = models.ForeignKey(
        KnowledgeCandidate,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="recurrence_proposals",
    )
    replaces = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replacements",
    )
    correction_reason = models.TextField(blank=True)
    operation_key = models.UUIDField()

    class Meta:
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="knowledge_recurrence_period_ck",
            ),
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                name="knowledge_recurrence_op_uq",
            ),
            models.UniqueConstraint(
                fields=["replaces"],
                condition=Q(replaces__isnull=False),
                name="knowledge_recurrence_single_correction_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شاهد تکرار قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgeRecurrenceSource(UUIDModel, CreatedAtModel):
    recurrence = models.ForeignKey(
        KnowledgeRecurrenceEvidence, on_delete=models.PROTECT, related_name="sources"
    )
    source_type = models.CharField(max_length=48)
    source_id = models.UUIDField()
    source_version = models.CharField(max_length=80)
    source_status = models.CharField(max_length=48)
    source_hash = models.CharField(max_length=64)
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["recurrence", "source_type", "source_id"],
                name="knowledge_recurrence_source_lineage_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("منبع تکرار قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgeReuseEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="knowledge_reuse_evidence",
    )
    publication_version = models.ForeignKey(
        KnowledgePublicationVersion,
        on_delete=models.PROTECT,
        related_name="reuse_events",
    )
    reuse_type = models.CharField(max_length=32, choices=ReuseType.choices)
    consumer_type = models.CharField(max_length=80)
    consumer_id = models.UUIDField()
    consumer_version = models.CharField(max_length=80)
    purpose = models.CharField(max_length=240)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_reuse_events",
    )
    status = models.CharField(
        max_length=16, choices=ReuseStatus.choices, default=ReuseStatus.VALID
    )
    reverses = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_by",
    )
    reason = models.TextField(blank=True)
    operation_key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "actor", "operation_key"],
                name="knowledge_reuse_op_uq",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "publication_version",
                    "reuse_type",
                    "consumer_type",
                    "consumer_id",
                    "consumer_version",
                ],
                condition=Q(status=ReuseStatus.VALID),
                name="knowledge_reuse_business_uq",
            ),
            models.UniqueConstraint(
                fields=["reverses"],
                condition=Q(reverses__isnull=False),
                name="knowledge_reuse_single_correction_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شاهد استفاده مجدد قابل تغییر نیست.")
        super().save(*args, **kwargs)


class KnowledgePromotion(UUIDModel, CreatedAtModel):
    source_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="knowledge_promotion_requests",
    )
    source_version = models.ForeignKey(
        KnowledgePublicationVersion,
        on_delete=models.PROTECT,
        related_name="promotion_requests",
    )
    sanitized_snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    anonymization_statement = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=PromotionStatus.choices,
        default=PromotionStatus.REQUESTED,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_promotions_requested",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_promotions_reviewed",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="knowledge_promotions_approved",
    )
    platform_candidate = models.OneToOneField(
        KnowledgeCandidate,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="promotion",
    )
    review_reason = models.TextField(blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["source_organization", "requested_by", "operation_key"],
                name="knowledge_promotion_op_uq",
            ),
            models.UniqueConstraint(
                fields=["source_version"],
                condition=Q(
                    status__in=[
                        PromotionStatus.REQUESTED,
                        PromotionStatus.RECOMMENDED,
                        PromotionStatus.APPROVED,
                    ]
                ),
                name="knowledge_promotion_active_source_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and not getattr(self, "_knowledge_transition", False)
        ):
            raise ValidationError("درخواست ترویج فقط از مسیر چرخه عمر تغییر می‌کند.")
        super().save(*args, **kwargs)


class KnowledgePromotionEvent(UUIDModel, CreatedAtModel):
    promotion = models.ForeignKey(
        KnowledgePromotion, on_delete=models.PROTECT, related_name="events"
    )
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, choices=PromotionStatus.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_promotion_events",
    )
    reason = models.TextField(blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)
    objects = ImmutableKnowledgeManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["promotion", "actor", "operation_key"],
                name="knowledge_promotion_event_op_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("رویداد ترویج قابل تغییر نیست.")
        super().save(*args, **kwargs)
