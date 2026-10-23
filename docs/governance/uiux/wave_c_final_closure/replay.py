"""Reproduce exact ten debt cases against current source or immutable HEAD export."""
import hashlib, io, json, os, subprocess, sys, tempfile, zipfile
import importlib.abc
import importlib.util
from pathlib import Path
OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[3]
mode=sys.argv[1]
if mode=='frozen':
    root=Path(tempfile.mkdtemp(prefix='bonira-wave-c-head-'))
    data=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(data)) as archive: archive.extractall(root)
    # Read local configuration in memory; never write secrets into evidence/export.
    sys.path.insert(0,str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    sys.path.pop(0)
    (OUT/'FROZEN_SOURCE.json').write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'archive_sha256':hashlib.sha256(data).hexdigest(),'path':str(root),'git_metadata':False,'purpose':'Read-only HEAD export for isolated baseline replay; no branch/worktree/index mutation'},indent=2)+'\n')
else: root=ROOT
os.chdir(root); sys.path.insert(0,str(root))
if mode=='entry_before':
    class SavedEntryLoader(importlib.abc.Loader):
        def create_module(self,spec): return None
        def exec_module(self,module):
            source=OUT/'entry_sources'/Path(*module.__name__.split('.')).with_suffix('.py')
            exec(compile(source.read_bytes(),str(source),'exec'),module.__dict__)
    class SavedEntryFinder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname in {'apps.procurement.test_p5_s08_sealed_custody','apps.subledgers.test_cep033_invoice_handoff'}:
                source=ROOT/Path(*fullname.split('.')).with_suffix('.py')
                return importlib.util.spec_from_file_location(fullname,source,loader=SavedEntryLoader())
    sys.meta_path.insert(0,SavedEntryFinder())

os.environ['DJANGO_SETTINGS_MODULE']='config.settings.development'
os.environ['DOCUMENT_PROTECTED_ROOT']=tempfile.mkdtemp(prefix='bonira-wave-c-test-files-')
import django
django.setup()
from django.conf import settings
assert settings.DEBUG and settings.DATABASES['default']['HOST'] in ('localhost','127.0.0.1','::1')
settings.DATABASES['default']['TEST']['NAME']=('test_bonira_uiux_batch09' if mode.startswith('fixed') or (mode.startswith('affected') or mode=='entry_before') else 'test_bonira_wc_closure_'+mode)
settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
from django.contrib.auth.hashers import reset_hashers
reset_hashers(setting='PASSWORD_HASHERS')
if mode=='entry_before':
    import importlib
    for name in ['apps.procurement.test_p5_s08_sealed_custody','apps.subledgers.test_cep033_invoice_handoff']:
        sys.modules.pop(name,None)
        importlib.import_module(name)
if len(sys.argv)>2:
    selected=sys.argv[2:]
else:
    failures=json.loads((OUT.parent/'wave_c_domain_resolution/BASELINE_DEBT.json').read_text())['failures']
    selected=[]
    for row in failures:
        module,cls,test=row['test'].rsplit('.',2)
        if mode=='frozen' and test=='test_payroll_registry_is_complete_and_owner_admin_are_denied':
            test='test_payroll_registry_is_complete_and_default_roles_are_denied'
        if mode.startswith('fixed') and test=='test_reversal_permission_has_no_implicit_system_role_grants':
            test='test_reversal_permission_has_only_reviewed_system_role_grants'
        selected.append(module.replace('.','/')+'.py::'+cls+'::'+test)
import pytest
sys.exit(pytest.main(['-q','--tb=short',*(['--reuse-db'] if mode.startswith('fixed') or (mode.startswith('affected') or mode=='entry_before') else []),'--junitxml='+str(OUT/(mode+'.xml')),*selected]))

