import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.conf import settings

settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
    "test_cep006_validation_20261015_b62e"
)

import pytest

raise SystemExit(
    pytest.main(
        [
            "apps/subledgers/tests.py",
            "apps/treasury/tests.py",
            "apps/reporting/test_p10_s07_s13.py",
            "-q",
            "--reuse-db",
            "--junitxml=output/cep-006/focused-results.xml",
        ]
    )
)
