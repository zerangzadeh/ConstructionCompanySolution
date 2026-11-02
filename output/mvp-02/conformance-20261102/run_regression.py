"""Reproduce the bounded regression; preserve historical generated traces."""

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

args = [
    "apps/workforce/test_mvp02.py",
    "apps/workforce/test_mvp02_uiux.py",
    "apps/workforce/test_mvp02_conformance.py::ConformanceTests",
    "apps/workforce/test_mvp02_conformance.py::ConformanceBrowserTests::test_frozen_details_and_policy_aware_review",
    "apps/workforce/test_mvp02_planned_end.py",
    "apps/workforce/test_cep010_person_workrelationship.py",
    "apps/workforce/test_cep029.py",
    "apps/timekeeping/test_mvp02.py",
    "apps/timekeeping/test_cep024_scope.py",
    "apps/timekeeping/test_p7_s06_s12_timekeeping.py",
    "apps/timekeeping/test_cep022_roster.py",
    "apps/timekeeping/test_cep062.py",
    "core/test_product_surface.py",
    "core/test_home.py",
    "core/test_cep017_navigation.py",
    "apps/organizations/test_permission_decorators.py",
    "apps/organizations/test_p1_1_authorization.py",
    "apps/workforce/test_mvp02_browser.py::FieldWorkforceBrowserTests::test_scenarios_a_through_h",
    "-q", "--reuse-db", "--tb=line",
]
evidence = root / "output/mvp-02/conformance-20261102"
(evidence / "regression-argv.json").write_text(json.dumps(args, indent=2), encoding="utf-8")
traces = {p: p.read_bytes() for p in (root / "docs/governance/cep/evidence").glob("CEP-062_*TRACE.json")}
os.environ["MVP02_BROWSER_EVIDENCE_DIRECTORY"] = str(evidence / "browser/retained-a-h")
try:
    with override_settings(MEDIA_ROOT=evidence / "test-media"):
        result = pytest.main(args)
finally:
    for path, content in traces.items():
        path.write_bytes(content)
raise SystemExit(result)
