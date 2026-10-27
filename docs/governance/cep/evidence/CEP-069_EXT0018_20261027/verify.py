"""Verify this bounded evidence packet; never issue statutory acceptance."""

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import yaml

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
import django

django.setup()
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.payroll.source_package_services import _validate_payload

checks = {}
package = json.loads((OUT / "EXT0018_SOURCE_REVIEW_PACKAGE.json").read_text("utf-8"))
expected = package.pop("content_sha256_excluding_this_field")
actual = hashlib.sha256(
    json.dumps(
        package,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
).hexdigest()
assert expected == actual
checks["review_package_digest"] = "PASS"
assert len({s["id"] for s in package["sources"]}) == len(package["sources"])
for source in package["sources"]:
    assert urlparse(source["source_url"]).hostname == "qavanin.ir"
    for artifact in source["artifacts"]:
        assert (
            hashlib.sha256((OUT / artifact["path"]).read_bytes()).hexdigest()
            == artifact["sha256"]
        )
checks["source_hashes_and_unique_identities"] = "PASS"
checks["source_authority_boundary"] = (
    "PASS_OFFICIAL_GOVERNMENT_PORTAL_SNAPSHOTS_NOT_CURRENTNESS_CERTIFICATION"
)
assert package["runtime_schema_compatibility"]["importable"] is False
assert package["review"]["disposition"] == "PENDING_HUMAN_REVIEW"
assert package["activation"]["status"] == "NOT_EXECUTED"
try:
    _validate_payload(package)
except ValidationError:
    checks["review_intake_rejected_as_runtime_payload"] = "PASS"
else:
    raise AssertionError("Incomplete review intake must never be importable")
for name, expected_hash in json.loads(
    (OUT / "IMPLEMENTATION_HASHES.json").read_text()
).items():
    data = (ROOT / name).read_bytes()
    committed = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
    # Git stores LF while checkout may use CRLF. Compare meaningful source exactly.
    assert data.replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n"), name
    assert hashlib.sha256(data).hexdigest() == expected_hash
checks["product_source_unchanged"] = "PASS"
focused = json.loads((OUT / "FOCUSED_RESULT.json").read_text())
assert focused["failures"] == 0
assert "Ran 16 tests" in (OUT / "FOCUSED_TESTS.txt").read_text("utf-8")
assert settings.DEBUG and connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
with transaction.atomic(), connection.cursor() as cursor:
    cursor.execute("SET TRANSACTION READ ONLY")
    cursor.execute(
        "SELECT count(*) FROM pg_database WHERE datname=%s",
        [focused["disposable_database"]],
    )
    assert cursor.fetchone()[0] == 0
checks["focused_tests"] = "16/16_PASS_SYNTHETIC_SAFETY_ONLY"
checks["disposable_database_removed"] = "PASS"
development = json.loads((OUT / "DEVELOPMENT.json").read_text())
assert not development["unapplied_migrations"]
assert len(development["missing_source_resolution"]) == 6
assert all(
    row["result"] == "FAIL_CLOSED_VALIDATION_ERROR"
    for row in development["missing_source_resolution"]
)
checks["configured_development_missing_source_cutoffs"] = "6/6_PASS"
registry = yaml.safe_load((ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text("utf-8"))
counts = Counter(
    registry["ceps"][f"CEP-{i:03}"]["execution"]["status"] for i in range(1, 80)
)
assert counts == {"COMPLETE": 78, "PARTIAL": 1}
assert registry["ceps"]["CEP-069"]["execution"]["status"] == "PARTIAL"
assert registry["gates"]["GATE-08"]["status"] == "PASS"
assert registry["gates"]["GATE-11"]["status"] == "NOT_PASSED"
assert registry["execution_frontier"]["next_executable_frontier"] == []
checks["canonical_registry_counts_and_gates"] = (
    "PASS_78_COMPLETE_1_PARTIAL_0_NOT_STARTED"
)
checks["required_review_currentness_and_official_activation"] = (
    "UNVERIFIED_HUMAN_REVIEW_REQUIRED"
)
checks["final_production_certification_and_human_signoff"] = "NOT_EXECUTED"
(OUT / "CHECKS.json").write_text(
    json.dumps(
        {
            "checks": checks,
            "source_count": len(package["sources"]),
            "package_digest": actual,
            "counts": counts,
            "next_executable_frontier": [],
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps(checks))
