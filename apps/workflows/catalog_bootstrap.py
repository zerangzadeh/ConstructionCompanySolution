"""Idempotent bootstrap for code-owned workflow reference data."""

from __future__ import annotations

from typing import Any

from django.db import connections, transaction


def synchronize_workflow_catalog(*, using: str, **kwargs: Any) -> None:
    """Restore registered workflow types after migrate or a Django flush.

    Workflow types are system-owned reference data.  The runtime registry is
    their canonical contract; historical data migrations retain the localized
    presentation fields that existed when each type was introduced.
    """

    del kwargs
    connection = connections[using]
    if "workflows_workflowtype" not in connection.introspection.table_names():
        return

    from apps.workflows.models import WorkflowType
    from apps.workflows.registry import registry

    with transaction.atomic(using=using):
        for specification in registry.workflow_types.values():
            workflow_type, _ = WorkflowType.objects.using(using).get_or_create(
                code=specification.code,
                defaults={
                    "name": specification.code,
                    "description": "",
                    "subject_type": specification.subject_type,
                    "subject_adapter": specification.subject_adapter,
                    "allowed_scope_fields": sorted(specification.allowed_scope_fields),
                    "is_active": True,
                },
            )
            WorkflowType.objects.using(using).filter(pk=workflow_type.pk).update(
                subject_type=specification.subject_type,
                subject_adapter=specification.subject_adapter,
                allowed_scope_fields=sorted(specification.allowed_scope_fields),
                is_active=True,
            )
