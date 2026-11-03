"""Module Selector validation in a dedicated migrated PostgreSQL test database."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import pytest
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase

test_database = "test_bonira_module_selector_clone_20261103"
connections["default"].settings_dict["TEST"]["NAME"] = test_database
original_setup = TransactionTestCase._fixture_setup.__func__


@classmethod
def isolated_fixture_setup(cls):
    # Preserve immutable-history triggers. Replay the migration snapshot only
    # after flushing this disposable test DB, as in the qualified F1 harness.
    for alias in cls._databases_names(include_mirrors=False):
        connection = connections[alias]
        if cls.serialized_rollback and hasattr(connection, "_test_serialized_contents"):
            if connection.settings_dict["NAME"] != test_database:
                raise RuntimeError(
                    "Module Selector reset requires its dedicated test database"
                )
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
    original_setup(cls)


TransactionTestCase._fixture_setup = isolated_fixture_setup
raise SystemExit(pytest.main(sys.argv[1:]))
