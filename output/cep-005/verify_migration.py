"""Bounded non-production migration verification; emits hashes, never audit contents."""
import os
import sys
import hashlib
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from apps.audit.models import AuditAction, AuditEvent
from apps.projects.models import ProjectCostFact, ProjectCostSourceContract
assert settings.DEBUG and connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1','')

def snapshot():
 result = {}
 for model in (AuditEvent, ProjectCostFact, ProjectCostSourceContract):
  rows=list(model.objects.order_by('pk').values())
  digest=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
  result[model.__name__]={'count':len(rows),'sha256':digest}
 return result

before=snapshot()
print('BEFORE',json.dumps(before,sort_keys=True),flush=True)
call_command('migrate','audit','0053',verbosity=1,interactive=False)
assert not MigrationRecorder(connection).migration_qs.filter(app='audit',name='0054_cep005_integration_attempt_action').exists()
assert snapshot()==before
print('REVERSE: PASS; all inspected audit/fact/contract rows unchanged',flush=True)
call_command('migrate','audit','0054',verbosity=1,interactive=False)
assert snapshot()==before
assert AuditAction.values.count('project_cost.integration_attempt')==1
print('REAPPLY: PASS; unchanged rows; exactly one action identity; model-state only',flush=True)
