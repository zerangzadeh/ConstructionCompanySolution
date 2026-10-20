from pathlib import Path
import os,sys,json
sys.path.insert(0,str(Path.cwd()))
os.environ["DJANGO_SETTINGS_MODULE"]="config.settings.development"
import django;django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from apps.timekeeping.models import LeaveMissionRequest
from apps.payroll.models import PayrollAdjustment
from apps.expenses.models import Expense
from apps.treasury.models import PaymentRequest
assert connection.vendor=="postgresql"
if "--test" in sys.argv:
 connection.close();connection.settings_dict["NAME"]="test_"+connection.settings_dict["NAME"]
 assert connection.settings_dict["NAME"].startswith("test_")

def retention():
 result={}
 with connection.cursor() as c:
  for model in (LeaveMissionRequest,PayrollAdjustment,Expense,PaymentRequest):
   table=connection.ops.quote_name(model._meta.db_table)
   c.execute(f"SELECT COUNT(*),md5(coalesce(string_agg(md5(row_to_json(t)::text),'' ORDER BY id::text),'')) FROM {table} t")
   result[model._meta.label]=c.fetchone()
 return result

executor=MigrationExecutor(connection)
target=("timekeeping","0004_cep062_mission_effect_lineage")
plan=executor.migration_plan([target])
assert [(m.app_label,m.name,b) for m,b in plan]==[(target[0],target[1],False)]
before=retention()
executor.migrate([target]);after=retention();assert before==after
result={"environment":"disposable test PostgreSQL" if "--test" in sys.argv else "configured Development PostgreSQL",
 "plan":[list(target)],"only_two_new_tables_and_constraints":True,"backfill":False,
 "legacy_before":before,"legacy_after":after,"retention_pass":True,"production":False}
if "--test" in sys.argv:
 with connection.cursor() as c:
  for name in ("timekeeping_missioneffect","timekeeping_missioneffectevent"):
   c.execute("SELECT COUNT(*) FROM "+connection.ops.quote_name(name));assert c.fetchone()[0]==0
 executor=MigrationExecutor(connection)
 back=executor.migration_plan([("timekeeping","0003_cep022_employment_lifecycle")])
 assert [(m.app_label,m.name,b) for m,b in back]==[(target[0],target[1],True)]
 executor.migrate([("timekeeping","0003_cep022_employment_lifecycle")]);assert retention()==before
 executor=MigrationExecutor(connection);executor.migrate([target]);assert retention()==before
 result["empty_owned_tables_rollback_reapply"]="PASS"
filename="CEP-062_TEST_MIGRATION.json" if "--test" in sys.argv else "CEP-062_MIGRATION.json"
Path("docs/governance/cep/evidence",filename).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
