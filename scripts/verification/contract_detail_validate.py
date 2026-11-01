"""Verify Contract Detail in an isolated PostgreSQL DB, never Development data."""

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
    "test_bonira_contract_detail_ref_20261101"
)
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/contracts/test_detail_dashboard.py",
            "apps/billing/test_mvp03.py",
            "apps/contracts/test_review_navigation.py",
            "--reuse-db",
            "-q",
        ]
    )
)
