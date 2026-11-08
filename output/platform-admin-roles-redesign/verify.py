"""Repeatable isolated PostgreSQL regression runner; no live database changes."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.conf import settings

settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
    "test_bonira_roles_redesign_20261107"
)

import django

django.setup()

import pytest

raise SystemExit(pytest.main([
    "apps/organizations/test_platform_roles_ui.py",
    "apps/organizations/test_platform_console.py",
    "apps/organizations/test_p1_1_authorization.py",
    "core/test_cep014_administration.py",
    "--reuse-db", "-p", "no:cacheprovider", "-q", "--tb=short",
    "--show-capture=no",
]))
