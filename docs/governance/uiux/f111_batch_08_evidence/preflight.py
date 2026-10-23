"""Read-only current authority, source, graph and finding entry checks."""

import json
import runpy
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
support = runpy.run_path(
    str(OUT.parent / "f111_batch_05_evidence/runtime.py"), run_name="b08_support"
)
from apps.accounts.models import User
from apps.organizations.authorization import (
    effective_role_assignments,
    effective_scope_grants,
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import Organization
from apps.projects.models import Project
from apps.workforce.models import TrainingRequirement
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

org = Organization.objects.get(slug="demo-construction-01")
aliases = support["ALIASES"]
permissions = [
    "purchase_requests.create",
    "contracts.create",
    "warehouses.create",
    "workforce_qualifications.manage",
]
actors = []
for alias in aliases:
    user = User.objects.get(username=alias)
    member = get_active_membership(user=user, organization=org)
    actors.append(
        {
            "actor": alias,
            "member": str(member.pk),
            "roles": list(
                effective_role_assignments(member).values_list("role__code", flat=True)
            ),
            "grants": list(
                effective_scope_grants(member).values(
                    "id", "scope_type", "project__code", "site__code"
                )
            ),
            "permissions": {
                p: has_business_permission(
                    user=user, organization=org, permission=p, allow_any_scope=True
                )
                for p in permissions
            },
            "staff": user.is_staff,
            "superuser": user.is_superuser,
        }
    )
data = {
    "settings": settings.SETTINGS_MODULE,
    "database": connection.settings_dict["NAME"],
    "vendor": connection.vendor,
    "pending_migrations": len(
        MigrationExecutor(connection).migration_plan(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
    ),
    "actors": actors,
    "projects": list(
        Project.objects.filter(code__in=support["CODES"].values()).values(
            "id", "code", "name", "organization__slug", "deleted_at"
        )
    ),
    "training_requirements": TrainingRequirement.objects.count(),
}
register = (OUT / "register_entry.txt").read_text(encoding="utf-8")
import re

data["findings"] = {
    key: re.search(
        rf"- finding_id: UIUX-F-{key}\n.*?(?=\n- finding_id:|\Z)", register, re.S
    ).group()
    for key in (113, 116, 117, 125)
}
data["prior_batches"] = {
    str(i): "RUNTIME_VERIFIED_RESOLVED"
    in next((OUT.parent).glob(f"UIUX_F111_BATCH_{i:02d}*REPORT.md")).read_text(
        encoding="utf-8"
    )
    for i in range(1, 8)
}
graph = json.loads((ROOT / "graphify-out/graph.json").read_text(encoding="utf-8"))
nodes = {n["id"]: n for n in graph["nodes"]}
seed = {
    n["id"]
    for n in nodes.values()
    if n.get("label")
    in {
        "PurchaseRequestForm",
        "ContractForm",
        "WarehouseForm",
        "TrainingRequirementForm",
        "scope_queryset()",
    }
}
edges = graph.get("links", graph.get("edges", []))
data["graph_navigation"] = {
    "nodes": [nodes[n] for n in seed],
    "one_hop_edges": [e for e in edges if e["source"] in seed or e["target"] in seed],
    "use": "Read-only navigation; current source authoritative; no graph writes",
}
(OUT / "PREFLIGHT.json").write_text(
    json.dumps(data, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(
    json.dumps(
        {k: v for k, v in data.items() if k not in {"findings", "graph_navigation"}},
        default=str,
        ensure_ascii=True,
    )
)
