from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from apps.reporting.catalog import GOVERNANCE_REFERENCE, METRIC_SPECS
from apps.reporting.project_closeout_catalog import (
    PROJECT_CLOSEOUT_FAMILIES,
    PROJECT_CLOSEOUT_GOVERNANCE_REFERENCE,
    PROJECT_CLOSEOUT_PROFILE_CODE,
)
from apps.reporting.reconciliation_catalog import (
    RECONCILIATION_GOVERNANCE_REFERENCE,
    RECONCILIATION_PAIR_SPECS,
)


def synchronize_metric_catalogue(*, using: str, **kwargs: Any) -> None:
    """Restore approved code-owned metric and reconciliation definitions."""

    del kwargs
    connection = connections[using]
    required = {
        "reporting_metricdefinition",
        "reporting_metricdefinitionversion",
    }
    if not required.issubset(connection.introspection.table_names()):
        return

    from apps.reporting.models import MetricDefinition, MetricDefinitionVersion

    with transaction.atomic(using=using):
        for code, spec in METRIC_SPECS.items():
            definition, _ = MetricDefinition.objects.using(using).get_or_create(
                code=code,
                defaults={
                    "persian_name": spec["persian_name"],
                    "source_domain": spec["source_domain"],
                    "source_permission": spec["source_permission"],
                    "sensitivity": "normal",
                    "drillthrough_route_name": spec["drillthrough"],
                    "metric_owner": "Product Owner through authoritative owning business domain",
                    "source_owner": spec["source_owner"],
                    "requires_independent_review": spec["requires_review"],
                    "is_active": True,
                },
            )
            specification = {
                "grain": "tenant/project/as_of",
                "formula": spec["formula"],
                "unit": spec["unit"],
                "time_basis": "explicit source cutoff and tenant timezone",
                "missing_input": "unknown_or_incomplete_never_zero",
                "late_correction": "linked_replacement_refresh",
                "drillthrough": spec["drillthrough"],
                "source_permission": spec["source_permission"],
            }
            payload_hash = hashlib.sha256(
                json.dumps(
                    specification,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            MetricDefinitionVersion.objects.using(using).get_or_create(
                definition=definition,
                version=1,
                defaults={
                    "status": "published",
                    "specification": specification,
                    "payload_hash": payload_hash,
                    "governance_reference": GOVERNANCE_REFERENCE,
                    "published_at": timezone.now(),
                },
            )

        reconciliation_tables = {
            "reporting_reconciliationpairdefinition",
            "reporting_reconciliationpairversion",
        }
        if not reconciliation_tables.issubset(connection.introspection.table_names()):
            return

        from apps.reporting.models import (
            ReconciliationPairDefinition,
            ReconciliationPairVersion,
        )

        for code, spec in RECONCILIATION_PAIR_SPECS.items():
            definition, _ = ReconciliationPairDefinition.objects.using(
                using
            ).get_or_create(
                code=code,
                defaults={
                    "persian_name": spec["persian_name"],
                    "left_authority": spec["left_authority"],
                    "right_authority": spec["right_authority"],
                    "sensitivity": spec.get("sensitivity", "normal"),
                    "requires_independent_review": True,
                    "is_active": True,
                },
            )
            specification = {
                "adapter": spec["adapter"],
                "grain": spec["grain"],
                "measure": spec["measure"],
                "source_permissions": spec["source_permissions"],
                "tolerance": spec["tolerance"],
                "materiality": spec["materiality"],
                "missing_input": "unknown_or_incomplete_never_zero",
                "rebuild": "immutable_replay_or_linked_successor",
                "downstream_effect": "none",
            }
            payload_hash = hashlib.sha256(
                json.dumps(
                    specification,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            ReconciliationPairVersion.objects.using(using).get_or_create(
                definition=definition,
                version=1,
                defaults={
                    "status": "published",
                    "specification": specification,
                    "source_owner_approvals": spec.get(
                        "source_owner_approvals",
                        {
                            "left": spec["left_authority"],
                            "right": spec["right_authority"],
                            "reconciliation_owner": "Reporting/Reconciliation",
                            "acceptance_owner": "Product Owner",
                        },
                    ),
                    "payload_hash": payload_hash,
                    "governance_reference": spec.get(
                        "governance_reference", RECONCILIATION_GOVERNANCE_REFERENCE
                    ),
                    "published_at": timezone.now(),
                },
            )

        closeout_tables = {
            "reporting_projectcloseoutprofiledefinition",
            "reporting_projectcloseoutprofileversion",
        }
        if not closeout_tables.issubset(connection.introspection.table_names()):
            return

        from apps.reporting.models import (
            ProjectCloseoutProfileDefinition,
            ProjectCloseoutProfileVersion,
        )

        definition, _ = ProjectCloseoutProfileDefinition.objects.using(
            using
        ).get_or_create(
            code=PROJECT_CLOSEOUT_PROFILE_CODE,
            defaults={
                "persian_name": "کنترل هماهنگ اختتام پروژه",
                "is_active": True,
            },
        )
        specification = {
            "families": {
                code: {
                    "persian_name": spec["persian_name"],
                    "authority": spec["authority"],
                    "models": spec["models"],
                    "permissions": spec["permissions"],
                    "sensitivity": spec["sensitivity"],
                    "empty_outcome": spec.get("empty_outcome", "unknown"),
                }
                for code, spec in PROJECT_CLOSEOUT_FAMILIES.items()
            },
            "execution": "explicit_synchronous",
            "missing_input": "explicit_never_zero_or_complete",
            "correction": "immutable_successor",
            "downstream_effect": "none",
        }
        payload_hash = hashlib.sha256(
            json.dumps(
                specification,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        ProjectCloseoutProfileVersion.objects.using(using).get_or_create(
            definition=definition,
            version=1,
            defaults={
                "status": "published",
                "specification": specification,
                "source_owner_approvals": {
                    code: spec["authority"]
                    for code, spec in PROJECT_CLOSEOUT_FAMILIES.items()
                }
                | {
                    "control_owner": "Reporting",
                    "acceptance_owner": "Product Owner",
                },
                "payload_hash": payload_hash,
                "governance_reference": PROJECT_CLOSEOUT_GOVERNANCE_REFERENCE,
                "published_at": timezone.now(),
            },
        )
