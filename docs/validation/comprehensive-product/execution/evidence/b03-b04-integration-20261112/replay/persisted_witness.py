import json
from common import root,guard
from django.apps import apps
from django.db import connection
from apps.daily_reports.submission_snapshots import verify_submission
guard(readonly=True)
cfg=json.loads((root/'actors.json').read_text(encoding='utf-8'))
Daily=apps.get_model('daily_reports','DailyReport')
first=Daily.objects.get(pk=cfg['ids']['report'])
second=Daily.objects.get(previous_revision=first)
verify_submission(first);verify_submission(second)
assert first.status=='returned' and second.status=='approved'
assert first.submission_hash==cfg['ids']['hash'] and first.submission_hash!=second.submission_hash
assert first.labor_entries.get().worker_count==2 and second.labor_entries.get().worker_count==3
assert second.approved_by_id!=second.created_by_id
data={'daily_reports':list(Daily.objects.filter(pk__in=[first.pk,second.pk]).order_by('revision_number').values('id','previous_revision_id','revision_number','status','submission_hash','created_by_id','approved_by_id')),'labor_counts':{'original':2,'correction':3}}
for app,name in [('safety','SafetyIncident'),('quality','QualityIssue')]:
    record=apps.get_model(app,name).objects.get(pk=cfg['records'][app]['id'])
    assert record.review_status=='approved' and record.status==cfg['records'][app]['status']
    revisions=list(record.review_revisions.order_by('sequence').values('state','actor_id','reason','previous_id'))
    assert len(revisions)==2 and revisions[0]['actor_id']!=revisions[1]['actor_id']
    data[app]={'id':record.pk,'operational_status':record.status,'formal_status':record.review_status,'revisions':revisions}
usage=apps.get_model('equipment','EquipmentUsageLog').objects.get(evidence_reference='GATE-CHROME-USAGE')
assert usage.runtime_hours==2 and usage.deployment_id and usage.operator_id
data['equipment']={'id':usage.pk,'deployment_id':usage.deployment_id,'operator_id':usage.operator_id,'started_at':usage.started_at,'ended_at':usage.ended_at,'runtime_hours':usage.runtime_hours,'source_key':usage.source_key}
data['audit']=list(apps.get_model('audit','AuditEvent').objects.filter(entity_id__in=[str(first.pk),str(second.pk),str(usage.pk),cfg['records']['safety']['id'],cfg['records']['quality']['id']]).order_by('created_at').values('action','entity_id','actor_id'))
with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname LIKE 'bonira_daily_revision%' AND tgenabled='O'")
    assert cursor.fetchone()[0]==8
data['enabled_revision_triggers']=8
(root/'persisted-witness.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print('PASS: retained sealed original, independently approved successor, formal Safety/Quality approvals with unchanged operational state, qualified 2-hour usage, 8 enabled revision triggers.')
