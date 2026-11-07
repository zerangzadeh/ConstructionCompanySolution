"""Workforce journeys in a dedicated, disposable PostgreSQL test database."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ.setdefault("BONIRA_BROWSER_LOCAL_ONLY", "1")

import django

django.setup()

from django.core.management import call_command
from django.db import connections

connections["default"].settings_dict["TEST"]["NAME"] = (
    "test_bonira_workforce_journey_01a1b054"
)

targets = sys.argv[1:] or [
    "apps.timekeeping.test_mvp02",
    "apps.workforce.test_mvp02",
    "apps.workforce.test_mvp02_uiux",
    "apps.workforce.test_mvp02_browser.FieldWorkforceBrowserTests.test_workforce_timekeeping_journeys",
]
call_command("test", *targets, keepdb=True, interactive=False, verbosity=1)
