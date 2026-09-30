from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from core.identifiers import (
    canonicalize_lower_identifier,
    canonicalize_party_identity_value,
)
from core.models import TimeStampedModel, UUIDModel


class PartyKind(models.TextChoices):
    COMPANY = "company", "شخص حقوقی"
    INDIVIDUAL = "individual", "شخص حقیقی"


class PartyRoleType(models.TextChoices):
    EMPLOYER = "employer", "کارفرما"
    CLIENT = "client", "مشتری"
    CONSULTANT = "consultant", "مشاور"
    SUPPLIER = "supplier", "تأمین‌کننده"
    SUBCONTRACTOR = "subcontractor", "پیمانکار جزء"
    OTHER = "other", "سایر"


class ContactType(models.TextChoices):
    EMAIL = "email", "ایمیل"
    PHONE = "phone", "تلفن"
    MOBILE = "mobile", "تلفن همراه"
    ADDRESS = "address", "نشانی"
    OTHER = "other", "سایر"


class PartyRestrictionScope(models.TextChoices):
    TENANT = "tenant", "Tenant"
    PLATFORM = "platform", "پلتفرم"


class PartyRestrictionEffect(models.TextChoices):
    INFORMATION_ONLY = "information_only", "صرفاً اطلاع‌رسانی"
    BLOCK_NEW_TRANSACTIONS = "block_new_transactions", "مسدودسازی تراکنش جدید"


class PartyAliasType(models.TextChoices):
    DISPLAY_NAME = "display_name", "نام نمایشی"
    LEGAL_NAME = "legal_name", "نام قانونی"
    IDENTIFIER = "identifier", "شناسه"
    OTHER = "other", "سایر"


class PartyClassificationKind(models.TextChoices):
    CATEGORY = "category", "دسته"
    TAG = "tag", "برچسب"


class PartyRepresentativeAuthority(models.TextChoices):
    REPRESENTATIVE = "representative", "نماینده مجاز"
    SIGNATORY = "signatory", "امضادار مجاز"


