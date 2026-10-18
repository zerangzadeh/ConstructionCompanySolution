"""Commercial-owned pre-award Tender/Bid identity and immutable history."""

# Django Meta collections are declarative schema, not mutable shared runtime state.
# ruff: noqa: RUF012

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class TenderBidStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    UNDER_REVIEW = "under_review", "در بررسی"
    WON = "won", "برنده"
    LOST = "lost", "بازنده"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"
    CANCELLED = "cancelled", "لغوشده"


TENDER_BID_TRANSITIONS: dict[str, frozenset[str]] = {
    TenderBidStatus.DRAFT: frozenset(
        {TenderBidStatus.SUBMITTED, TenderBidStatus.CANCELLED}
    ),
    TenderBidStatus.SUBMITTED: frozenset(
        {TenderBidStatus.UNDER_REVIEW, TenderBidStatus.WITHDRAWN}
    ),
    TenderBidStatus.UNDER_REVIEW: frozenset(
        {TenderBidStatus.WON, TenderBidStatus.LOST, TenderBidStatus.WITHDRAWN}
    ),
    TenderBidStatus.WON: frozenset(),
    TenderBidStatus.LOST: frozenset(),
    TenderBidStatus.WITHDRAWN: frozenset(),
    TenderBidStatus.CANCELLED: frozenset(),
}


class ImmutableHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("تاریخچه مناقصه تغییرپذیر نیست.")

    def delete(self):
        raise ValidationError("تاریخچه مناقصه حذف‌پذیر نیست.")


class ImmutableHistoryManager(models.Manager.from_queryset(ImmutableHistoryQuerySet)):
    pass


class TenderBidActivation(UUIDModel, CreatedAtModel):
    """Explicit tenant activation evidence; absence denies runtime mutations."""

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="tender_bid_activation",
    )
    is_active = models.BooleanField(default=False)
    policy_reference = models.CharField(max_length=160)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commercial_tender_bid_activations",
    )


class TenderBid(UUIDModel, CreatedAtModel):
    """Stable pre-award opportunity identity; status lives in immutable revisions."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="tender_bids",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tender_bids",
    )
    opportunity_code = models.CharField(max_length=80)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commercial_tender_bids_created",
    )
    objects = ImmutableHistoryManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "opportunity_code"],
                name="uq_tender_bid_org_code",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "project"], name="tender_bid_org_project_idx"
            )
        ]

    def clean(self):
        super().clean()
        self.opportunity_code = self.opportunity_code.strip().upper()
        if not self.opportunity_code:
            raise ValidationError("شناسه فرصت الزامی است.")
        validate_related_organizations(
            self, project=self.project if self.project_id else None
        )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("هویت فرصت مناقصه تغییرپذیر نیست.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("فرصت مناقصه حذف‌پذیر نیست.")


class TenderBidRevision(UUIDModel, CreatedAtModel):
    """Append-only state and detail snapshot, including post-submission corrections."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    tender_bid = models.ForeignKey(
        TenderBid, on_delete=models.PROTECT, related_name="revisions"
    )
    version = models.PositiveIntegerField()
    previous_revision = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successor_revisions",
    )
    status = models.CharField(max_length=20, choices=TenderBidStatus.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    submission_reference = models.CharField(max_length=160, blank=True)
    result_reference = models.CharField(max_length=160, blank=True)
    bid_bond_reference = models.CharField(max_length=160, blank=True)
    bid_cost_reference = models.CharField(max_length=160, blank=True)
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commercial_tender_bid_revisions_created",
    )

    objects = ImmutableHistoryManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tender_bid", "version"], name="uq_tender_bid_revision_version"
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="ck_tender_bid_revision_version"
            ),
        ]
        ordering = ["version"]

    def clean(self):
        super().clean()
        validate_related_organizations(
            self,
            tender_bid=self.tender_bid if self.tender_bid_id else None,
            previous_revision=self.previous_revision
            if self.previous_revision_id
            else None,
        )
        self.title = self.title.strip()
        self.reason = self.reason.strip()
        if not self.title or not self.reason:
            raise ValidationError("عنوان و دلیل ثبت نسخه الزامی است.")
        if (
            self.previous_revision_id
            and self.previous_revision.tender_bid_id != self.tender_bid_id
        ):
            raise ValidationError("نسخه پیشین باید متعلق به همین مناقصه باشد.")
        if self.previous_revision_id is None:
            if self.version != 1 or self.status != TenderBidStatus.DRAFT:
                raise ValidationError("نسخه نخست باید پیش‌نویس باشد.")
        else:
            previous = self.previous_revision
            if self.version != previous.version + 1:
                raise ValidationError("شماره نسخه باید پیوسته باشد.")
            if self.status == previous.status:
                if not TENDER_BID_TRANSITIONS[previous.status]:
                    raise ValidationError("وضعیت نهایی قابل بازنگری نیست.")
            elif self.status not in TENDER_BID_TRANSITIONS.get(
                previous.status, frozenset()
            ):
                raise ValidationError("گذار وضعیت معتبر نیست.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("نسخه ثبت‌شده مناقصه تغییرپذیر نیست.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("نسخه ثبت‌شده مناقصه حذف‌پذیر نیست.")


class TenderBidEvidence(UUIDModel, CreatedAtModel):
    """Pinned DMS-version link; DMS keeps document bytes and access authority."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    revision = models.ForeignKey(
        TenderBidRevision, on_delete=models.PROTECT, related_name="evidence_links"
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion", on_delete=models.PROTECT
    )
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    objects = ImmutableHistoryManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "document_version"],
                name="uq_tender_bid_revision_document",
            ),
        ]

    def clean(self):
        super().clean()
        validate_related_organizations(
            self,
            revision=self.revision if self.revision_id else None,
            document_version=self.document_version
            if self.document_version_id
            else None,
        )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("پیوند شاهد مناقصه تغییرپذیر نیست.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("پیوند شاهد مناقصه حذف‌پذیر نیست.")
