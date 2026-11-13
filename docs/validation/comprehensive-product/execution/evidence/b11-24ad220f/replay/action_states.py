from sweep import *
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from apps.procurement.services import create_purchase_request,add_purchase_request_item
from apps.procurement.rfq_services import create_rfq,add_rfq_line,submit_rfq_for_issue
from apps.procurement.models import PurchaseOrder,GoodsReceipt
from apps.inventory.models import StockTransaction
from apps.equipment.p8_models import EquipmentUsageLog,EquipmentCostPolicyVersion,EquipmentCostRate,EquipmentCostAllocation,EquipmentCostSourceEnvelope
actors,s=load_fixtures();u,o=actors['ops'];ruser,ro=actors['rfq'];out={}
from apps.procurement.models import PurchaseRequest,RequestForQuotation
if not PurchaseRequest.objects.filter(organization=o,request_number='B11-UI-DRAFT').exists():
 with transaction.atomic():
  req=create_purchase_request(organization=o,actor=u,project=s['ops-project'],request_number='B11-UI-DRAFT',title='درخواست آماده آزمون رابط')
  item=add_purchase_request_item(organization=o,actor=u,purchase_request=req,material=s['order'].items.first().material,quantity=Decimal('1'))
  base=s['rfq']
  rfq=create_rfq(organization=ro,actor=ruser,project=base.project,purchase_request=base.purchase_request,rfq_number='B11-UI-DRAFT',title='استعلام آزمون رابط',closing_at=timezone.now()+timedelta(days=1),earliest_opening_at=timezone.now()+timedelta(days=2))
  add_rfq_line(organization=ro,actor=ruser,rfq=rfq,purchase_request_item=base.purchase_request.items.first(),quantity=Decimal('1'))
  # View-only factories reuse persisted usage context. They do not exercise posting or cost calculation.
  usage=EquipmentUsageLog.objects.filter(organization=o).first();assert usage
  policy=EquipmentCostPolicyVersion.objects.create(organization=o,code='B11-UI-ONLY',version=1,status='published',effective_from=usage.started_at.date(),monetary_policy_code='accounting-money-precision',monetary_policy_version='v1',prepared_by=u)
  rate=EquipmentCostRate.objects.create(organization=o,policy=policy,equipment=usage.equipment,rate_amount=1,component_snapshot={'ui_fixture':'1'},effective_from=usage.started_at.date(),prepared_by=u)
  allocation=EquipmentCostAllocation(organization=o,usage=usage,rate=rate,project=usage.deployment.project,site=usage.deployment.site,measure=1,rate_snapshot=1,amount=1,source_key='B11-UI-ONLY',prepared_by=u);allocation.full_clean();allocation.save()
  envelope=EquipmentCostSourceEnvelope(organization=o,allocation=allocation,occurrence_key='B11-UI-ONLY',source_amount=1,prepared_by=u);envelope.full_clean();envelope.save()
else:
 req=PurchaseRequest.objects.get(organization=o,request_number='B11-UI-DRAFT')
 rfq=RequestForQuotation.objects.get(organization=ro,rfq_number='B11-UI-DRAFT')
 allocation=EquipmentCostAllocation.objects.get(organization=o,source_key='B11-UI-ONLY')
 envelope=EquipmentCostSourceEnvelope.objects.get(allocation=allocation)
order=PurchaseOrder.objects.filter(organization=o,status='draft').first();receipt=GoodsReceipt.objects.filter(organization=o,status='draft').first();stock=StockTransaction.objects.filter(organization=o,status='draft').first()
proc,origin,log=host()
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  def observe(name,actor,path,actions=()):
   page,response=run.get(actor,path);assert response.status==200
   for detail in page.locator('main details').all():detail.evaluate('(e)=>e.open=true')
   bounds=run.bounds(page)
   controls=page.locator('main form[action]').evaluate_all('(es)=>es.map(e=>({action:new URL(e.action).pathname,buttons:[...e.querySelectorAll("button")].map(b=>b.innerText.trim()),confirm:e.dataset.confirmTitle||null}))')
   out[name]={'actor':actor,'path':path,'status':response.status,'widths':bounds,'controls':controls}
   assert all(x['scrollWidth']<=x['width']+1 for x in bounds)
   out[name]['required_controls_found']={action:any(c['action'].endswith(action) for c in controls) for action in actions}
   return page
  observe('request-draft','ops',reverse('procurement:request_detail',args=[req.pk]),('/items/','/cancel/'))
  observe('order-draft','ops',reverse('procurement:order_detail',args=[order.pk]),('/items/','/issue/','/cancel/'))
  observe('receipt-draft','ops',reverse('procurement:receipt_detail',args=[receipt.pk]),('/items/','/post/'))
  observe('transaction-draft','ops',reverse('inventory:transaction_detail',args=[stock.pk]),('/post/',))
  observe('rfq-draft','rfq',reverse('procurement:rfq_detail',args=[rfq.pk]),('/lines/','/submit/'))
  if rfq.status=='draft':submit_rfq_for_issue(organization=ro,actor=ruser,rfq=rfq)
  observe('rfq-submitted','rfq',reverse('procurement:rfq_detail',args=[rfq.pk]),('/issue/',))
  observe('equipment-reversal','ops',reverse('equipment:cost_allocation_reverse',args=[allocation.pk]))
  observe('equipment-reconciliation','ops',reverse('equipment:cost_handoff_reconcile',args=[envelope.pk]))
  observe('materials-actions','ops','/materials/governance/?material='+str(s['order'].items.first().material_id),('/actions/alias/',))
  observe('parties-actions','ops',reverse('parties:governance_detail',args=[s['order'].supplier_id]),('/actions/alias/',))
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('action-state-views.json',out)
print('Positive source control pages',len(out))


