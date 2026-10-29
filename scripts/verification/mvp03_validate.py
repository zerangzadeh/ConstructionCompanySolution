"""Run MVP-03 checks in a dedicated, reusable, non-Development test database."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import pytest
from django.db import connections

connections["default"].settings_dict["TEST"]["NAME"] = "test_bonira_mvp03_20261029"
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/billing/test_mvp03.py",
            "apps/projects/test_mvp03_business_hub.py",
            "apps/billing/test_mvp03_browser.py",
            "--reuse-db",
            "-q",
        ]
    )
)
