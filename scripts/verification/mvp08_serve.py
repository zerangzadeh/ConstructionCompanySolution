"""Retained local UAT copy; safe error pages and local static assets."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["DB_NAME"] = "test_bonira_mvp08_demo_20261103"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.conf import settings
from django.core.management import call_command

from apps.accounts.management.commands.seed_mvp_demo import SLUG, guard_environment
from apps.organizations.models import Organization

guard_environment()
Organization.objects.get(slug=SLUG)
settings.DEBUG = False
settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
settings.PRODUCT_SURFACE_PROFILE = "MVP"
settings.DOCUMENT_PROTECTED_ROOT = ROOT / "output/mvp-08/continuation-20261103/protected-source"
call_command(
    "runserver",
    "127.0.0.1:8008",
    use_reloader=False,
    insecure_serving=True,
)
