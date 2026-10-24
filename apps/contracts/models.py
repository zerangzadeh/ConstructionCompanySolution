import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models import AbstractTypedDocumentLink
from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ContractDocumentLink(AbstractTypedDocumentLink):
    """Contract-owned append-only evidence link."""

    target_field_name = "contract"
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="typed_document_links",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "contract"], name="contract_document_link_uq"
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="contract_doclink_org_doc_idx",
            )
        ]


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    COMPLETED = "completed", "تکمیل‌شده"
    TERMINATED = "terminated", "خاتمه‌یافته"


class ContractDirection(models.TextChoices):
    RECEIVABLE = "receivable", "دریافتنی"
    PAYABLE = "payable", "پرداختنی"


class ContractType(models.TextChoices):
    CLIENT = "client", "قرارداد کارفرمایی"
    SUBCONTRACT = "subcontract", "قرارداد پیمانکار جزء"
    SUPPLIER = "supplier", "قرارداد تأمین‌کننده"
    OTHER = "other", "سایر"


class ContractAmendmentStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"


class ContractTermVersionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class ContractTermCalculationBasis(models.TextChoices):
    GROSS = "gross", "مبلغ ناخالص"


class RetentionReleaseRequirement(models.TextChoices):
    UNCONFIGURED = "unconfigured", "تعریف‌نشده"
    EVIDENCE_ONLY = "evidence_only", "با شواهد قراردادی"
    APPROVED_CLEARANCE = "approved_clearance", "با مفاصاحساب تأییدشده"


class ContractualRecordKind(models.TextChoices):
    SITE_INSTRUCTION = "site_instruction", "دستور کارگاهی"
    VARIATION = "variation", "تغییر / دستور تغییر"
    CLAIM = "claim", "ادعای قراردادی"
    EOT = "eot", "تمدید مدت"


class ContractualRecordStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    RETURNED = "returned", "بازگردانده‌شده"
    WITHDRAWN = "withdrawn", "مستردشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    CANCELLED = "cancelled", "باطل‌شده"


class ContractualRevisionAction(models.TextChoices):
    ORIGINAL = "original", "نسخه اصلی"
    CORRECTION = "correction", "اصلاح / جایگزینی"
    CANCELLATION = "cancellation", "ابطال پیوندخورده"


