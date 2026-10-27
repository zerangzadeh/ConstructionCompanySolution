"""Independent read-only runtime, source, Git and scoped-closeout checks."""

import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

import psycopg
import yaml

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
OLD = OUT.parent / "CEP-069_EXT0018_20261027"
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
import django

django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

checks = {}
hash_of = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = list(
    csv.DictReader((OLD / "ARTIFACT_HASHES.csv").read_text("utf-8").splitlines())
)
assert len(original) == 37
for row in original:
    path = OLD / row["path"]
    assert path.stat().st_size == int(row["bytes"]) and hash_of(path) == row["sha256"]
checks["original_37_artifacts_and_v1_source_package_unchanged"] = "PASS"
review = OLD / "ADOPTED_EXPERT_REVIEW.md"
for filename in ("TAX_PARAMETERS.json", "INSURANCE_PARAMETERS.json"):
    p = json.loads((OUT / filename).read_text("utf-8"))
    assert p["statutory_governance"]["review_sha256"] == hash_of(review)
checks["retained_human_review_parameter_hash_linkage"] = "PASS"
packages = json.loads((OUT / "RUNTIME_SOURCE_PACKAGES.json").read_text("utf-8"))
from apps.payroll.source_package_services import _digest

assert len(packages) == 4
for package in packages:
    assert _digest(package["content"]) == package["digest"]
    g = package["content"]["policy"]["parameters"]["statutory_governance"]
    for source in g["sources"]:
        if source["reference"] == "HOUSING-9234-T65481-1405":
            assert source["sha256"] == hash_of(OUT / "HOUSING_1405.rendered.json")
    assert (
        package["content"]["policy"]["adopted_review"]["disposition"]
        == "accepted_with_conditions"
    )
checks["four_runtime_package_content_and_adopted_review_digests"] = "PASS"
conditions = json.loads((OUT / "CONDITIONS_VERIFIED.json").read_text("utf-8"))
assert conditions["conditions"] == {str(i): "PASS" for i in range(1, 11)}
assert conditions["behavioral_test_count"] == 36
assert conditions["behavioral_result_sha256"] == hash_of(OUT / "REMEDIATION_TESTS.txt")
assert "Ran 36 tests" in (OUT / "REMEDIATION_TESTS.txt").read_text("utf-8")
assert json.loads((OUT / "REMEDIATION_RESULT.json").read_text("utf-8"))["failures"] == 0
q = json.loads((OUT / "QUALIFICATION_RESULT.json").read_text("utf-8"))
assert q["database_removed"] and q["nonproduction_qualification"] == "PASS"
assert q["business_database_before"] == q["business_database_after"]
checks["36_behavioral_cases_and_fresh_source_qualification"] = "PASS"
assert settings.DEBUG and settings.SETTINGS_MODULE == "config.settings.development"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
with transaction.atomic(), connection.cursor() as cursor:
    cursor.execute("SET TRANSACTION READ ONLY")
    cursor.execute(
        "SELECT count(*) FROM pg_database WHERE datname LIKE 'test_cep069_%'"
    )
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT count(*) FROM payroll_statutorysourcepackage")
    assert cursor.fetchone()[0] == 0
    executor = MigrationExecutor(connection)
    pending = [
        f"{m.app_label}.{m.name}"
        for m, backward in executor.migration_plan(executor.loader.graph.leaf_nodes())
    ]
    assert pending == ["payroll.0010_cep069_reviewed_statutory_context"]
checks["independent_database_cleanup_and_business_nonactivation"] = (
    "PASS_SQL_READ_ONLY_NEW_MIGRATION_PENDING"
)
params = deepcopy(connection.get_connection_params())
params["dbname"] = "test_construction_erp"
params["options"] = params.get("options", "") + " -c default_transaction_read_only=on"
with (
    psycopg.connect(**params) as template_connection,
    template_connection.cursor() as cursor,
):
    cursor.execute("SHOW transaction_read_only")
    assert cursor.fetchone()[0] == "on"
    for table in (
        "accounts_user",
        "organizations_organization",
        "payroll_statutorysourcepackage",
    ):
        cursor.execute('SELECT count(*) FROM "' + table + '"')
        assert cursor.fetchone()[0] == 0
    cursor.execute(
        "SELECT count(*) FROM django_migrations WHERE app='payroll' AND name='0010_cep069_reviewed_statutory_context'"
    )
    assert cursor.fetchone()[0] == 0