class BusinessParty(UUIDModel, TimeStampedModel):
    """A tenant-owned counterparty, independent of current transaction text."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="business_parties",
    )
    party_kind = models.CharField(
        "نوع طرف تجاری", max_length=20, choices=PartyKind.choices
    )
    display_name = models.CharField("نام نمایشی", max_length=255)
    legal_name = models.CharField("نام قانونی", max_length=255, blank=True)
    tax_identifier = models.CharField("شناسه مالیاتی", max_length=100, blank=True)
    normalized_display_name = models.CharField(
        "نام نمایشی نرمال‌شده",
        max_length=255,
        editable=False,
        db_index=True,
        blank=True,
        default="",
    )
    normalized_legal_name = models.CharField(
        "نام قانونی نرمال‌شده",
        max_length=255,
        blank=True,
        editable=False,
        db_index=True,
        default="",
    )
    normalized_tax_identifier = models.CharField(
        "شناسه نرمال‌شده",
        max_length=100,
        blank=True,
        editable=False,
        db_index=True,
        default="",
    )
    merged_into = models.ForeignKey(
        "self",
        verbose_name="طرف تجاری مرجع پس از ادغام",
        on_delete=models.PROTECT,
        related_name="merged_sources",
        null=True,
        blank=True,
    )
    merged_at = models.DateTimeField("زمان ثبت ادغام", null=True, blank=True)
    merged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده ادغام",
        on_delete=models.PROTECT,
        related_name="business_party_merges_recorded",
        null=True,
        blank=True,
    )
    merge_reason = models.TextField("دلیل ادغام", blank=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_parties_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_parties_updated",
    )

    class Meta:
        verbose_name = "طرف تجاری"
        verbose_name_plural = "طرف‌های تجاری"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "normalized_tax_identifier"],
                condition=~Q(normalized_tax_identifier="")
                & Q(merged_into__isnull=True),
                name="unique_party_normalized_identifier_per_org",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        merged_into__isnull=True,
                        merged_at__isnull=True,
                        merged_by__isnull=True,
                        merge_reason="",
                    )
                    | Q(
                        merged_into__isnull=False,
                        merged_at__isnull=False,
                        merged_by__isnull=False,
                        merge_reason__gt="",
                    )
                ),
                name="party_merge_evidence_complete",
            ),
            models.CheckConstraint(
                condition=~Q(id=F("merged_into")),
                name="party_cannot_merge_into_self",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "display_name"],
                name="party_org_name_idx",
            ),
            models.Index(
                fields=["organization", "archived_at"],
                name="party_org_archived_idx",
            ),
        ]
        ordering = ["display_name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if not self.display_name.strip():
            raise ValidationError({"display_name": "وارد کردن نام نمایشی الزامی است."})
        if self.merged_into_id:
            if self.organization_id != self.merged_into.organization_id:
                raise ValidationError(
                    "طرف‌های تجاری ادغام‌شده باید متعلق به یک سازمان باشند."
                )
            if self.merged_into.merged_into_id:
                raise ValidationError("زنجیره ادغام طرف تجاری مجاز نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.normalized_display_name = canonicalize_party_identity_value(
            self.display_name
        )
        self.normalized_legal_name = canonicalize_party_identity_value(self.legal_name)
        self.normalized_tax_identifier = canonicalize_party_identity_value(
            self.tax_identifier
        )
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).first()
            if (
                previous
                and previous.merged_into_id
                and any(
                    getattr(previous, field) != getattr(self, field)
                    for field in (
                        "merged_into_id",
                        "merged_at",
                        "merged_by_id",
                        "merge_reason",
                    )
                )
            ):
                raise ValidationError("سابقه ادغام طرف تجاری تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.display_name


class PartyIdentitySnapshot(UUIDModel):
    """Append-only identity evidence for one tenant-owned party."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.PROTECT,
        related_name="party_identity_snapshots",
    )
    party = models.ForeignKey(
        BusinessParty,
        verbose_name="طرف تجاری",
        on_delete=models.PROTECT,
        related_name="identity_snapshots",
    )
    sequence = models.PositiveIntegerField("شماره نسخه")
    party_kind = models.CharField(
        "نوع طرف تجاری", max_length=20, choices=PartyKind.choices
    )
    display_name = models.CharField("نام نمایشی", max_length=255)
    legal_name = models.CharField("نام قانونی", max_length=255, blank=True)
    tax_identifier = models.CharField("شناسه مالیاتی", max_length=100, blank=True)
    normalized_display_name = models.CharField("نام نمایشی نرمال‌شده", max_length=255)
    normalized_legal_name = models.CharField(
        "نام قانونی نرمال‌شده", max_length=255, blank=True
    )
    normalized_tax_identifier = models.CharField(
        "شناسه نرمال‌شده", max_length=100, blank=True
    )
    reason = models.TextField("دلیل ثبت")
    recorded_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.PROTECT,
        related_name="party_identity_snapshots_recorded",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "نسخه هویت طرف تجاری"
        verbose_name_plural = "نسخه‌های هویت طرف تجاری"
        ordering = ["party", "sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["party", "sequence"], name="unique_party_identity_sequence"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError(
                "نسخه هویت و طرف تجاری باید متعلق به یک سازمان باشند."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("نسخه هویت طرف تجاری تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("نسخه هویت طرف تجاری قابل حذف نیست.")


class PartyRestriction(UUIDModel, TimeStampedModel):
    """Generic, explicit restriction in one party context."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.PROTECT,
        related_name="party_restrictions",
    )
    party = models.ForeignKey(
        BusinessParty,
        verbose_name="طرف تجاری",
        on_delete=models.PROTECT,
        related_name="restrictions",
    )
    scope = models.CharField(
        "دامنه", max_length=20, choices=PartyRestrictionScope.choices
    )
    code = models.CharField("کد محدودیت", max_length=80)
    effect = models.CharField(
        "اثر", max_length=40, choices=PartyRestrictionEffect.choices
    )
    reason = models.TextField("دلیل")
    effective_from = models.DateTimeField("شروع اثر")
    effective_until = models.DateTimeField("پایان اثر", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.PROTECT,
        related_name="party_restrictions_created",
    )
    revoked_at = models.DateTimeField("زمان لغو", null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="لغوکننده",
        on_delete=models.PROTECT,
        related_name="party_restrictions_revoked",
        null=True,
        blank=True,
    )
    revocation_reason = models.TextField("دلیل لغو", blank=True)

    class Meta:
        verbose_name = "محدودیت طرف تجاری"
        verbose_name_plural = "محدودیت‌های طرف تجاری"
        ordering = ["party", "scope", "code", "-effective_from"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "party", "scope", "effect"],
                name="party_restriction_lookup_idx",
            ),
        ]
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=F("effective_from")),
                name="party_restriction_effective_interval",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        revoked_at__isnull=True,
                        revoked_by__isnull=True,
                        revocation_reason="",
                    )
                    | Q(
                        revoked_at__isnull=False,
                        revoked_by__isnull=False,
                        revocation_reason__gt="",
                    )
                ),
                name="party_restriction_revocation_evidence",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_lower_identifier(self.code)
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError("محدودیت و طرف تجاری باید متعلق به یک سازمان باشند.")
        if not self.code:
            raise ValidationError({"code": "کد محدودیت الزامی است."})
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل محدودیت الزامی است."})
        if self.effective_until and self.effective_until <= self.effective_from:
            raise ValidationError(
                {"effective_until": "پایان اثر باید پس از شروع باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        self.full_clean()
        super().save(*args, **kwargs)


class PartyRole(UUIDModel, TimeStampedModel):
    """A party's permitted business role within the same tenant."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="party_roles",
    )
    party = models.ForeignKey(
        BusinessParty,
        verbose_name="طرف تجاری",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    role = models.CharField("نقش", max_length=20, choices=PartyRoleType.choices)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "نقش طرف تجاری"
        verbose_name_plural = "نقش‌های طرف تجاری"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "party", "role"],
                name="unique_party_role_per_organization",
            ),
        ]
        ordering = ["role"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError("طرف تجاری و نقش باید متعلق به یک سازمان باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.party} - {self.get_role_display()}"


class PartyContact(UUIDModel, TimeStampedModel):
    """A tenant-owned contact channel for a business party."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="party_contacts",
    )
    party = models.ForeignKey(
        BusinessParty,
        verbose_name="طرف تجاری",
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    contact_type = models.CharField(
        "نوع راه ارتباطی", max_length=20, choices=ContactType.choices
    )
    value = models.CharField("مقدار", max_length=255)
    label = models.CharField("عنوان", max_length=100, blank=True)
    is_primary = models.BooleanField("راه ارتباطی اصلی", default=False)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)

    class Meta:
        verbose_name = "راه ارتباطی طرف تجاری"
        verbose_name_plural = "راه‌های ارتباطی طرف تجاری"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "party", "contact_type", "value"],
                name="unique_party_contact_value_per_organization",
            ),
            models.UniqueConstraint(
                fields=["party"],
                condition=Q(is_primary=True, archived_at__isnull=True),
                name="unique_active_primary_contact_per_party",
            ),
        ]
        ordering = ["-is_primary", "contact_type", "value"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError(
                "طرف تجاری و راه ارتباطی باید متعلق به یک سازمان باشند."
            )
        if not self.value.strip():
            raise ValidationError({"value": "وارد کردن مقدار راه ارتباطی الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.party} - {self.value}"


class PartyAlias(UUIDModel, TimeStampedModel):
    """Append-only tenant-local alternate identity evidence."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="party_aliases",
    )
    party = models.ForeignKey(
        BusinessParty, on_delete=models.PROTECT, related_name="aliases"
    )
    alias_type = models.CharField(max_length=20, choices=PartyAliasType.choices)
    value = models.CharField(max_length=255)
    normalized_value = models.CharField(max_length=255, editable=False, db_index=True)
    reason = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="party_aliases_recorded",
    )

    class Meta:
        ordering = ["party", "alias_type", "value"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "party", "alias_type", "normalized_value"],
                name="unique_party_alias_evidence",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "alias_type", "normalized_value"],
                name="party_alias_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError(
                "نام مستعار و طرف تجاری باید متعلق به یک سازمان باشند."
            )
        if not self.normalized_value:
            raise ValidationError({"value": "مقدار نام مستعار الزامی است."})
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل ثبت نام مستعار الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("سابقه نام مستعار تغییرپذیر نیست.")
        self.value = self.value.strip()
        self.normalized_value = canonicalize_party_identity_value(self.value)
        self.reason = self.reason.strip()
        self.full_clean()
        super().save(*args, **kwargs)


