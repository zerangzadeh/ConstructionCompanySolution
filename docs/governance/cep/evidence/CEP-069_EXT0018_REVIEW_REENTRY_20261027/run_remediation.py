"""Fresh isolated migration + regression; never migrate configured business DB."""

import contextlib
import json
import os
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path[:0] = [str(ROOT), str(OUT)]
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
import django

django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.test.runner import DiscoverRunner

assert settings.DEBUG and connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
template = json.loads((OUT / "TEMPLATE_CHECK.json").read_text("utf-8"))
assert template["eligible"] and template["read_only"]
name = "test_cep069_remed_" + uuid.uuid4().hex[:12]
settings.DATABASES["default"].setdefault("TEST", {}).update(
    NAME=name, TEMPLATE=template["template"]
)
labels = [
    "apps.payroll.test_cep069.AdoptedStatutoryTests",
    "delta_tests.ConditionalReviewTests.test_conditional_review_cannot_import",
    "delta_tests.ConditionalReviewTests.test_conditional_review_cannot_bypass_through_publication",
    "delta_tests.ConditionalReviewTests.test_changed_to_conditional_evidence_blocks_existing_package_activation",
]
with (
    (OUT / "REMEDIATION_TESTS.txt").open("w", encoding="utf-8") as stream,
    contextlib.redirect_stdout(stream),
    contextlib.redirect_stderr(stream),
):
    failures = DiscoverRunner(
        verbosity=2, interactive=False, keepdb=False, debug_mode=True
    ).run_tests(labels)
with transaction.atomic(), connection.cursor() as cursor:
    cursor.execute("SET TRANSACTION READ ONLY")
    cursor.execute("SELECT count(*) FROM pg_database WHERE datname=%s", [name])
    removed = cursor.fetchone()[0] == 0
assert removed
result = {
    "failures": failures,
    "database": name,
    "database_removed": removed,
    "template_mutation": "NONE",
    "labels": labels,
    "production": "NOT_ACCESSED",
    "business_database_mutation": "NONE",
}
(OUT / "REMEDIATION_RESULT.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result))
raise SystemExit(bool(failures))
