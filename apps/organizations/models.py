from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_lower_identifier
from core.models import TimeStampedModel, UUIDModel


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    CANCELLED = "cancelled", "لغوشده"
    ARCHIVED = "archived", "بایگانی‌شده"


class MembershipRole(models.TextChoices):
    """Stable codes for the protected roles shipped with the product."""

    COMPANY_OWNER = "company_owner", "مالک شرکت"
    COMPANY_MANAGER = "company_manager", "مدیر شرکت"
    OPERATIONS_MANAGER = "operations_manager", "مدیر اجرایی"
    MEMBER = "member", "عضو"
    VIEWER = "viewer", "مشاهده‌گر"


class MembershipStatus(models.TextChoices):
    INVITED = "invited", "دعوت‌شده"
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    REVOKED = "revoked", "لغوشده"


class InvitationRole(models.TextChoices):
    COMPANY_MANAGER = "company_manager", "مدیر شرکت"
    OPERATIONS_MANAGER = "operations_manager", "مدیر اجرایی"
    MEMBER = "member", "عضو"
    VIEWER = "viewer", "مشاهده‌گر"


class BusinessPermissionCode(models.TextChoices):
    """Business capabilities implemented and enforced by application services."""

    MEMBERSHIP_MANAGE = "membership.manage", "مدیریت اعضای شرکت"
    COMPANY_SETTINGS_MANAGE = "company.settings.manage", "مدیریت تنظیمات شرکت"
    PARTIES_MANAGE = "parties.manage", "مدیریت طرف‌های تجاری"
    MATERIALS_MANAGE = "materials.manage", "مدیریت مصالح و واحدها"
    PROJECTS_MANAGE = "projects.manage", "مدیریت پروژه‌ها"
    CONTRACTS_MANAGE = "contracts.manage", "مدیریت قراردادها"
    ESTIMATES_MANAGE = "estimates.manage", "مدیریت برآوردها"
    ESTIMATES_APPROVE = "estimates.approve", "تأیید برآوردها"
    EXPENSES_MANAGE = "expenses.manage", "مدیریت هزینه‌ها"
    PAYMENTS_MANAGE = "payments.manage", "مدیریت پرداخت‌ها"
    DOCUMENTS_MANAGE = "documents.manage", "مدیریت اسناد"
    DAILY_REPORTS_CREATE = "daily_reports.create", "ثبت گزارش روزانه"
    DAILY_REPORTS_MANAGE = "daily_reports.manage", "مدیریت گزارش‌های روزانه"
    WORKFORCE_MANAGE = "workforce.manage", "مدیریت نیروی انسانی"
    PROCUREMENT_REQUEST = "procurement.request", "ثبت درخواست و دریافت خرید"
    PROCUREMENT_MANAGE = "procurement.manage", "مدیریت و تأیید خرید"
    INVENTORY_MOVEMENT = "inventory.movement", "ثبت گردش انبار"
    INVENTORY_MANAGE = "inventory.manage", "مدیریت انبار"
    AUDIT_VIEW = "audit.view", "مشاهده گزارش رویدادها"


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "در انتظار"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    EXPIRED = "expired", "منقضی‌شده"
    REVOKED = "revoked", "لغوشده"


