"""Compile and validate the frozen P10-S20 dataset plan.

This certification-only tool does not alter product runtime. Preflight mode emits
a deterministic plan and one canary descriptor per data family. Full ORM/DMS
materialization remains deliberately unavailable until an isolated environment
and an approved loader implementation exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROFILE_ID = "P10-S20-WP1-20261007-E0E078C9-A"
ROOT = Path(__file__).resolve().parent


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compile_plan() -> dict[str, Any]:
    volume = _load("dataset_volume.json")
    workload = _load("workload.json")
    if volume["workload_profile_id"] != PROFILE_ID:
        raise ValueError("dataset profile ID does not match the frozen profile")
    if workload["workload_profile_id"] != PROFILE_ID:
        raise ValueError("workload profile ID does not match the frozen profile")
    if workload["tenants"] != 10 or workload["projects_per_tenant"] != 10:
        raise ValueError("Tenant/project cardinality does not match WP1")
    if sum(workload["journey_family_percent"].values()) != 100:
        raise ValueError("journey-family shares must total 100")
    if abs(sum(volume["lifecycle_distribution"].values()) - 1) > 1e-9:
        raise ValueError("lifecycle distribution must total 1")
    dms = volume["dms"]
    if dms["aggregate_documents"] != 220_000:
        raise ValueError("DMS document count does not match WP1")
    if dms["aggregate_versions"] != 550_000:
        raise ValueError("DMS version count does not match WP1")
    rows = volume["standard_tenant_rows"]
    plan = {
        "workload_profile_id": PROFILE_ID,
        "mode": "preflight-plan-only",
        "standard_tenant_units": 11,
        "standard_tenant_rows": rows,
        "dms": dms,
        "canary_descriptors": [
            {"family": family, "count": 1, "target": count}
            for family, count in sorted(rows.items())
        ],
        "materialization_supported": False,
        "materialization_blocker": (
            "No approved certification-only ORM/DMS loader exists for the full "
            "frozen relational dataset."
        ),
    }
    plan["plan_sha256"] = _canonical_hash(plan)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = compile_plan()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "plan_sha256": plan["plan_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
