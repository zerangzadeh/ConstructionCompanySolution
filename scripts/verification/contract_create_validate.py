"""Contract Create verification on its own isolated PostgreSQL test database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import pytest
from django.db import connections

connections["default"].settings_dict["TEST"]["NAME"] = (
    "test_bonira_contract_create_reference_20261101"
)
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/contracts/test_create_reference.py",
            "apps/billing/test_mvp03_contextual_create.py",
            "--reuse-db",
            "-q",
        ]
    )
)
