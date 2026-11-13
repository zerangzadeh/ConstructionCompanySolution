"""Independent read-only PostgreSQL witness for completed Chrome journeys."""
import hashlib
import json
from pathlib import Path

from runtime_common import root, guard
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

guard(readonly=True)
chrome=json.loads((root/"chrome-accepted/results.json").read_text(encoding="utf-8"))
assert len(chrome["journeys"])==3
reports=[]
with connection.cursor() as cursor:
    cursor.execute("SELECT current_database(), inet_server_port(), current_setting('data_directory')")
    identity=cursor.fetchone()
    assert identity[0]=="b03_return_ui"
    for journey in chrome["journeys"]:
        original=journey["source"]
        successor=journey["successor"]
        pair=[]
        for expected in (original,successor):
            cursor.execute("""
                SELECT id, previous_revision_id, revision_number, edit_version, status,
                       created_by_id, approved_by_id, submission_snapshot, submission_hash,
                       submitted_at, approved_at
                FROM daily_reports_dailyreport WHERE id=%s
            """,[expected["id"]])
            row=cursor.fetchone()
            names=[col.name for col in cursor.description]
            data=dict(zip(names,row))
            snapshot=json.loads(data["submission_snapshot"]) if isinstance(data["submission_snapshot"],str) else data["submission_snapshot"]
            payload=json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
            assert hashlib.sha256(payload).hexdigest()==data["submission_hash"]==expected["hash"]
            assert data["status"]==expected["status"]
            counts={}
            for table,key in (
                ("dailyreportlaborentry","labor"),("dailyreportequipmententry","equipment"),
                ("dailyreportmaterialentry","materials"),("dailyactivity","activities"),("delayevent","delays"),
            ):
                cursor.execute(f"SELECT count(*) FROM daily_reports_{table} WHERE report_id=%s",[expected["id"]])
                counts[key]=cursor.fetchone()[0]
                assert counts[key]==len(snapshot["entries"][key])==1
            cursor.execute("""
                SELECT event.action, event.actor_id, event.created_at, event.metadata
                FROM audit_auditevent event WHERE entity_type='daily_report' AND entity_id=%s
                ORDER BY created_at
            """,[expected["id"]])
            audit=cursor.fetchall()
            decision="daily_report.returned" if data["status"]=="returned" else "daily_report.approved"
            decisions=[event for event in audit if event[0]==decision]
            assert len(decisions)==1 and decisions[0][1] != data["created_by_id"]
            metadata=json.loads(decisions[0][3]) if isinstance(decisions[0][3],str) else decisions[0][3]
            assert metadata["submission_hash"]==data["submission_hash"]
            if data["status"]=="returned":assert metadata["reason"]=="اصلاح شرح و ردیف‌های گزارش"
            cursor.execute("""
                SELECT wi.id, wi.status, wi.completion_outcome, instance.id, instance.version_id,
                       instance.status, wi.current_assignee_id
                FROM workflows_workitem wi
                JOIN workflows_workflowinstance instance ON instance.id=wi.instance_id
                WHERE instance.subject_id=%s AND instance.subject_type='daily_reports.daily_report'
            """,[expected["id"]])
            work=cursor.fetchall()
            assert len(work)==1 and work[0][1:3]==("completed",data["status"]) and work[0][5]=="completed"
            pair.append({
                **{k:v for k,v in data.items() if k!="submission_snapshot"},
                "counts":counts,"snapshot_bytes":len(payload),"audit":audit,"work":work,
                "submitter_id":snapshot["submitter_id"],"creator_membership_id":snapshot["creator_membership_id"],
            })
        assert str(pair[1]["previous_revision_id"])==str(pair[0]["id"])
        assert pair[1]["work"][0][0] != pair[0]["work"][0][0]
        assert pair[0]["revision_number"]==1 and pair[1]["revision_number"]==2
        assert pair[1]["approved_by_id"] != pair[1]["created_by_id"]
        reports.append({"width":journey["width"],"revisions":pair})
    cursor.execute("""
        SELECT count(*) FROM organizations_organizationrole_permissions grants
        JOIN organizations_businesspermission permission ON grants.businesspermission_id=permission.id
        JOIN organizations_organizationrole role ON grants.organizationrole_id=role.id
        WHERE role.organization_id IS NULL AND permission.code='daily_reports.correct'
    """)
    assert cursor.fetchone()[0]==0
    cursor.execute("SELECT tgname FROM pg_trigger WHERE tgname LIKE 'bonira_daily_revision_%' AND NOT tgisinternal ORDER BY tgname")
    triggers=[r[0] for r in cursor.fetchall()]
    assert len(triggers)==8
    cursor.execute("""
        SELECT app,name,applied FROM django_migrations
        WHERE (app='daily_reports' AND name IN ('0008_daily_report_return','0009_revision_guards'))
        OR (app='organizations' AND name='0130_daily_report_correction_permission')
        OR (app='audit' AND name='0060_daily_report_return')
        OR (app='workflows' AND name='0028_daily_report_return_catalog')
        ORDER BY app,name
    """)
    migrations=cursor.fetchall()
    assert len(migrations)==5
executor=MigrationExecutor(connection)
assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
result={
    "identity":identity,"migrations":migrations,"pending_migrations":0,
    "applied_migration_count":len(executor.loader.applied_migrations),"triggers":triggers,
    "default_correction_grants":0,"journeys":reports,
}
(root/"persisted-state.json").write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2),encoding="utf-8")
print("SQL witness PASS: three immutable source/successor pairs, 30 entry rows, six completed independent decisions, five migrations, zero pending and zero default correction grants.")

