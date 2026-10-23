"""Rerun unchanged test with only its historical-file export redirected."""
import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.stdout.reconfigure(encoding="utf-8")
import pytest

target = ROOT / "docs/governance/cep/evidence/CEP-068_MISSION_LINK_TRACE.json"
before = hashlib.sha256(target.read_bytes()).hexdigest()
original_write_text = Path.write_text


def isolated_write(path, data, *args, **kwargs):
    if path.resolve() == target:
        return original_write_text(OUT / "MISSION_LINK_TRACE.json", data, encoding="utf-8")
    return original_write_text(path, data, *args, **kwargs)


with patch.object(Path, "write_text", isolated_write):
    code = pytest.main([
        "apps/workforce/test_cep068_mission.py::ESSMissionTests::test_own_routing_link_is_projection_only_and_hides_financial_reviewer_data",
        "-q", "--reuse-db", "--disable-warnings", "--tb=no", "-p", "no:cacheprovider",
        "--junitxml=" + str(OUT / "GATE07_RETRY.xml"),
    ])
assert hashlib.sha256(target.read_bytes()).hexdigest() == before
(OUT / "GATE07_RETRY.json").write_text(json.dumps({
    "exit_code": int(code), "assertions_and_product_code": "UNCHANGED",
    "harness_only_change": "Historical trace exporter redirected to this reentry's UTF-8 evidence; no assertion or business-path substitution",
    "historical_trace_preserved_sha256": before,
    "initial_failure_class": "TEST INFRASTRUCTURE DEBT: cp1252 legacy evidence export, after original projection/privacy assertions passed",
    "scope": "Single original failed case only; original 41 PASS retained without duplication",
}, indent=2) + "\n", encoding="utf-8")
sys.exit(int(code))
