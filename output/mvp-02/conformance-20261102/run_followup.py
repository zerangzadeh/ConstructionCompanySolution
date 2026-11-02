"""Rerun corrected UI checks and the isolated retained-table teardown failure."""

import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
os.chdir(root)
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
import pytest
from django.test import override_settings

from apps.timekeeping.test_cep062 import MissionRoutingConcurrencyTests
from apps.workforce.test_mvp02_browser import FieldWorkforceBrowserTests

# The original concurrency assertions run unchanged. Reuse the already-qualified,
# test_-guarded Django cascading flush for retained retired Payments FK tables.
# This patch exists only in this non-production runner, never in application code.
MissionRoutingConcurrencyTests._fixture_teardown = FieldWorkforceBrowserTests._fixture_teardown

evidence = root / "output/mvp-02/conformance-20261102"
args = [
    "apps/workforce/test_mvp02_conformance.py::ConformanceTests",
    "apps/workforce/test_mvp02_conformance.py::ConformanceBrowserTests::test_frozen_details_and_policy_aware_review",
    "apps/timekeeping/test_cep062.py::MissionRoutingConcurrencyTests::test_duplicate_source_race_has_one_native_target",
    "-q", "--reuse-db", "--tb=line", f"--junitxml={evidence / 'followup-junit.xml'}",
]
(evidence / "followup-argv.json").write_text(json.dumps(args, indent=2), encoding="utf-8")
traces = {p: p.read_bytes() for p in (root / "docs/governance/cep/evidence").glob("CEP-062_*TRACE.json")}
try:
    with override_settings(MEDIA_ROOT=evidence / "test-media"):
        result = pytest.main(args)
finally:
    for path, content in traces.items():
        path.write_bytes(content)
raise SystemExit(result)
