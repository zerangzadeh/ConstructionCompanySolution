import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.conf import settings

settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
    "test_cep011_validation_20261015_dms"
)

import pytest

raise SystemExit(
    pytest.main(
        [
            "apps/documents/test_cep011.py",
            "-q",
            "--reuse-db",
            "--junitxml=output/cep-011/focused-results.xml",
        ]
    )
)
