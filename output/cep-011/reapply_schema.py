"""Reapply only CEP-011 schema on its isolated disposable test database."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
from django.conf import settings

TEST_NAME = "test_cep011_validation_20261015_dms"
settings.DATABASES["default"]["NAME"] = TEST_NAME

from django.core.management import call_command
from django.db import connection

django.setup()
with connection.cursor() as cursor:
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == TEST_NAME

call_command("migrate", "workforce", "0009", verbosity=0)
call_command("migrate", "documents", "0010", verbosity=0)
call_command("migrate", "documents", "0011", verbosity=0)
call_command("migrate", "workforce", "0010", verbosity=0)
print("CEP-011 isolated migration reapply: PASS")
