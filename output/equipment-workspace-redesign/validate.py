import os,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.db import connection
from psycopg import sql
name='test_bonira_equipment_workspace_final_20261105'
with connection.cursor() as c:
    c.execute('SELECT 1 FROM pg_database WHERE datname=%s',[name])
    if c.fetchone() is None:
        c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(name),sql.Identifier('test_bonira_module_selector_clone_20261103')))
connection.settings_dict['TEST']['NAME']=name
import pytest
raise SystemExit(pytest.main(['tests/test_equipment_operations_workspace.py','tests/test_mvp07_xlsx.py::P1ExportTests::test_equipment_operational_sources_and_filters','--reuse-db','-q','--tb=short','--junitxml=output/equipment-workspace-redesign/focused-tests.xml']))