class BusinessPermission(UUIDModel, TimeStampedModel):
    """A code-owned business capability that can be attached to global roles."""

    code = models.CharField("کد مجوز", max_length=100, unique=True)
    name = models.CharField("عنوان فارسی", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "مجوز کسب‌وکار"
        verbose_name_plural = "مجوزهای کسب‌وکار"
        ordering = ["code"]  # noqa: RUF012

    def __str__(self) -> str:
        return self.name


class OrganizationRole(UUIDModel, TimeStampedModel):
    """A global role assembled by a system administrator from known capabilities."""

    code = models.SlugField("کد نقش", max_length=64, unique=True)
    name = models.CharField("عنوان فارسی", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    permissions = models.ManyToManyField(
        BusinessPermission,
        verbose_name="مجوزهای کسب‌وکار",
        related_name="roles",
        blank=True,
    )
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    is_system = models.BooleanField("نقش سیستمی", default=False)
    is_owner = models.BooleanField("نقش مالک شرکت", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_roles_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_roles_updated",
    )

    class Meta:
        verbose_name = "نقش شرکتی"
        verbose_name_plural = "نقش‌های شرکتی"
        ordering = ["name"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["is_owner"],
                condition=Q(is_owner=True),
                name="unique_company_owner_role",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_lower_identifier(self.code)
        if self.is_owner and (not self.is_system or not self.is_active):
            raise ValidationError("نقش مالک شرکت باید یک نقش سیستمی و فعال باقی بماند.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Organization(UUIDModel, TimeStampedModel):
    """A construction company tenant."""

    name = models.CharField("نام سازمان", max_length=255)
    legal_name = models.CharField("نام قانونی", max_length=255, blank=True)
    slug = models.SlugField("شناسه URL", max_length=255, unique=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    timezone = models.CharField("منطقه زمانی", max_length=64, default="UTC")
    currency = models.CharField("واحد پول", max_length=3, default="USD")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_updated",
    )
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)

    class Meta:
        verbose_name = "سازمان"
        verbose_name_plural = "سازمان‌ها"
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.slug = canonicalize_lower_identifier(self.slug)

    def save(self, *args: object, **kwargs: object) -> None:
        self.slug = canonicalize_lower_identifier(self.slug)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class OrganizationSettings(UUIDModel, TimeStampedModel):
    """Configuration owned by exactly one organization.

    The timezone and currency fields on :class:`Organization` remain during the
    compatibility period. Services keep their values synchronized when settings
    are changed.
    """

    organization = models.OneToOneField(
        Organization,
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="settings",
    )
    timezone = models.CharField("منطقه زمانی", max_length=64, default="UTC")
    currency = models.CharField(
        "واحد پول",
        max_length=3,
        default="USD",
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="واحد پول باید یک کد سه‌حرفی با حروف بزرگ لاتین باشد.",
            )
        ],
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        "ماه شروع سال مالی",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )

    class Meta:
        verbose_name = "تنظیمات سازمان"
        verbose_name_plural = "تنظیمات سازمان‌ها"

    def __str__(self) -> str:
        return f"تنظیمات {self.organization.name}"


class OrganizationMembership(UUIDModel, TimeStampedModel):
    """A user's membership and role within an organization."""

    organization = models.ForeignKey(
        Organization,
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        "کد نقش سازگار",
        max_length=64,
        default=MembershipRole.MEMBER,
        editable=False,
    )
    role_definition = models.ForeignKey(
        OrganizationRole,
        verbose_name="نقش",
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.INVITED,
    )
    joined_at = models.DateTimeField("زمان عضویت", null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="دعوت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_memberships_invited",
    )

    class Meta:
        verbose_name = "عضویت سازمان"
        verbose_name_plural = "عضویت‌های سازمان"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_organization_membership",
            ),
        ]
        ordering = ["organization__name", "user__username"]  # noqa: RUF012

    @property
    def role_label(self) -> str:
        return self.role_definition.name

    def save(self, *args: object, **kwargs: object) -> None:
        if self.role_definition_id is None:
            self.role_definition = OrganizationRole.objects.get(code=self.role)
        self.role = self.role_definition.code
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"role", "role_definition"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.organization.name}"


class OrganizationInvitation(UUIDModel, TimeStampedModel):
    """A time-limited invitation for an existing user to join an organization."""

    organization = models.ForeignKey(
        Organization,
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر دعوت‌شده",
        on_delete=models.CASCADE,
        related_name="organization_invitations",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="دعوت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_invitations_sent",
    )
    role = models.CharField(
        "کد نقش سازگار",
        max_length=64,
        default=InvitationRole.MEMBER,
        editable=False,
    )
    role_definition = models.ForeignKey(
        OrganizationRole,
        verbose_name="نقش",
        on_delete=models.PROTECT,
        related_name="invitations",
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    token_hash = models.CharField("هش توکن", max_length=64, unique=True)
    expires_at = models.DateTimeField("زمان انقضا")
    accepted_at = models.DateTimeField("زمان پذیرش", null=True, blank=True)

    class Meta:
        verbose_name = "دعوت‌نامه سازمان"
        verbose_name_plural = "دعوت‌نامه‌های سازمان"
        ordering = ["-created_at"]  # noqa: RUF012

    @property
    def role_label(self) -> str:
        return self.role_definition.name

    def save(self, *args: object, **kwargs: object) -> None:
        if self.role_definition_id is None:
            self.role_definition = OrganizationRole.objects.get(code=self.role)
        self.role = self.role_definition.code
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"role", "role_definition"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"دعوت‌نامه {self.organization.name} برای {self.invitee.username}"
