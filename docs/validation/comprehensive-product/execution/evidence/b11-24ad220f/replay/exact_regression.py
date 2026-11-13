from sweep import *
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.utils import timezone
from core.organization_time import render_in_organization_time
from apps.billing.forms import PayableMeasurementForm,TaxpayerInvoiceForm
actors,s=load_fixtures();result={}
def check(name,fn):
 fn();result[name]='PASS'
def zones():
 request=SimpleNamespace(organization=SimpleNamespace(settings=SimpleNamespace(timezone='UTC')))
 tenant=SimpleNamespace(settings=SimpleNamespace(timezone='Asia/Tehran'))
 with timezone.override(ZoneInfo('Europe/Paris')):
  with patch('core.organization_time.render',side_effect=lambda *a,**k:timezone.get_current_timezone_name()):
   assert render_in_organization_time(request,'x')=='UTC'
   assert render_in_organization_time(request,'x',organization=tenant)=='Asia/Tehran'
   assert timezone.get_current_timezone_name()=='Europe/Paris'
check('explicit-authorized-organization-and-ambient-time-restoration',zones)
def payable():
 u,o=actors['payable'];f=PayableMeasurementForm(organization=o,membership=o.memberships.get(user=u))
 field=f.fields['contract_item'];items=list(field.queryset);assert items
 assert all(x.organization_id==o.pk for x in items)
 assert all('object (' not in field.label_from_instance(x) and str(x.pk) not in field.label_from_instance(x) for x in items)
 assert not PayableMeasurementForm(organization=o).fields['contract_item'].queryset.exists()
 other=actors['billing'][1]
 assert not PayableMeasurementForm(organization=o,membership=other.memberships.first()).fields['contract_item'].queryset.exists()
 f=PayableMeasurementForm({'contract_item':str(items[0].pk),'measured_on':'1405/08/22','period_quantity':'2','cumulative_quantity':'2','evidence_reference':''},organization=o,membership=o.memberships.get(user=u))
 assert not f.is_valid() and 'evidence_reference' in f.errors and f['period_quantity'].value()=='2'
check('payable-labels-scope-deny-default-and-invalid-retention',payable)
def taxpayer():
 u,o=actors['billing'];f=TaxpayerInvoiceForm(organization=o);field=f.fields['source_claim'];items=list(field.queryset);assert items
 assert all(x.organization_id==o.pk and x.status=='approved' for x in items)
 assert all('object (' not in field.label_from_instance(x) and str(x.pk) not in field.label_from_instance(x) for x in items)
 foreign=TaxpayerInvoiceForm(organization=actors['payable'][1])
 assert not foreign.fields['source_claim'].queryset.filter(pk__in=[x.pk for x in items]).exists()
check('taxpayer-business-labels-and-organization-isolation',taxpayer)
proc,origin,log=host()
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  page,response=run.get('field','/equipment/create/');assert response.status==200
  assert page.locator('main').aria_snapshot().count('combobox')==2
  page.locator('[name=category]').evaluate('(e)=>e.tomselect.destroy()')
  field=page.locator('[name=category]');assert field.is_visible()
  print('fallback',field.evaluate('(e)=>({labels:e.labels.length,aria:e.getAttribute("aria-hidden"),html:e.outerHTML})'),flush=True)
  assert field.evaluate('(e)=>e.labels.length')>=1 and field.get_attribute('aria-hidden') in (None,'false')
  result['equipment-enhancement-destroy-restores-native-labeled-fallback']='PASS'
  page,response=run.get('platform','/organizations/platform/member-roles/')
  assert response.status==200
  field=page.locator('select[data-hide-enhanced-source=true]');assert field.count()==1
  assert field.get_attribute('aria-hidden')=='true'
  field.evaluate('(e)=>e.tomselect.destroy()')
  assert field.is_visible() and field.evaluate('(e)=>e.labels.length')==1 and field.get_attribute('aria-hidden') is None
  result['platform-tenant-selector-enhancement-cleanup']='PASS'
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close()
write('exact-regression.json',result)
print(result)
