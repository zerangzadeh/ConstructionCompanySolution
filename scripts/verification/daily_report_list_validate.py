"""Run the daily reports UX checks on a dedicated test database."""

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
    "test_bonira_daily_list_ready_20261101"
)
raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "apps/daily_reports/test_list_reference.py",
            "--reuse-db",
            "-q",
        ]
    )
)
