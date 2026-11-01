"""Run Estimate Detail checks in a disposable PostgreSQL DB; never seed development."""

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

connections["default"].settings_dict["TEST"]["NAME"] = (
    "test_bonira_estimate_detail_clone_20261101"
)
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/estimates/test_detail_reference.py",
            "apps/estimates/test_mvp03_estimate_ux.py",
            "--reuse-db",
            "-q",
        ]
    )
)
