"""B1 checks in a dedicated PostgreSQL test database; never development data."""

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
from django.core.management import call_command
from django.db import connections

TEST_DATABASE = "test_bonira_b1_warehouse_20261104"
connections["default"].settings_dict["TEST"]["NAME"] = TEST_DATABASE


class RetainMigrationSeed:
    @pytest.fixture(scope="session", autouse=True)
    def migration_seed(self, django_db_setup, django_db_blocker):
        with django_db_blocker.unblock():
            connection = connections["default"]
            if connection.settings_dict["NAME"] != TEST_DATABASE:
                raise RuntimeError(
                    "B1 fixture reset requires its dedicated test database"
                )
            seed_path = ROOT / "output/b1-warehouse-list/migration-seed.json"
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
            raise RuntimeError("B1 seed restoration is test-only")
        call_command(
            "flush",
            interactive=False,
            verbosity=0,
            allow_cascade=True,
            inhibit_post_migrate=True,
        )
        connections["default"].creation.deserialize_db_from_string(seed)


raise SystemExit(
    pytest.main(
        sys.argv[1:] or ["tests/test_warehouse_reference_list.py", "--reuse-db", "-q"],
        plugins=[RetainMigrationSeed()],
    )
)
