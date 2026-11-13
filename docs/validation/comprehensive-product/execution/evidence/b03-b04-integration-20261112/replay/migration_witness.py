import importlib, json, platform
from common import root, guard
import django, psycopg
import apps as app_package, core, config
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

guard(readonly=True)
executor=MigrationExecutor(connection)
executor.loader.check_consistent_history(connection)
pending=executor.migration_plan(executor.loader.graph.leaf_nodes())
assert not pending
assert not apps.get_model('accounts','User').objects.exists()
assert not apps.get_model('organizations','Organization').objects.exists()
with connection.cursor() as cursor:
    cursor.execute('SELECT version(),current_database(),inet_server_port()')
    server,name,port=cursor.fetchone()
    cursor.execute("SELECT c.relname,t.tgname,t.tgenabled,t.tgdeferrable,t.tginitdeferred,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE NOT t.tgisinternal AND t.tgname LIKE 'bonira_daily_revision%' ORDER BY c.relname,t.tgname")
    triggers=cursor.fetchall()
    cursor.execute("SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.proname LIKE 'bonira_daily_revision%' ORDER BY p.proname")
    functions=dict(cursor.fetchall())
    cursor.execute('SELECT app,name FROM django_migrations ORDER BY app,name')
    applied=cursor.fetchall()
assert len(triggers)==8 and all(row[2]=='O' for row in triggers)
assert len(functions)==3
assert 'daily_reports_dailyreport%ROWTYPE' in functions['bonira_daily_revision_guard']
assert 'daily_reports_dailyreport%ROWTYPE' in functions['bonira_daily_revision_entry_guard']
assert any(row[1]=='bonira_daily_revision_decision_guard' and row[3] and row[4] for row in triggers)
result={'server':server,'database':name,'loopback_port':port,'python':platform.python_version(),'django':django.get_version(),'psycopg':psycopg.__version__,'runtime_source_paths':{key:package.__file__ for key,package in [('apps',app_package),('core',core),('config',config)]},'applied_count':len(applied),'pending':0,'users':0,'organizations':0,'triggers':triggers,'functions':functions,'applied_migrations':applied}
(root/'migration-witness.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(f'PASS: {len(applied)} migrations, zero pending, 8 enabled revision triggers, 3 functions, deferred decision guard, native %ROWTYPE, zero tenants/users.')
