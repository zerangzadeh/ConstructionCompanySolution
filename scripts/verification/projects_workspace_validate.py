"""Projects UI verification against a dedicated migrated PostgreSQL test DB."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ.setdefault("BONIRA_BROWSER_LOCAL_ONLY", "1")

import django

django.setup()

import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase

TEST_DATABASE = "test_bonira_projects_workspace_ready_20261103"
connections["default"].settings_dict["TEST"]["NAME"] = TEST_DATABASE

# Use the repository's F1 isolated-fixture pattern: immutable published workflow
# rows must be empty before Django replays its serialized migration seed state.
original_fixture_setup = TransactionTestCase._fixture_setup.__func__


@classmethod
def isolated_fixture_setup(cls):
    for alias in cls._databases_names(include_mirrors=False):
        connection = connections[alias]
        if cls.serialized_rollback and hasattr(connection, "_test_serialized_contents"):
            if connection.settings_dict["NAME"] != TEST_DATABASE:
                raise RuntimeError("Projects fixture reset requires its dedicated DB")
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
    original_fixture_setup(cls)


TransactionTestCase._fixture_setup = isolated_fixture_setup


class EvidenceLocation:
    @pytest.fixture(scope="session", autouse=True)
    def retained_migration_seed(self, django_db_setup, django_db_blocker):
        """Keep repeated browser runs independent of their final test flush."""
        seed_path = root / "output/projects-ui-20261103/migration-seed.json"
        with django_db_blocker.unblock():
            connection = connections["default"]
            if connection.settings_dict["NAME"] != TEST_DATABASE:
                raise RuntimeError("Seed replay requires the dedicated Projects DB")
            if seed_path.exists():
                seed = seed_path.read_text(encoding="utf-8")
            else:
                seed = connection._test_serialized_contents
                if '"model": "organizations.businesspermission"' not in seed:
                    raise RuntimeError("A migrated, seeded test baseline is required")
                seed_path.parent.mkdir(parents=True, exist_ok=True)
                seed_path.write_text(seed, encoding="utf-8")
            connection._test_serialized_contents = seed
            call_command(
                "flush",
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
            connection.creation.deserialize_db_from_string(seed)
        yield
        with django_db_blocker.unblock():
            call_command(
                "flush",
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
            connection.creation.deserialize_db_from_string(seed)

    def pytest_collection_modifyitems(self, items):
        for item in items:
            cls = getattr(item, "cls", None)
            if cls and issubclass(cls, StaticLiveServerTestCase):
                cls.browser_evidence_directory = (
                    root / "output/projects-ui-20261103/browser" / cls.__name__
                )


targets = [
    "apps/projects/test_command_center.py",
    "apps/projects/test_mvp03_business_hub.py",
    "apps/projects/test_command_center_browser.py",
    "apps/contracts/test_filter_bar.py",
    "apps/contracts/test_reference_list_browser.py",
]
arguments = sys.argv[1:]
if not arguments or arguments[0].startswith("-"):
    arguments = [*targets, *(arguments or ["--reuse-db", "-q"])]
raise SystemExit(
    pytest.main(
        arguments,
        plugins=[EvidenceLocation()],
    )
)
