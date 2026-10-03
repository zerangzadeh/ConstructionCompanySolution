"""Idempotent bootstrap for the code-owned authorization catalogue."""

from __future__ import annotations

from typing import Any

from django.db import connections, transaction
from django.utils import timezone


def synchronize_authorization_catalog(*, using: str, **kwargs: Any) -> None:
    """Restore code-owned permissions and system roles after migrate or flush.

    Data migrations establish historical schema transitions. This post-migrate
    reconciler owns the repeatable runtime baseline needed after Django flushes
    database rows without replaying those migrations.
    """

    del kwargs
    connection = connections[using]
    required_tables = {
        "organizations_businesspermission",
        "organizations_organizationrole",
        "organizations_protectedoperation",
    }
    if not required_tables.issubset(connection.introspection.table_names()):
        return

    from apps.organizations.models import (
        BusinessPermission,
        BusinessPermissionCode,
        ProtectedOperation,
        ProtectedOperationCode,
    )
    from apps.organizations.role_defaults import (
        DEFAULT_ROLE_METADATA,
        DEFAULT_ROLE_PERMISSIONS,
    )

    with transaction.atomic(using=using):
        permissions: dict[str, BusinessPermission] = {}
        for code in sorted(
            permission_code.value for permission_code in BusinessPermissionCode
        ):
            permission_code = BusinessPermissionCode(code)
            permission, _ = BusinessPermission.objects.using(using).update_or_create(
                code=code,
                defaults={
                    "name": permission_code.label,
                    "description": permission_code.label,
                    "is_active": True,
                },
            )
            permissions[code] = permission

        from apps.organizations.models import OrganizationRole

        for role_code, metadata in DEFAULT_ROLE_METADATA.items():
            role, _ = OrganizationRole.objects.using(using).update_or_create(
                organization=None,
                code=role_code,
                defaults=metadata,
            )
            role.permissions.set(
                permissions[code]
                for code in sorted(DEFAULT_ROLE_PERMISSIONS[role_code])
            )

        for operation_code in ProtectedOperationCode:
            ProtectedOperation.objects.using(using).get_or_create(
                code=operation_code.value,
                version=1,
                defaults={
                    "name": operation_code.label,
                    "description": operation_code.label,
                    "effective_at": timezone.now(),
                    "reason": "Code-owned authorization catalog baseline",
                },
            )
