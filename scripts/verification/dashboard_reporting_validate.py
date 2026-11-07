"""Dashboard/report checks in dedicated disposable PostgreSQL; never development data."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ.setdefault("BONIRA_BROWSER_LOCAL_ONLY", "1")

import django

django.setup()

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.color import no_style
from django.db import connections

TEST_DATABASE = "test_bonira_dashboard_reporting_ready_20261106"
connections["default"].settings_dict["TEST"]["NAME"] = TEST_DATABASE


class RetainMigrationSeed:
    @pytest.fixture(autouse=True)
    def baseline_templates(self):
        if os.environ.get("BONIRA_DASHBOARD_BASELINE") != "1":
            yield
            return
        from copy import deepcopy

        from django.conf import settings
        from django.test import override_settings

        configured = deepcopy(settings.TEMPLATES)
        configured[0]["DIRS"] = [
            ROOT / "output/dashboard-reporting/baseline-templates",
            *configured[0]["DIRS"],
        ]
        with override_settings(TEMPLATES=configured):
            yield

    @pytest.fixture(scope="session", autouse=True)
    def migration_seed(self, django_db_setup, django_db_blocker):
        with django_db_blocker.unblock():
            connection = connections["default"]
            if connection.settings_dict["NAME"] != TEST_DATABASE:
                raise RuntimeError(
                    "Dashboard fixture reset requires its dedicated test database"
                )
            seed_path = ROOT / "output/dashboard-reporting/migration-seed.json"
            seed = (
                seed_path.read_text(encoding="utf-8")
                if seed_path.exists()
                else connection._test_serialized_contents
            )
            if '"model": "organizations.businesspermission"' not in seed:
                raise RuntimeError("A fully migrated permission catalogue is required")
            seed_path.write_text(seed, encoding="utf-8")
            connection._test_serialized_contents = seed
            self.restore(seed)
        yield
        with django_db_blocker.unblock():
            self.restore(seed)

    @staticmethod
    def restore(seed):
        if connections["default"].settings_dict["NAME"] != TEST_DATABASE:
            raise RuntimeError("Dashboard seed restoration is test-only")
        call_command(
            "flush",
            interactive=False,
            verbosity=0,
            allow_cascade=True,
            inhibit_post_migrate=True,
        )
        connections["default"].creation.deserialize_db_from_string(seed)
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        synchronize_authorization_catalog(using="default")
        # Explicit IDs in the retained seed do not advance PostgreSQL sequences.
        # New additive migrations/post_migrate may allocate content types next.
        connection = connections["default"]
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), apps.get_models()):
                cursor.execute(sql)


raise SystemExit(
    pytest.main(
        sys.argv[1:]
        or [
            "tests/test_dashboard_reporting.py",
            "core/test_home_workspace.py",
            "apps/projects/test_command_center.py",
            "core/test_product_surface.py",
            "--reuse-db",
            "-q",
        ],
        plugins=[RetainMigrationSeed()],
    )
)
