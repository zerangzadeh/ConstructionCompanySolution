"""Read-only persisted verification for this bounded sample batch."""
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from seed import guard,finance,MARKER,SPECS
from apps.organizations.models import Organization
from apps.contracts.models import Contract
from apps.estimates.models import Estimate
from apps.billing.models import ProgressClaim,ProgressRecord

guard()
root=Path(__file__).resolve().parent
result=json.loads((root/'result.json').read_text(encoding='utf-8'))
org=Organization.objects.get(slug='demo-construction-02')
contracts=list(Contract.objects.filter(organization=org,contract_number__in=[s[0] for s in SPECS]))
assert len(contracts)==3
estimates=list(Estimate.objects.filter(organization=org,contract__in=contracts))
assert len(estimates)==6
for c in contracts:
 assert c.direction=='receivable' and c.contract_type=='client' and c.status=='active' and MARKER in c.notes
 assert c.contract_value==sum((i.line_total for i in c.items.all()),Decimal(0))
 assert c.project_baselines.count()==1
for e in estimates:
 assert e.project_id==e.contract.project_id and e.organization_id==e.contract.organization_id
 assert e.total_amount==sum((i.line_total for i in e.current_revision.items.all()),Decimal(0))
claims=list(ProgressClaim.objects.filter(organization=org,contract__in=contracts))
assert len(claims)==15
for c in claims:
 assert c.project_id==c.contract.project_id and c.baseline.contract_id==c.contract_id
 assert c.net_amount==c.gross_amount+c.adjustment_amount
 assert c.gross_amount==sum((i.current_amount for i in c.items.all()),Decimal(0))
 if c.status=='returned':
  assert c.returned_revision.status=='draft' and c.returned_revision.claim_number==c.claim_number
records=ProgressRecord.objects.filter(organization=org,baseline__contract__in=contracts)
assert records.count()==24 and not records.exclude(status='verified').exists()
assert finance(org)==result['base']['finance_before_after']
summary={'contracts':len(contracts),'estimates':len(estimates),'estimate_statuses':dict(Counter(e.status for e in estimates)),'claims':len(claims),'claim_statuses':dict(Counter(c.status for c in claims)),'verified_progress_records':records.count(),'finance_unchanged':True,'amounts_and_scope_reconciled':True,'pre_existing_business_rows_unchanged':result['pre_existing_business_rows_unchanged'],'http_checks':len(result['http_checks'])}
(root/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))

