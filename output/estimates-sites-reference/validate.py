"""Focused validation on a separate clone of an idle synthetic test baseline."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import psycopg
import pytest
from django.db import connections
from psycopg import sql

db = connections["default"].settings_dict
test_name = "test_bonira_estimates_sites_ready_20261101"
baseline = "test_bonira_mvp03_20261029"
with psycopg.connect(
    dbname="postgres",
    user=db["USER"],
    password=db["PASSWORD"],
    host=db["HOST"],
    port=db["PORT"],
    autocommit=True,
) as connection:
    if not connection.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (test_name,)
    ).fetchone():
        active = connection.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = %s", (baseline,)
        ).fetchone()[0]
        if active:
            raise RuntimeError("Test baseline is busy; do not clone it.")
        connection.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(test_name), sql.Identifier(baseline)
            )
        )
db["TEST"]["NAME"] = test_name
raise SystemExit(
    pytest.main(
        [
            "apps/estimates/test_mvp03_estimate_ux.py",
            "apps/projects/tests.py::ProjectServiceTests::test_all_site_list_is_tenant_scoped",
            "apps/contracts/test_filter_bar.py",
            "core/test_cep003_localization_accessibility.py",
            "--reuse-db",
            "-q",
        ]
    )
)
