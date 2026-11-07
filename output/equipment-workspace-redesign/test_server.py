import os,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
from django.db import connections
name='test_bonira_equipment_workspace_ready_20261105'
connections.close_all()
settings.DATABASES['default']['NAME']=name
connections['default'].settings_dict['NAME']=name
with connections['default'].cursor() as c:
    c.execute('SELECT current_database()')
    assert c.fetchone()[0]==name
from apps.organizations.models import Organization,OrganizationSettings
OrganizationSettings.objects.get_or_create(organization=Organization.objects.get(slug='b1'),defaults={'timezone':'Asia/Tehran'})
from django.core.management import call_command
call_command('runserver','127.0.0.1:8003',use_reloader=False)
