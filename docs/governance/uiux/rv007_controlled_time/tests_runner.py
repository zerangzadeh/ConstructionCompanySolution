"""Focused/affected and exact frozen-HEAD replay in isolated test databases."""
import json
import os
from pathlib import Path
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
mode = sys.argv[1]
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
target = ROOT
if mode == "frozen":
    target = Path(json.loads((OUT.parent / "wave_c_final_closure/FROZEN_SOURCE.json").read_text())["path"])
os.chdir(target)
sys.path.insert(0, str(target))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.environ["DOCUMENT_PROTECTED_ROOT"] = tempfile.mkdtemp(prefix="bonira-rv007-controlled-tests-")
import django
django.setup()
from django.conf import settings
from django.contrib.auth.hashers import reset_hashers
assert settings.DEBUG and settings.DATABASES["default"]["HOST"] in {"localhost", "127.0.0.1", "::1"}
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = "test_bonira_wc_closure_frozen" if mode == "frozen" else "test_bonira_uiux_batch09"
settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
reset_hashers(setting="PASSWORD_HASHERS")
import pytest
affected = ["apps/procurement/test_rfq.py", "apps/procurement/test_rfq_close.py", "apps/procurement/test_quotes.py", "apps/procurement/test_p5_s08_sealed_custody.py", "apps/procurement/test_p5_s10_admissibility.py", "apps/procurement/test_p5_s11_comparison_award.py", "apps/procurement/test_cep032_buyer_actions.py"]
selection = ["apps/procurement/test_p5_s09_protected_opening.py"] if mode == "focused" else affected
if mode == "frozen":
    selection = ["apps/procurement/test_cep032_buyer_actions.py", "apps/procurement/test_rfq_close.py::RFQCloseManifestTests::test_close_permission_is_intersected_with_project_scope"]
sys.exit(pytest.main(["-q", "--tb=short", "--reuse-db", "--junitxml=" + str(OUT / (mode + ".xml")), *selection]))
