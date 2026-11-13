import json,os
from pathlib import Path
import psycopg
from psycopg import sql
root=Path(__file__).resolve().parent;out=root.parents[1]/'output/project-detail-ui-remediation/evidence'
result={}
for database in ['project_ui_original','project_ui_retest']:
 with psycopg.connect(host='127.0.0.1',port=int((root/'port.txt').read_text()),user='b11_local',dbname=database) as conn:
  with conn.cursor() as c:
   c.execute('SET TRANSACTION READ ONLY')
   c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'projects_%' OR tablename LIKE 'equipment_%' OR tablename LIKE 'expenses_%' OR tablename LIKE 'contracts_%' OR tablename LIKE 'daily_reports_%' OR tablename LIKE 'documents_%') ORDER BY tablename")
   tables=[row[0] for row in c.fetchall()];business={}
   for table in tables:
    c.execute(sql.SQL("SELECT count(*),md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) FROM {} t").format(sql.Identifier(table)))
    count,digest=c.fetchone();business[table]={'rows':count,'digest':digest}
   c.execute("select count(*) from django_migrations");applied=c.fetchone()[0]
   result[database]={'tables':business,'applied_migrations':applied}
assert result['project_ui_original']==result['project_ui_retest'],'Business source changed between baseline clone and final read verification'
(out/'business-preservation.json').write_text(json.dumps({'result':'PASS','tables_compared':len(tables),'business_sources_identical':True,'databases':result},indent=2)+'\n')
print('Business tables preserved:',len(tables),'Migration records:',applied)
