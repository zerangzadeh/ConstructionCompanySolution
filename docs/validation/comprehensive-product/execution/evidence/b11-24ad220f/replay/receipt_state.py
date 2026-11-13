from sweep import *
from django.db import transaction
from decimal import Decimal
from django.utils import timezone
from apps.procurement.services import create_purchase_order,add_purchase_order_item,issue_purchase_order,create_goods_receipt,add_goods_receipt_item
actors,s=load_fixtures();u,o=actors['ops']
with transaction.atomic():
 order=create_purchase_order(organization=o,actor=u,project=s['ops-project'],supplier=s['order'].supplier,order_number='B11-UI-RECEIPT',order_date=timezone.localdate())
 item=add_purchase_order_item(organization=o,actor=u,purchase_order=order,material=s['order'].items.first().material,quantity=Decimal('2'),unit_price=Decimal('1'))
 issue_purchase_order(organization=o,actor=u,purchase_order=order)
 receipt=create_goods_receipt(organization=o,actor=u,purchase_order=order,receipt_number='B11-UI-RECEIPT',received_at=timezone.now())
 add_goods_receipt_item(organization=o,actor=u,goods_receipt=receipt,purchase_order_item=item,quantity=Decimal('1'))
proc,origin,log=host();out={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  page,r=run.get('ops',reverse('procurement:receipt_detail',args=[receipt.pk]));assert r.status==200
  page.locator('main details').evaluate_all('(es)=>es.forEach(e=>e.open=true)')
  out={'status':r.status,'path':urlsplit(page.url).path,'widths':run.bounds(page),'forms':page.locator('main form').evaluate_all('(es)=>es.map(e=>({path:new URL(e.action).pathname,buttons:[...e.querySelectorAll("button")].map(x=>x.innerText.trim())}))')}
  assert all(any(f['path'].endswith(a) for f in out['forms']) for a in ['/items/','/post/','/void/'])
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('receipt-state-views.json',out)
