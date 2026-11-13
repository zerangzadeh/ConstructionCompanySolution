from sweep import *
from apps.procurement.models import GoodsReceipt
from apps.procurement.services import create_goods_receipt,post_goods_receipt
from django.utils import timezone
actors,s=load_fixtures();u,o=actors['ops'];first=GoodsReceipt.objects.get(organization=o,receipt_number='B11-UI-RECEIPT')
empty=create_goods_receipt(organization=o,actor=u,purchase_order=first.purchase_order,receipt_number='B11-UI-EMPTY',received_at=timezone.now())
post_goods_receipt(organization=o,actor=u,goods_receipt=first)
proc,origin,log=host();out={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  for name,obj,action in [('empty',empty,'/items/'),('posted',first,'/void/')]:
   page,r=run.get('ops',reverse('procurement:receipt_detail',args=[obj.pk]));assert r.status==200
   page.locator('main details').evaluate_all('(es)=>es.forEach(e=>e.open=true)')
   forms=page.locator('main form').evaluate_all('(es)=>es.map(e=>({path:new URL(e.action).pathname,buttons:[...e.querySelectorAll("button")].map(x=>x.innerText.trim())}))')
   out[name]={'path':urlsplit(page.url).path,'status':r.status,'widths':run.bounds(page),'forms':forms}
   assert any(f['path'].endswith(action) for f in forms),action
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('receipt-state-retest.json',out)
