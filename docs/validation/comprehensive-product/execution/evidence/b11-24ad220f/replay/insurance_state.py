from sweep import *
from apps.contracts.services import create_contract_term_version
from django.utils import timezone
actors,s=load_fixtures();u,o=actors['billing'];contract=s['billing-contract']
term=create_contract_term_version(organization=o,actor=u,contract=contract,effective_from=timezone.localdate(),reason='نسخه پیش‌نویس آزمون رابط')
proc,origin,log=host();out={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  page,r=run.get('billing',reverse('contracts:detail',args=[contract.pk])+'?pane=terms');assert r.status==200
  action=reverse('contracts:term_insurance_select',args=[contract.pk,term.pk]);form=page.locator(f'main form[action="{action}"]');assert form.count()==1
  out={'status':r.status,'path':urlsplit(page.url).path+'?pane=terms','widths':run.bounds(page),'controls':form.aria_snapshot(),'business_scope':'Draft control inspection only. No classification or statutory rate activation.'}
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('insurance-source-ui.json',out)
