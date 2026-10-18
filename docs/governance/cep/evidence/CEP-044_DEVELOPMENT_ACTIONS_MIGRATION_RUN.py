"""Bounded approved local expand with old-column data fingerprints, no row export."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.settings_dict["HOST"] in ("127.0.0.1", "localhost", "::1")
assert "prod" not in connection.settings_dict["NAME"].lower()
assert connection.vendor == "postgresql" and connection.Database.__name__ == "psycopg"
TARGET = [("subledgers", "0008_cep044_writeoff_actions")]
executor = MigrationExecutor(connection)
plan = executor.migration_plan(TARGET)
assert [(m.app_label, m.name, backwards) for m, backwards in plan] == [
    ("subledgers", TARGET[0][1], False)
]

tables = {
    model._meta.db_table: model._meta.pk.column
    for model in apps.get_models(include_auto_created=True)
    if model._meta.managed and not model._meta.proxy
}
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT table_name,column_name FROM information_schema.columns "
        "WHERE table_schema=current_schema() ORDER BY table_name,ordinal_position"
    )
    columns = {}
    for table, column in cursor.fetchall():
        if table in tables:
            columns.setdefault(table, []).append(column)


def encode(value):
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    return str(value)


def snapshot():
    result = {}
    for table, names in columns.items():
        # The list was captured before the expand: every existing column is
        # checked without interpreting the new NULL relationship as a change.
        digest = hashlib.sha256()
        count = 0
        fields = ",".join(connection.ops.quote_name(name) for name in names)
        quoted_table = connection.ops.quote_name(table)
        pk = connection.ops.quote_name(tables[table])
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {fields} FROM {quoted_table} ORDER BY {pk}")
            while rows := cursor.fetchmany(1000):
                for row in rows:
                    digest.update(
                        json.dumps(
                            row, sort_keys=True, separators=(",", ":"), default=encode
                        ).encode("utf-8")
                        + b"\n"
                    )
                    count += 1
        result[table] = {"count": count, "sha256": digest.hexdigest()}
    return result


before = snapshot()
executor.migrate(TARGET)
after = snapshot()
assert before == after, "Existing table count/fingerprint changed; investigate."
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT COUNT(*) FROM subledgers_writeoffproposal WHERE corrects_id IS NOT NULL"
    )
    linked = cursor.fetchone()[0]
with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM subledgers_writeoffcorrection")
    corrections = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM subledgers_writeoffdecision WHERE authority_evidence <> '{}'::jsonb"
    )
    decisions = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM subledgers_writeoffreversal WHERE authority_evidence <> '{}'::jsonb"
    )
    reversals = cursor.fetchone()[0]
assert corrections == decisions == reversals == 0
assert linked == 0, "No inferred source pairing or backfill is authorized."
result = {
    "authority": "HUMAN-CEP044-PERSISTENCE-20261019 + HUMAN-CEP044-CORRECTION-20261019",
    "date": "2026-10-19",
    "environment": "Configured loopback Development PostgreSQL / Psycopg3 only",
    "operation": "MigrationExecutor.migrate(subledgers0008); additive authority JSON fields and immutable correction-set table; no data migration or post-migrate catalog bootstrap",
    "preexisting_tables_verified": len(before),
    "before": before,
    "after": after,
    "all_preexisting_columns_counts_and_sha256_unchanged": True,
    "new_source_links": linked,
    "new_corrections_decisions_reversals": [corrections, decisions, reversals],
    "existing_history_grants_and_audit_preserved": True,
    "production": False,
}
path = ROOT / "docs/governance/cep/evidence/CEP-044_DEVELOPMENT_ACTIONS_MIGRATION.json"
path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(
    json.dumps(
        {"migration": TARGET, "preserved_tables": len(before), "new_links": linked}
    )
)
