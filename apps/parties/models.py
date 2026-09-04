from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel, UUIDModel


class PartyKind(models.TextChoices):
    COMPANY = "company", "Company"
    INDIVIDUAL = "individual", "Individual"


class PartyRoleType(models.TextChoices):
    EMPLOYER = "employer", "Employer"
    CLIENT = "client", "Client"
    CONSULTANT = "consultant", "Consultant"
    SUPPLIER = "supplier", "Supplier"
    SUBCONTRACTOR = "subcontractor", "Subcontractor"
    OTHER = "other", "Other"


class ContactType(models.TextChoices):
    EMAIL = "email", "Email"
    PHONE = "phone", "Phone"
    MOBILE = "mobile", "Mobile"
    ADDRESS = "address", "Address"
    OTHER = "other", "Other"


class BusinessParty(UUIDModel, TimeStampedModel):
    """A tenant-owned counterparty, independent of current transaction text."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="business_parties",
    )
    party_kind = models.CharField(max_length=20, choices=PartyKind.choices)
    display_name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    tax_identifier = models.CharField(max_length=100, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_parties_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_parties_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "tax_identifier"],
                condition=~Q(tax_identifier=""),
                name="unique_party_tax_identifier_per_organization",
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
            raise ValidationError({"display_name": "Display name is required."})

    def __str__(self) -> str:
        return self.display_name


class PartyRole(UUIDModel, TimeStampedModel):
    """A party's permitted business role within the same tenant."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="party_roles",
    )
    party = models.ForeignKey(
        BusinessParty,
        on_delete=models.CASCADE,
        related_name="roles",
    )
    role = models.CharField(max_length=20, choices=PartyRoleType.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
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
            raise ValidationError(
                "Party and role must belong to the same organization."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.party} - {self.role}"


class PartyContact(UUIDModel, TimeStampedModel):
    """A tenant-owned contact channel for a business party."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="party_contacts",
    )
    party = models.ForeignKey(
        BusinessParty,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    contact_type = models.CharField(max_length=20, choices=ContactType.choices)
    value = models.CharField(max_length=255)
    label = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
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
                "Party and contact must belong to the same organization."
            )
        if not self.value.strip():
            raise ValidationError({"value": "Contact value is required."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.party} - {self.value}"