class PartyClassification(UUIDModel, TimeStampedModel):
    """Tenant-owned category or tag vocabulary for parties."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="party_classifications",
    )
    kind = models.CharField(max_length=20, choices=PartyClassificationKind.choices)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="party_classifications_created",
    )

    class Meta:
        ordering = ["kind", "name"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "kind", "code"],
                name="unique_party_classification_code",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_lower_identifier(self.code)
        if not self.code:
            raise ValidationError({"code": "کد دسته یا برچسب الزامی است."})
        if not self.name.strip():
            raise ValidationError({"name": "نام دسته یا برچسب الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        self.name = self.name.strip()
        self.full_clean()
        super().save(*args, **kwargs)


class PartyClassificationAssignment(UUIDModel, TimeStampedModel):
    """Historical category/tag assignment without destructive removal."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="party_classification_assignments",
    )
    party = models.ForeignKey(
        BusinessParty,
        on_delete=models.PROTECT,
        related_name="classification_assignments",
    )
    classification = models.ForeignKey(
        PartyClassification,
        on_delete=models.PROTECT,
        related_name="party_assignments",
    )
    assigned_at = models.DateTimeField()
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="party_classifications_assigned",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="party_classifications_revoked",
        null=True,
        blank=True,
    )
    revocation_reason = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["party", "classification"],
                condition=Q(revoked_at__isnull=True),
                name="unique_active_party_classification",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        revoked_at__isnull=True,
                        revoked_by__isnull=True,
                        revocation_reason="",
                    )
                    | Q(
                        revoked_at__isnull=False,
                        revoked_by__isnull=False,
                        revocation_reason__gt="",
                    )
                ),
                name="party_classification_revocation_evidence",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError("انتساب و طرف تجاری باید متعلق به یک سازمان باشند.")
        if (
            self.classification_id
            and self.organization_id != self.classification.organization_id
        ):
            raise ValidationError("انتساب و دسته باید متعلق به یک سازمان باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "party_id",
                "classification_id",
                "assigned_at",
                "assigned_by_id",
            )
            if any(
                getattr(original, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError("سابقه انتساب دسته‌بندی تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class PartyRepresentative(UUIDModel, TimeStampedModel):
    """Effective-dated representative/signatory evidence; not a User identity."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="party_representatives",
    )
    party = models.ForeignKey(
        BusinessParty, on_delete=models.PROTECT, related_name="representatives"
    )
    authority = models.CharField(
        max_length=20, choices=PartyRepresentativeAuthority.choices
    )
    full_name = models.CharField(max_length=255)
    title = models.CharField(max_length=120, blank=True)
    evidence_reference = models.CharField(max_length=255)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="party_representatives_recorded",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="party_representatives_revoked",
        null=True,
        blank=True,
    )
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["party", "authority", "full_name"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "party", "authority", "effective_from"],
                name="party_rep_lookup_idx",
            )
        ]
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=F("effective_from")),
                name="party_representative_interval",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        revoked_at__isnull=True,
                        revoked_by__isnull=True,
                        revocation_reason="",
                    )
                    | Q(
                        revoked_at__isnull=False,
                        revoked_by__isnull=False,
                        revocation_reason__gt="",
                    )
                ),
                name="party_representative_revocation_evidence",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.party_id and self.organization_id != self.party.organization_id:
            raise ValidationError("نماینده و طرف تجاری باید متعلق به یک سازمان باشند.")
        if not self.full_name.strip():
            raise ValidationError({"full_name": "نام نماینده الزامی است."})
        if not self.evidence_reference.strip():
            raise ValidationError(
                {"evidence_reference": "مرجع مدرک اختیار الزامی است."}
            )
        if self.effective_until and self.effective_until <= self.effective_from:
            raise ValidationError("پایان اعتبار باید پس از شروع اعتبار باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "party_id",
                "authority",
                "full_name",
                "title",
                "evidence_reference",
                "effective_from",
                "effective_until",
                "recorded_by_id",
            )
            if any(
                getattr(original, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError("سابقه اختیار نماینده تغییرپذیر نیست.")
        self.full_name = self.full_name.strip()
        self.title = self.title.strip()
        self.evidence_reference = self.evidence_reference.strip()
        self.full_clean()
        super().save(*args, **kwargs)
