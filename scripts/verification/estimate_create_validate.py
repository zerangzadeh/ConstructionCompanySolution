"""Run Estimate Create acceptance on a dedicated disposable PostgreSQL test DB."""

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
    "test_bonira_estimate_create_acceptance_20261101"
)
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/estimates/test_create_reference.py",
            "apps/billing/test_mvp03_contextual_create.py",
            "apps/estimates/test_mvp03_estimate_ux.py",
            "--reuse-db",
            "-q",
        ]
    )
)
