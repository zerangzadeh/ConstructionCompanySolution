import os
from pathlib import Path
import django
django.setup()
from django.db import connection

root = Path(os.environ["B04_TMP"]).resolve()
db = os.environ["B04_DB"]
def guard(readonly=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), inet_server_port(), current_setting('data_directory')")
        name, port, directory = cursor.fetchone()
        assert name == db and str(port) == (root / "db-port.txt").read_text().strip()
        assert Path(directory).resolve() == root / "pg"
        if readonly:
            cursor.execute("SET default_transaction_read_only=on")
        return name, port

if __name__ == "__main__":
    from django.db.migrations.executor import MigrationExecutor
    from django.apps import apps
    name, port = guard(readonly=True)
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
    assert not apps.get_model("accounts.User").objects.exists()
    assert not apps.get_model("organizations.Organization").objects.exists()
    assert apps.get_model("organizations.BusinessPermission").objects.exists()
    print(f"{name} | 127.0.0.1:{port} | {len(executor.loader.applied_migrations)} applied | 0 pending | no tenants/users | catalog loaded")