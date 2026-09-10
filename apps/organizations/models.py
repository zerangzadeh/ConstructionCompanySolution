from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.identifiers import canonicalize_lower_identifier
from core.models import TimeStampedModel, UUIDModel


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    CANCELLED = "cancelled", "لغوشده"
    ARCHIVED = "archived", "بایگانی‌شده"


class MembershipRole(models.TextChoices):
    OWNER = "owner", "مالک"
    ADMIN = "admin", "مدیر"
    MANAGER = "manager", "مدیر اجرایی"
    MEMBER = "member", "عضو"
    VIEWER = "viewer", "مشاهده‌گر"


class MembershipStatus(models.TextChoices):
    INVITED = "invited", "دعوت‌شده"
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    REVOKED = "revoked", "لغوشده"


class InvitationRole(models.TextChoices):
    ADMIN = "admin", "مدیر"
    MANAGER = "manager", "مدیر اجرایی"
    MEMBER = "member", "عضو"
    VIEWER = "viewer", "مشاهده‌گر"


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "در انتظار"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    EXPIRED = "expired", "منقضی‌شده"
    REVOKED = "revoked", "لغوشده"


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
        "نقش",
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
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
        "نقش",
        max_length=20,
        choices=InvitationRole.choices,
        default=InvitationRole.MEMBER,
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

    def __str__(self) -> str:
        return f"دعوت‌نامه {self.organization.name} برای {self.invitee.username}"
