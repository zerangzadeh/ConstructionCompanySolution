from pathlib import Path
import os,importlib,json,sys
sys.path.insert(0,str(Path.cwd()))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings.development")
import django;django.setup()
from django.apps import apps
from django.db import connection,migrations
from django.conf import settings
from apps.workflows.models import WorkflowTemplate
name="test_"+settings.DATABASES["default"]["NAME"]
connection.close();connection.settings_dict["NAME"]=name
assert connection.settings_dict["NAME"].startswith("test_")
before=WorkflowTemplate.objects.count()
modules=[]
for p in sorted(Path("apps/workflows/migrations").glob("*.py")):
 if p.name[:4] in {"0018","0019","0020"}:
  m=importlib.import_module("apps.workflows.migrations."+p.stem)
  for op in m.Migration.operations:
   if isinstance(op,migrations.RunPython):op.code(apps,None)
  modules.append(p.name)
print(json.dumps({"database":"disposable test PostgreSQL","templates_before":before,"templates_after":WorkflowTemplate.objects.count(),"unchanged_seed_functions":modules,"schema_operations":False,"production":False}))

for prefix in ("0004", "0006"):
 model = apps.get_model("reporting", "ReconciliationPairVersion" if prefix == "0004" else "ProjectCloseoutProfileVersion")
 if model.objects.filter(status="published").exists():
  print("Disposable catalogue already present:", prefix); continue
 p=next(Path("apps/reporting/migrations").glob(prefix+"*.py"))
 m=importlib.import_module("apps.reporting.migrations."+p.stem)
 for op in m.Migration.operations:
  if isinstance(op,migrations.RunPython):op.code(apps,None)
 print("Restored existing disposable Reporting catalogue:",p.name)
