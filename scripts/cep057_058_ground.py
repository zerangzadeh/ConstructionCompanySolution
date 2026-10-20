"""Read-only grounding; run from repository root with the Development interpreter."""

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.db import connection, transaction

from apps.organizations.models import OrganizationMembership
from apps.workforce.models import WorkRelationship
from scripts.cep057_058_package import validate

root = Path(r"C:/Users/azera/Downloads/BONIRA_CEP057_058_SYNTHETIC_DEV_CLOSURE_V2")
package = validate(root)
registry = Path("CEP_EXECUTION_REGISTRY.yaml").read_text(encoding="utf-8")
manifest = Path("docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text()
proof = {
    "package_validation": package,
    "canonical": {},
    "sources": {},
    "dependencies": {},
}
for cep in ("CEP-023", "CEP-025", "CEP-029", "CEP-057", "CEP-058"):
    raw = Path(f"docs/governance/cep/PROMPTS/{cep}_EXECUTION_PROMPT.md").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    block = re.search(rf"  {cep}:\n(.*?)(?=\n  CEP-|\Z)", manifest, re.DOTALL)[1]
    assert digest == re.search(r"sha256: (\w+)", block)[1]
    proof["canonical"][cep] = digest
    if cep not in ("CEP-057", "CEP-058"):
        block = re.search(rf"  {cep}:\n(.*?)(?=\n  CEP-|\Z)", registry, re.DOTALL)[1]
        assert re.search(r"    execution:\n      status: COMPLETE", block)
        proof["dependencies"][cep] = "COMPLETE_WITH_IMPLEMENTATION_PRESENT"
discovery = json.loads(
    Path(
        "docs/governance/cep/supporting/v1-data-intake/DISCOVERY_AND_VALIDATION.json"
    ).read_text()
)
recovery_root = Path(discovery["recovery_root"])
for name, entry in discovery["recovery_sources"].items():
    path = recovery_root / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    proof["sources"][name] = {"sha256": entry["sha256"], "members": {}}
    with zipfile.ZipFile(path) as archive:
        for member, digest in entry["members"].items():
            found = [n for n in archive.namelist() if n.split("/")[-1] == member]
            assert len(found) == 1
            content = archive.read(found[0])
            assert hashlib.sha256(content).hexdigest() == digest
            proof["sources"][name]["members"][member] = digest
            # Retain only relevant specification/IMB/external clauses; no new source authority.
            if "SPECIFICATION.md" in member or "DECISION_REGISTER" in member:
                decoded = content.decode("utf-8-sig")
                selected = [
                    line
                    for line in decoded.splitlines()
                    if any(
                        x in line
                        for x in (
                            "opening",
                            "Opening",
                            "reset",
                            "Reset",
                            "PD-026",
                            "PD-031",
                            "Decision-05",
                            "migration",
                            "Migration",
                            "IMB-0075",
                            "IMB-0080",
                        )
                    )
                ]
                proof["sources"][name]["members"][member] = {
                    "sha256": digest,
                    "relevant_lines": selected,
                }
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    assert settings.SETTINGS_MODULE == "config.settings.development"
    assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1")
    with Path(
        "docs/governance/cep/evidence/CEP-029_SOURCE_TARGET_MAPPING.csv"
    ).open() as stream:
        mapping = list(csv.DictReader(stream))
    subjects = []
    for row in mapping:
        obj = WorkRelationship.objects.get(
            pk=row["relationship_id"],
            organization_id=row["organization_id"],
            legacy_employee_id=row["employee_id"],
            person_id=row["person_id"],
        )
        assert obj.revisions.exists()
        subjects.append(obj)
    assert len(subjects) == len({s.pk for s in subjects}) == 10
    proof["identity_resolution"] = [
        {
            "source_employee_key": f"DEV-HR-{i:03}",
            "organization_id": str(s.organization_id),
            "relationship_id": str(s.pk),
            "employee_id": str(s.legacy_employee_id),
            "person_id": str(s.person_id),
            "revision_ids": list(map(str, s.revisions.values_list("pk", flat=True))),
        }
        for i, s in enumerate(sorted(subjects, key=lambda s: s.pk), 1)
    ]
    proof["actors"] = [
        {
            "organization_id": str(m.organization_id),
            "user_id": str(m.user_id),
            "role": m.role,
        }
        for m in OrganizationMembership.objects.filter(
            organization_id__in={s.organization_id for s in subjects}, status="active"
        )
    ]
    from apps.payroll.models import (
        PayrollComponent,
        PayrollCumulativeState,
        PayrollRun,
        PayrollYearInterval,
    )
    from apps.workforce.leave_models import LeaveBalanceEntry, LeavePolicyVersion

    proof["database_before"] = {
        model.__name__: model.objects.count()
        for model in (
            LeavePolicyVersion,
            LeaveBalanceEntry,
            PayrollCumulativeState,
            PayrollComponent,
            PayrollYearInterval,
            PayrollRun,
        )
    }
    from django.db.migrations.executor import MigrationExecutor

    proof["pending_migrations"] = [
        str(m)
        for m in MigrationExecutor(connection).migration_plan(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
    ]
    assert not proof["pending_migrations"]
proof["git"] = {
    key: subprocess.check_output(["git", *args], text=True).strip()
    for key, args in {
        "head": ["rev-parse", "HEAD"],
        "origin": ["rev-parse", "origin/main"],
        "branch": ["branch", "--show-current"],
        "status": ["status", "--short"],
        "diff_names": ["diff", "--name-status"],
        "diff_stat": ["diff", "--stat"],
    }.items()
}
Path("docs/governance/cep/evidence/CEP-057_058_SYNTHETIC_GROUNDING.json").write_text(
    json.dumps(proof, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {
            k: proof[k]
            for k in (
                "dependencies",
                "identity_resolution",
                "actors",
                "database_before",
                "pending_migrations",
            )
        },
        indent=2,
    )
)
