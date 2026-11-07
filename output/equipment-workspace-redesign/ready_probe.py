import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT datname FROM pg_database WHERE datname IN ('test_bonira_module_selector_clone_20261103','test_bonira_b1_warehouse_20261104','test_bonira_mvp07_20261103')")
    print(c.fetchall())
