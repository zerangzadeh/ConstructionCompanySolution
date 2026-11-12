import json
from datetime import date
from common import *
from django.apps import apps
from django.db.migrations.executor import MigrationExecutor
from apps.audit.models import AuditEvent
from apps.daily_reports.models import DailyReport,DailyReportLaborEntry,DailyReportStatus
from apps.daily_reports.field_models import FieldDownstreamProposal
from apps.daily_reports.workflow import COMPATIBILITY_CONFIGURATION
guard(readonly=True)
cfg=json.loads((root/db/"actors.json").read_text())
targets=json.loads((root/db/"targets.json").read_text())
org=cfg["ids"]["org"]
executor=MigrationExecutor(connection)
assert len(executor.loader.applied_migrations)==457
assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
def audit(pk):
    return list(AuditEvent.objects.filter(organization_id=org,entity_id=str(pk)).order_by("created_at").values("id","action","actor__username","created_at","correlation_id","metadata"))
reports=[]
for d in (1,2,3):
    report=DailyReport.objects.get(organization_id=org,site_id=cfg["ids"]["site"],reporting_date=date(2026,9,d))
    entries=list(report.labor_entries.order_by("created_at"))
    assert report.status=="approved" and report.created_by_id!=report.approved_by_id and len(entries)==2
    assert len([a for a in audit(report.pk) if a["action"]=="daily_report.approved"])==1
    for entry in entries:
        assert len(audit(entry.pk))==1
    reports.append({"id":report.pk,"status":report.status,"created_by":report.created_by_id,"approved_by":report.approved_by_id,"audit":audit(report.pk),"entries":[{"id":e.pk,"team":e.team_name,"worker_count":e.worker_count,"hours":e.hours_worked,"audit":audit(e.pk)} for e in entries]})
proposals=[]
for i,pk in enumerate(targets["proposals"][:6]+json.loads((root/db/"review-delta.json").read_text())):
    p=FieldDownstreamProposal.objects.get(pk=pk,organization_id=org)
    expected="accepted" if i%2==0 else "rejected"
    assert p.status==expected and p.created_by_id!=p.reviewed_by_id and p.submitted_by_id!=p.reviewed_by_id
    transitions=list(p.transitions.order_by("created_at").values())
    assert len(transitions)==2 and transitions[0]["proposal_hash"]==transitions[1]["proposal_hash"]==p.proposal_hash
    assert p.source_canonical_hash==p.observation.canonical_hash
    assert len([a for a in audit(p.pk) if a["action"]=="field_proposal."+expected])==1
    if expected=="rejected": assert transitions[1]["reason"]
    proposals.append({"id":p.pk,"status":p.status,"created_by":p.created_by_id,"submitted_by":p.submitted_by_id,"reviewed_by":p.reviewed_by_id,"source_hash":p.source_canonical_hash,"proposal_hash":p.proposal_hash,"transitions":transitions,"audit":audit(p.pk)})
result={"database":db,"port":(root/"db-port.txt").read_text().strip(),"migrations_applied":457,"pending":0,"daily_reports":reports,"proposals":proposals,"daily_report_statuses":DailyReportStatus.values,"current_compatibility_transitions":COMPATIBILITY_CONFIGURATION["transitions"]}
(root/db/"evidence"/"persisted-state-final.json").write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2),encoding="utf-8")
print("PostgreSQL witness PASS: 3 independent approvals; 6 labor rows/6 receipts; 6 accepted + 6 reasoned rejected proposals/24 retained transitions; 457 unchanged migrations")

