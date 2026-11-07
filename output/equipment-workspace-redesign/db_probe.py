import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT datname, state, wait_event_type, wait_event, left(query, 90) FROM pg_stat_activity WHERE datname LIKE 'test_bonira_equipment%'")
    print(cursor.fetchall())
