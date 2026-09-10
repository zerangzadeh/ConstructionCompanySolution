from typing import Any

from django.core.exceptions import ValidationError


def validate_related_organizations(instance: Any, **relations: Any) -> None:
    """Require each tenant-owned relation to belong to the instance tenant."""

    organization_id = getattr(instance, "organization_id", None)
    if organization_id is None:
        return

    errors = {
        field_name: "رکورد مرتبط باید متعلق به همین سازمان باشد."
        for field_name, related in relations.items()
        if related is not None
        and getattr(related, "organization_id", organization_id) != organization_id
    }
    if errors:
        raise ValidationError(errors)
