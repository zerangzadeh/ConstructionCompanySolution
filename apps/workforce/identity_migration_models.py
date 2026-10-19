"""Immutable reconciliation evidence for CEP-029 identity conversion."""

# Django Meta collections describe the schema.
# ruff: noqa: RUF012

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel


class IdentityMigrationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Identity migration evidence is append-only.")

    def delete(self):
        raise ValidationError("Identity migration evidence cannot be deleted.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("Migration evidence requires individual validation.")


class EmployeeIdentityMigration(UUIDModel, CreatedAtModel):
    objects = models.Manager.from_queryset(IdentityMigrationQuerySet)()
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_key = models.CharField(max_length=180)
    process_version = models.PositiveSmallIntegerField()
    source_fingerprint = models.CharField(max_length=64)
    input_fingerprint = models.CharField(max_length=64)
    result = models.JSONField()
    reason = models.TextField(max_length=2000)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_key"],
                name="workforce_identity_run_key_uq",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Identity migration evidence is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Identity migration evidence cannot be deleted.")
