"""Focused synthetic safety qualification for CEP-069; no current-law claim."""

import contextlib
import json
import os
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[4]))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
import django

django.setup()
from django.conf import settings
from django.db import connection
from django.test.runner import DiscoverRunner

assert settings.DEBUG and connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
name = "test_cep069_" + uuid.uuid4().hex[:16]
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = name
labels = ["apps.payroll.test_cep052.SourcePackageTests"]
with (
    (OUT / "FOCUSED_TESTS.txt").open("w", encoding="utf-8") as stream,
    contextlib.redirect_stdout(stream),
    contextlib.redirect_stderr(stream),
):
    runner = DiscoverRunner(verbosity=2, interactive=False, keepdb=False)
    failures = runner.run_tests(labels)
result = {
    "labels": labels,
    "failures": failures,
    "disposable_database": name,
    "keepdb": False,
    "evidence_scope": "Synthetic framework safety only; existing completed CEP-052 lifecycle unchanged",
    "current_statutory_correctness": "UNVERIFIED; official reviewed package unavailable",
    "production_certification": "NOT_EXECUTED",
}
(OUT / "FOCUSED_RESULT.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result))
raise SystemExit(bool(failures))
