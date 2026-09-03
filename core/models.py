"""Abstract model mixins shared by stable business-record patterns."""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Use a non-sequential UUID primary key for public business records."""

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)

    class Meta:
        abstract = True


class CreatedAtModel(models.Model):
    """Record when a business record was first persisted."""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class TimeStampedModel(CreatedAtModel):
    """Record creation and last-update timestamps for mutable records."""

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
