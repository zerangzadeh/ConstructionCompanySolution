"""Run existing focused/affected tests against an explicitly isolated test database."""
import os
from pathlib import Path
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.environ["DOCUMENT_PROTECTED_ROOT"] = tempfile.mkdtemp(prefix="bonira-rv007-test-files-")
import django

django.setup()
from django.conf import settings
from django.contrib.auth.hashers import reset_hashers

assert settings.DEBUG and settings.DATABASES["default"]["HOST"] in {"localhost", "127.0.0.1", "::1"}
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = "test_bonira_uiux_batch09"
settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
reset_hashers(setting="PASSWORD_HASHERS")
import pytest

mode = sys.argv[1]
selection = {
    "focused": ["apps/procurement/test_p5_s09_protected_opening.py"],
    "affected": ["apps/procurement/test_rfq.py", "apps/procurement/test_rfq_close.py", "apps/procurement/test_quotes.py", "apps/procurement/test_p5_s08_sealed_custody.py", "apps/procurement/test_p5_s10_admissibility.py", "apps/procurement/test_p5_s11_comparison_award.py", "apps/procurement/test_cep032_buyer_actions.py"],
}[mode]
sys.exit(pytest.main(["-q", "--tb=short", "--reuse-db", "--junitxml=" + str(OUT / (mode + ".xml")), *selection]))
