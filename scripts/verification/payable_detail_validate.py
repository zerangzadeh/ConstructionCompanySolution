"""Verify Payable Certificate Detail in an isolated PostgreSQL DB, never Development data."""

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
    "test_bonira_payable_detail_ready_20261101"
)
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/billing/test_payable_detail.py",
            "--reuse-db",
            "-q",
        ]
    )
)
