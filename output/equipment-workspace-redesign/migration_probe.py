import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.db import connection
import psycopg
for name in ('test_bonira_equipment_workspace_20261105', 'test_bonira_equipment_workspace_ui_20261105'):
    params=connection.get_connection_params()
    params['dbname']=name
    with psycopg.connect(**params) as probe:
        with probe.cursor() as cursor:
            cursor.execute('SELECT app, name FROM django_migrations ORDER BY applied DESC LIMIT 3')
            print(name, cursor.fetchall())
