from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.identifiers import canonicalize_lower_identifier
from core.models import TimeStampedModel, UUIDModel


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    CANCELLED = "cancelled", "Cancelled"
    ARCHIVED = "archived", "Archived"


class MembershipRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class MembershipStatus(models.TextChoices):
    INVITED = "invited", "Invited"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REVOKED = "revoked", "Revoked"


class InvitationRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"


class Organization(UUIDModel, TimeStampedModel):
    """A construction company tenant."""

    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    timezone = models.CharField(max_length=64, default="UTC")
    currency = models.CharField(max_length=3, default="USD")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_updated",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
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
        on_delete=models.CASCADE,
        related_name="settings",
    )
    timezone = models.CharField(max_length=64, default="UTC")
    currency = models.CharField(
        max_length=3,
        default="USD",
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="Currency must be a three-letter uppercase code.",
            )
        ],
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )

    def __str__(self) -> str:
        return f"Settings for {self.organization.name}"


class OrganizationMembership(UUIDModel, TimeStampedModel):
    """A user's membership and role within an organization."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
    )
    status = models.CharField(
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.INVITED,
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_memberships_invited",
    )

    class Meta:
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
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_invitations",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_invitations_sent",
    )
    role = models.CharField(
        max_length=20,
        choices=InvitationRole.choices,
        default=InvitationRole.MEMBER,
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.organization.name} invitation for {self.invitee.username}"
