from apps.organizations.models import BusinessPermissionCode
from apps.organizations.permission_registry import (
    PERMISSION_RESOURCES_BY_KEY,
    registered_permission_codes,
)

PERMISSION_GROUP_LABELS: dict[str, str] = {
    key: resource.label for key, resource in PERMISSION_RESOURCES_BY_KEY.items()
}


def permission_group_label(code: str) -> str:
    """Return the Persian catalog group for a stable permission code."""

    namespace = code.partition(".")[0]
    return PERMISSION_GROUP_LABELS.get(namespace, namespace)


def permission_codes(*permissions: BusinessPermissionCode) -> set[str]:
    """Normalize TextChoices values for role-default declarations."""

    return {str(permission) for permission in permissions}


def permission_codes_with_suffix(suffix: str) -> set[str]:
    """Return catalog codes for one operation, such as all view permissions."""

    return {
        code for code in registered_permission_codes() if code.endswith(f".{suffix}")
    }
