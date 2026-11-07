"""Clone an idle disposable test seed; never copies or mutates development data."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
import psycopg
from psycopg import sql
from django.db import connection

SOURCE = "test_bonira_operational_workspace_20261105"
TARGET = "test_bonira_dashboard_reporting_ready_20261106"
assert SOURCE.startswith("test_") and TARGET.startswith("test_") and SOURCE != TARGET
params = connection.get_connection_params()
params["connect_timeout"] = 5
with psycopg.connect(**params, autocommit=True) as conn:
    assert conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", (SOURCE,)).fetchone()[0] == 0
    if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TARGET,)).fetchone():
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(TARGET), sql.Identifier(SOURCE)))
seed = (ROOT / "output/operational-workspace/migration-seed.json").read_text(encoding="utf-8")
assert '"model": "organizations.businesspermission"' in seed
(ROOT / "output/dashboard-reporting/migration-seed.json").write_text(seed, encoding="utf-8")
p = ROOT / "scripts/verification/dashboard_reporting_validate.py"
p.write_text(p.read_text(encoding="utf-8").replace('test_bonira_dashboard_reporting_20261106', TARGET), encoding="utf-8")
print("Disposable test clone ready; canonical migration seed retained.")