class Contract(UUIDModel, TimeStampedModel):
    """A project contract owned by one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField("شماره قرارداد", max_length=80)
    title = models.CharField("عنوان قرارداد", max_length=255)
    counterparty_name = models.CharField("نام طرف قرارداد", max_length=255)
    party = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="طرف تجاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts",
    )
    direction = models.CharField(
        "جهت قرارداد",
        max_length=20,
        choices=ContractDirection.choices,
        null=True,
        blank=True,
    )
    contract_type = models.CharField(
        "نوع قرارداد",
        max_length=20,
        choices=ContractType.choices,
        null=True,
        blank=True,
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        db_index=True,
    )
    contract_value = models.DecimalField(
        "مبلغ قرارداد",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    signed_at = models.DateField("تاریخ امضا", null=True, blank=True)
    start_date = models.DateField("تاریخ شروع", null=True, blank=True)
    end_date = models.DateField("تاریخ پایان", null=True, blank=True)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts_updated",
    )
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)

    class Meta:
        verbose_name = "قرارداد"
        verbose_name_plural = "قراردادها"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract_number"],
                name="unique_contract_number_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="contract_org_status_idx",
            ),
            models.Index(
                fields=["organization", "deleted_at"],
                name="contract_org_deleted_idx",
            ),
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.contract_number = canonicalize_upper_identifier(self.contract_number)
        if self.project_id:
            validate_related_organizations(
                self,
                project=self.project,
                party=self.party if self.party_id else None,
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.contract_number = canonicalize_upper_identifier(self.contract_number)
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ContractStatus.ACTIVE,
                ContractStatus.COMPLETED,
                ContractStatus.TERMINATED,
            } and any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "title",
                    "counterparty_name",
                    "party_id",
                    "direction",
                    "contract_type",
                    "contract_value",
                    "notes",
                )
            ):
                raise ValidationError(
                    "شرایط قرارداد نهایی‌شده فقط از طریق الحاقیه قابل تغییر است."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.contract_number} - {self.title}"


class ContractTermVersion(UUIDModel, TimeStampedModel):
    """Immutable approved commercial terms for one receivable or payable contract."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="contract_term_versions",
    )
    contract = models.ForeignKey(
        Contract,
        on_delete=models.PROTECT,
        related_name="term_versions",
    )
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    insurance_classification = models.ForeignKey(
        "organizations.InsuranceClassification",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_term_versions",
        verbose_name="طبقه‌بندی بیمه",
    )
    insurance_classification_selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_insurance_selections",
    )
    payment_due_days = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=ContractTermVersionStatus.choices,
        default=ContractTermVersionStatus.DRAFT,
        db_index=True,
    )
    retention_rate = models.DecimalField(
        max_digits=9, decimal_places=6, default=Decimal(0)
    )
    retention_cap = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    retention_basis = models.CharField(
        max_length=20,
        choices=ContractTermCalculationBasis.choices,
        default=ContractTermCalculationBasis.GROSS,
    )
    advance_recovery_rate = models.DecimalField(
        max_digits=9, decimal_places=6, default=Decimal(0)
    )
    advance_recovery_cap = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    advance_recovery_basis = models.CharField(
        max_length=20,
        choices=ContractTermCalculationBasis.choices,
        default=ContractTermCalculationBasis.GROSS,
    )
    contractual_insurance_rate = models.DecimalField(
        max_digits=9, decimal_places=6, default=Decimal(0)
    )
    contractual_insurance_cap = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    contractual_insurance_basis = models.CharField(
        max_length=20,
        choices=ContractTermCalculationBasis.choices,
        default=ContractTermCalculationBasis.GROSS,
    )
    retention_release_requirement = models.CharField(
        max_length=30,
        choices=RetentionReleaseRequirement.choices,
        default=RetentionReleaseRequirement.UNCONFIGURED,
    )
    retention_release_cap = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contract_term_versions_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_term_versions_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(blank=True)
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseded_versions",
    )

    class Meta:
        ordering = ["contract_id", "-version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "version"],
                name="contract_term_org_contract_version_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_due_days__lte=3650),
                name="contract_term_due_days_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(retention_rate__gte=0)
                    & models.Q(retention_rate__lte=100)
                    & models.Q(advance_recovery_rate__gte=0)
                    & models.Q(advance_recovery_rate__lte=100)
                    & models.Q(contractual_insurance_rate__gte=0)
                    & models.Q(contractual_insurance_rate__lte=100)
                ),
                name="contract_term_rates_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(retention_cap__gte=0)
                    & models.Q(advance_recovery_cap__gte=0)
                    & models.Q(contractual_insurance_cap__gte=0)
                    & models.Q(retention_release_cap__gte=0)
                ),
                name="contract_term_caps_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=ContractTermVersionStatus.DRAFT,
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                    )
                    | models.Q(
                        status__in=(
                            ContractTermVersionStatus.APPROVED,
                            ContractTermVersionStatus.SUPERSEDED,
                        ),
                        approved_by__isnull=False,
                        approved_at__isnull=False,
                    )
                ),
                name="contract_term_approval_state",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.contract_id:
            validate_related_organizations(self, contract=self.contract)
            if self.contract.direction not in {
                ContractDirection.RECEIVABLE,
                ContractDirection.PAYABLE,
            }:
                raise ValidationError("جهت قرارداد برای شرایط تجاری باید مشخص باشد.")
            if (
                self.contract.direction == ContractDirection.PAYABLE
                and self.contract.contract_type != ContractType.SUBCONTRACT
            ):
                raise ValidationError(
                    "شرایط پرداختنی این مرحله فقط برای پیمان جزء است."
                )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل نسخه شرایط قرارداد الزامی است."})
        if (
            self.approved_by_id
            and self.approved_by_id == self.insurance_classification_selected_by_id
        ):
            raise ValidationError(
                "انتخاب‌کننده طبقه‌بندی نمی‌تواند همان نسخه را تأیید کند."
            )
        if self.approved_by_id == self.created_by_id and self.approved_by_id:
            raise ValidationError("تهیه‌کننده نمی‌تواند همان نسخه شرایط را تأیید کند.")
        if self.superseded_by_id:
            if self.superseded_by_id == self.pk:
                raise ValidationError("نسخه شرایط نمی‌تواند جایگزین خود باشد.")
            if self.superseded_by.contract_id != self.contract_id:
                raise ValidationError("نسخه جایگزین باید متعلق به همان قرارداد باشد.")
        if (
            self.retention_release_requirement
            == RetentionReleaseRequirement.UNCONFIGURED
            and self.retention_release_cap != 0
        ):
            raise ValidationError(
                "سقف آزادسازی فقط همراه با اختیار صریح آزادسازی قابل ثبت است."
            )
        if (
            self.retention_release_requirement
            != RetentionReleaseRequirement.UNCONFIGURED
            and (
                self.retention_release_cap <= 0
                or self.retention_release_cap > self.retention_cap
            )
        ):
            raise ValidationError(
                "سقف آزادسازی باید مثبت و حداکثر برابر سقف کسور تضمین باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status != ContractTermVersionStatus.DRAFT:
                immutable = (
                    "organization_id",
                    "contract_id",
                    "version",
                    "effective_from",
                    "payment_due_days",
                    "insurance_classification_id",
                    "insurance_classification_selected_by_id",
                    "retention_rate",
                    "retention_cap",
                    "retention_basis",
                    "advance_recovery_rate",
                    "advance_recovery_cap",
                    "advance_recovery_basis",
                    "contractual_insurance_rate",
                    "contractual_insurance_cap",
                    "contractual_insurance_basis",
                    "retention_release_requirement",
                    "retention_release_cap",
                    "reason",
                    "created_by_id",
                    "approved_by_id",
                    "approved_at",
                    "approval_reason",
                )
                if any(
                    getattr(previous, field) != getattr(self, field)
                    for field in immutable
                ):
                    raise ValidationError(
                        "نسخه تأییدشده شرایط قرارداد تغییرناپذیر است."
                    )
                if previous.status == ContractTermVersionStatus.SUPERSEDED:
                    raise ValidationError(
                        "نسخه جایگزین‌شده شرایط قرارداد قابل تغییر نیست."
                    )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != ContractTermVersionStatus.DRAFT:
            raise ValidationError("نسخه تأییدشده شرایط قرارداد قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class ContractItem(UUIDModel, TimeStampedModel):
    """A draft commercial line; header value remains authoritative in R7."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="contract_items",
    )
    contract = models.ForeignKey(
        Contract, verbose_name="قرارداد", on_delete=models.CASCADE, related_name="items"
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        verbose_name="گره ساختار شکست کار",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contract_items",
    )
    description = models.CharField("شرح ردیف", max_length=255)
    quantity = models.DecimalField("مقدار", max_digits=18, decimal_places=4)
    unit = models.CharField("واحد قدیمی", max_length=30, default="unit")
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contract_items",
    )
    unit_price = models.DecimalField("قیمت واحد", max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)

    class Meta:
        verbose_name = "ردیف قرارداد"
        verbose_name_plural = "ردیف‌های قرارداد"
        ordering = ["sort_order", "created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract"], name="contract_item_org_ct_idx"
            )
        ]

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def clean(self) -> None:
        super().clean()
        relations = {"contract": self.contract} if self.contract_id else {}
        if self.wbs_node_id:
            relations["wbs_node"] = self.wbs_node
        if self.unit_of_measure_id:
            relations["unit_of_measure"] = self.unit_of_measure
        validate_related_organizations(self, **relations)
        if self.wbs_node_id and self.wbs_node.project_id != self.contract.project_id:
            raise ValidationError(
                {"wbs_node": "گره ساختار شکست باید متعلق به پروژه قرارداد باشد."}
            )
        if self.unit_of_measure_id and (
            not self.unit_of_measure.is_active or self.unit_of_measure.archived_at
        ):
            raise ValidationError(
                {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ContractAmendment(UUIDModel, TimeStampedModel):
    """An approved, immutable adjustment to a finalized contract's terms."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="contract_amendments",
    )
    contract = models.ForeignKey(
        Contract,
        verbose_name="قرارداد",
        on_delete=models.CASCADE,
        related_name="amendments",
    )
    amendment_number = models.PositiveIntegerField("شماره الحاقیه")
    title = models.CharField("عنوان الحاقیه", max_length=255)
    reason = models.TextField("دلیل")
    value_change = models.DecimalField(
        "تغییر مبلغ", max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ContractAmendmentStatus.choices,
        default=ContractAmendmentStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_amendments_approved",
    )
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_amendments_created",
    )

    class Meta:
        verbose_name = "الحاقیه قرارداد"
        verbose_name_plural = "الحاقیه‌های قرارداد"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["contract", "amendment_number"],
                name="unique_amendment_number_per_contract",
            )
        ]
        ordering = ["amendment_number"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.contract_id:
            validate_related_organizations(self, contract=self.contract)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status == ContractAmendmentStatus.APPROVED:
                raise ValidationError("الحاقیه تأییدشده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ContractualRecord(UUIDModel, TimeStampedModel):
    """Versioned contractual decision evidence with no downstream side effects."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="contractual_records",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="contractual_records"
    )
    contract = models.ForeignKey(
        Contract, on_delete=models.PROTECT, related_name="contractual_records"
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="contractual_records",
    )
    kind = models.CharField(max_length=24, choices=ContractualRecordKind.choices)
    record_number = models.CharField(max_length=80)
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    revision_action = models.CharField(
        max_length=16,
        choices=ContractualRevisionAction.choices,
        default=ContractualRevisionAction.ORIGINAL,
    )
    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseding_record",
    )
    revision_reason = models.TextField(blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    notice_reference = models.CharField(max_length=160, blank=True)
    notice_date = models.DateField(null=True, blank=True)
    requested_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    requested_eot_days = models.PositiveIntegerField(null=True, blank=True)
    valuation_assumptions = models.TextField(blank=True)
    cost_impact_assumptions = models.TextField(blank=True)
    schedule_impact_assumptions = models.TextField(blank=True)
    contract_value_impact_assumptions = models.TextField(blank=True)
    linked_amendment = models.ForeignKey(
        ContractAmendment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractual_records",
    )
    status = models.CharField(
        max_length=16,
        choices=ContractualRecordStatus.choices,
        default=ContractualRecordStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractual_records_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractual_records_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(blank=True)
    entitlement_approved = models.BooleanField(null=True, blank=True)
    approved_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    approved_eot_days = models.PositiveIntegerField(null=True, blank=True)
    approved_delay_responsibility = models.TextField(blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractual_records_returned",
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True)
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractual_records_withdrawn",
    )
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contractual_records_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contractual_records_updated",
    )
    idempotency_key = models.CharField(max_length=120)

    class Meta:
        ordering = ["contract_id", "kind", "record_number", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="contractual_record_org_idempotency_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "series_id", "version"],
                name="contractual_record_series_version_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_amount__isnull=True)
                | models.Q(requested_amount__gte=0),
                name="contractual_requested_amount_nonnegative_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(approved_amount__isnull=True)
                | models.Q(approved_amount__gte=0),
                name="contractual_approved_amount_nonnegative_ck",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "contract", "status"],
                name="contractual_scope_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            party_identity_snapshot=self.party_identity_snapshot,
            supersedes=self.supersedes if self.supersedes_id else None,
            linked_amendment=self.linked_amendment
            if self.linked_amendment_id
            else None,
        )
        if self.contract.project_id != self.project_id:
            raise ValidationError(
                "رکورد قراردادی باید به پروژه قرارداد تعلق داشته باشد."
            )
        if self.contract.party_id != self.party_identity_snapshot.party_id:
            raise ValidationError("تصویر هویت طرف باید متعلق به طرف قرارداد باشد.")
        if (
            self.linked_amendment_id
            and self.linked_amendment.contract_id != self.contract_id
        ):
            raise ValidationError("الحاقیه مرجع باید متعلق به همین قرارداد باشد.")
        if self.supersedes_id:
            if (
                self.supersedes.contract_id != self.contract_id
                or self.supersedes.kind != self.kind
                or self.supersedes.series_id != self.series_id
                or self.version != self.supersedes.version + 1
                or self.revision_action == ContractualRevisionAction.ORIGINAL
            ):
                raise ValidationError("زنجیره نسخه قراردادی معتبر نیست.")
        elif (
            self.version != 1
            or self.revision_action != ContractualRevisionAction.ORIGINAL
        ):
            raise ValidationError("نسخه نخست باید رکورد اصلی باشد.")
        if (
            self.revision_action != ContractualRevisionAction.ORIGINAL
            and not self.revision_reason.strip()
        ):
            raise ValidationError("دلیل اصلاح یا ابطال الزامی است.")
        if not all(
            (self.record_number.strip(), self.title.strip(), self.description.strip())
        ):
            raise ValidationError("شماره، عنوان و شرح رکورد قراردادی الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ContractualRecordStatus.APPROVED,
                ContractualRecordStatus.RETURNED,
                ContractualRecordStatus.WITHDRAWN,
                ContractualRecordStatus.SUPERSEDED,
                ContractualRecordStatus.CANCELLED,
            }:
                permitted = {"status", "updated_by_id", "updated_at"}
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError(
                        "تاریخچه نهایی رکورد قراردادی تغییرناپذیر است."
                    )
            elif previous.status == ContractualRecordStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "approval_reason",
                    "entitlement_approved",
                    "approved_amount",
                    "approved_eot_days",
                    "approved_delay_responsibility",
                    "returned_by_id",
                    "returned_at",
                    "return_reason",
                    "withdrawn_by_id",
                    "withdrawn_at",
                    "withdrawal_reason",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError("تصویر رکورد ارسال‌شده قابل ویرایش نیست.")
        self.record_number = canonicalize_upper_identifier(self.record_number)
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError(
            "رکورد قراردادی باید با تاریخچه نگهداری شود و حذف‌پذیر نیست."
        )


class ContractualRecordEvidence(UUIDModel, TimeStampedModel):
    """Append-only typed reference to existing authoritative evidence."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    record = models.ForeignKey(
        ContractualRecord, on_delete=models.PROTECT, related_name="evidence_links"
    )
    label = models.CharField(max_length=255)
    document_version = models.ForeignKey(
        "documents.DocumentVersion", null=True, blank=True, on_delete=models.PROTECT
    )
    project_control_item = models.ForeignKey(
        "projects.ProjectControlItem", null=True, blank=True, on_delete=models.PROTECT
    )
    project_change_proposal = models.ForeignKey(
        "projects.ProjectChangeProposal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    schedule_revision = models.ForeignKey(
        "projects.ProjectScheduleRevision",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    progress_record = models.ForeignKey(
        "billing.ProgressRecord", null=True, blank=True, on_delete=models.PROTECT
    )
    payable_measurement = models.ForeignKey(
        "billing.PayableMeasurement", null=True, blank=True, on_delete=models.PROTECT
    )
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=(
                    models.Q(document_version__isnull=False)
                    | models.Q(project_control_item__isnull=False)
                    | models.Q(project_change_proposal__isnull=False)
                    | models.Q(schedule_revision__isnull=False)
                    | models.Q(progress_record__isnull=False)
                    | models.Q(payable_measurement__isnull=False)
                ),
                name="contractual_evidence_source_present_ck",
            )
        ]

    def clean(self) -> None:
        super().clean()
        names = (
            "document_version",
            "project_control_item",
            "project_change_proposal",
            "schedule_revision",
            "progress_record",
            "payable_measurement",
        )
        sources = [getattr(self, name) for name in names]
        if sum(source is not None for source in sources) != 1:
            raise ValidationError("هر پیوند شواهد باید دقیقاً یک منبع داشته باشد.")
        validate_related_organizations(
            self,
            record=self.record,
            **{
                name: value
                for name, value in zip(names, sources, strict=True)
                if value is not None
            },
        )
        for source in sources[1:]:
            if source is not None and source.project_id != self.record.project_id:
                raise ValidationError("شواهد عملیاتی باید متعلق به پروژه رکورد باشد.")
        if self.progress_record_id and self.progress_record.status != "verified":
            raise ValidationError("فقط پیشرفت راستی‌آزمایی‌شده قابل استناد است.")
        if (
            self.payable_measurement_id
            and self.payable_measurement.status != "verified"
        ):
            raise ValidationError(
                "فقط اندازه‌گیری پرداختنی راستی‌آزمایی‌شده قابل استناد است."
            )
        if self.record.status != ContractualRecordStatus.DRAFT:
            raise ValidationError("شواهد فقط به نسخه پیش‌نویس افزوده می‌شود.")
        if not self.label.strip():
            raise ValidationError("عنوان پیوند شواهد الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("پیوند شواهد تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("پیوند شواهد حذف‌پذیر نیست.")