checks["empty_template_unchanged"] = "PASS_SQL_READ_ONLY"
registry = yaml.safe_load((ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text("utf-8"))
baseline = yaml.safe_load(
    subprocess.check_output(
        ["git", "show", "HEAD:CEP_EXECUTION_REGISTRY.yaml"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
)
assert {k: v for k, v in registry["ceps"].items() if k != "CEP-069"} == {
    k: v for k, v in baseline["ceps"].items() if k != "CEP-069"
}
counts = Counter(
    v["execution"]["status"]
    for k, v in registry["ceps"].items()
    if int(k.split("-")[1]) <= 79
)
assert counts == Counter({"COMPLETE": 79})
assert (
    registry["summary"]["execution_state_complete"] == 79
    and registry["summary"]["partial_current"] == 0
)
assert registry["gates"]["GATE-11"]["status"] == "NOT_PASSED"
assert registry["gates"]["GATE-08"]["status"] == "PASS"
assert registry["execution_frontier"]["next_executable_frontier"] == []
checks["registry_other_ceps_preserved_79_complete_gate11_not_passed_frontier_empty"] = (
    "PASS"
)
prompt = ROOT / "docs/governance/cep/PROMPTS/CEP-069_EXECUTION_PROMPT.md"
assert (
    hash_of(prompt)
    == "41d138764cb8fcde81dfea26f6c6df82202c54e4da3a641b2b18382811f2ebba"
)
assert (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    == "a1322c38e5c89d399c6ba54c239444a2b61c119a"
)
checks["canonical_prompt_and_head_unchanged"] = "PASS"
python = str(ROOT / ".venv-2/Scripts/python.exe")
product = [
    "apps/organizations/policy_specs.py",
    "apps/payroll/models.py",
    "apps/payroll/source_package_services.py",
    "apps/payroll/statutory_services.py",
    "apps/payroll/statutory_governance.py",
    "apps/payroll/test_cep069.py",
    "apps/payroll/migrations/0010_cep069_reviewed_statutory_context.py",
]
for name, args in (
    ("ruff", [python, "-m", "ruff", "check", *product, str(OUT)]),
    (
        "new_file_format",
        [
            python,
            "-m",
            "ruff",
            "format",
            "--check",
            product[4],
            product[5],
            product[6],
            str(OUT),
        ],
    ),
    ("django_system_check", [python, "manage.py", "check"]),
    (
        "migration_drift",
        [python, "manage.py", "makemigrations", "--check", "--dry-run"],
    ),
    ("whitespace", ["git", "diff", "--check"]),
):
    result = subprocess.run(
        args, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", check=False
    )
    checks[name] = {
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    assert result.returncode == 0, (name, result.stdout, result.stderr)
changes = list(
    csv.DictReader(
        (ROOT / "docs/governance/cep/manifests/CEP-069_CHANGE_MANIFEST.csv")
        .read_text("utf-8")
        .splitlines()
    )
)
assert all(
    (ROOT / row["path"]).is_file()
    or row["path"].endswith(("FINAL_CHECKS.json", "ARTIFACT_HASHES.csv"))
    for row in changes
)
result = {
    "checks": checks,
    "verdict": "PASS_APPROVED_NONPRODUCTION_CLOSEOUT",
    "production_certification": "NOT_EXECUTED",
    "human_signoff": "NOT_EXECUTED",
    "git_writes": "NONE",
}
(OUT / "FINAL_CHECKS.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
paths = {ROOT / row["path"] for row in changes}
paths.add(OUT / "FINAL_CHECKS.json")
paths.discard(OUT / "ARTIFACT_HASHES.csv")
assert all(path.is_file() for path in paths)
with (OUT / "ARTIFACT_HASHES.csv").open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["path", "bytes", "sha256"])
    for path in sorted(paths):
        writer.writerow(
            [path.relative_to(ROOT).as_posix(), path.stat().st_size, hash_of(path)]
        )
print(
    json.dumps(
        {
            "verdict": result["verdict"],
            "original_artifacts": len(original),
            "catalog_entries": len(paths),
            "focused_tests": 36,
            "CEP069": "COMPLETE_APPROVED_NONPRODUCTION",
            "gate11": "NOT_PASSED",
            "production_or_git_writes": "NONE",
        }
    )
)
