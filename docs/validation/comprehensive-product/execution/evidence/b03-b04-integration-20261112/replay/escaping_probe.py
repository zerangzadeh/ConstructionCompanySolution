import importlib, json
from pathlib import Path
import django
django.setup()
from django.db import connection

root = Path(__file__).resolve().parent
with connection.cursor() as cursor:
    cursor.execute("SELECT current_database(),inet_server_port(),current_setting('data_directory')")
    name, port, directory = cursor.fetchone()
assert name == 'integration_frozen' and str(port) == (root/'db-port.txt').read_text()
assert Path(directory).resolve() == root/'pg'
migration = importlib.import_module('apps.daily_reports.migrations.0009_revision_guards')
results = {}
for label in ('REPORT','ENTRIES'):
    sql = getattr(migration,label)
    try:
        with connection.schema_editor(collect_sql=True, atomic=False) as editor:
            editor.execute(sql)  # Exact previous default: params=(). No SQL mutation.
    except Exception as exc:
        assert type(exc).__name__ == 'ProgrammingError' and "got '%R'" in str(exc)
        results[label] = {'original_error':f'{type(exc).__module__}.{type(exc).__name__}: {exc}'}
    else:
        raise AssertionError('Original interpolation failure not reproduced')
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        editor.execute(sql, params=None)
        assert editor.collected_sql == [sql + ('' if sql.rstrip().endswith(';') else ';')]
        assert 'daily_reports_dailyreport%ROWTYPE' in editor.collected_sql[0]
    results[label]['corrected_sql_unchanged'] = True
print(json.dumps(results, indent=2))
