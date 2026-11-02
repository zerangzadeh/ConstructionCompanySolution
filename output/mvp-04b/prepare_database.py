import os,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner
name='test_mvp04b_'+uuid4().hex[:10]
Path('output/mvp-04b/database-name.txt').write_text(name,encoding='utf-8')
settings.DATABASES['default'].setdefault('TEST',{})['NAME']=name
print('Preparing isolated PostgreSQL database',name,flush=True)
runner=DiscoverRunner(verbosity=1,interactive=False,keepdb=True)
runner.setup_test_environment()
configuration=runner.setup_databases()
runner.teardown_databases(configuration)
runner.teardown_test_environment()
print('Isolated migrated database ready for bounded validation.',flush=True)
