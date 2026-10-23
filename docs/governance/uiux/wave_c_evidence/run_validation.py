"""Disposable PostgreSQL checks, with exact effective-entry replay on request."""
import importlib.abc
import importlib.util
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]

class EntryLoader(importlib.abc.Loader):
    def create_module(self,spec):
        return None

    def exec_module(self,module):
        source=OUT/'entry_sources'/Path(*module.__name__.split('.')).with_suffix('.py')
        exec(compile(source.read_bytes(),module.__file__,'exec'),module.__dict__)

class EntryFinder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in ('apps.inventory.p8_views','apps.accounting.views'):
            source=ROOT/Path(*fullname.split('.')).with_suffix('.py')
            return importlib.util.spec_from_file_location(fullname,source,loader=EntryLoader())

if __name__=='__main__':
    os.chdir(ROOT)
    sys.path.insert(0,str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
    arguments=sys.argv[1:]
    entry='--entry' in arguments
    if entry:
        arguments.remove('--entry')
        sys.meta_path.insert(0,EntryFinder())
    with TemporaryDirectory(prefix='bonira-wave-c-test-') as storage:
        os.environ['DOCUMENT_PROTECTED_ROOT']=storage
        import django
        django.setup()
        from django.conf import settings
        from django.contrib.auth.hashers import reset_hashers
        assert settings.SETTINGS_MODULE=='config.settings.development'
        assert settings.DATABASES['default']['HOST'] in ('localhost','127.0.0.1','::1')
        settings.DATABASES['default']['TEST']['NAME']='test_bonira_uiux_batch09'
        settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
        reset_hashers(setting='PASSWORD_HASHERS')
        if entry:
            settings.TEMPLATES[0]['DIRS']=[OUT/'entry_sources/templates',OUT/'entry_sources/apps/accounting/templates',OUT/'entry_sources/apps/subledgers/templates',*settings.TEMPLATES[0]['DIRS']]
        import pytest
        sys.exit(pytest.main(arguments))
