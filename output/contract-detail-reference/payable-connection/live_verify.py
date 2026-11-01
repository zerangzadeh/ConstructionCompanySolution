"""Read-only installed Chrome verification of the user's existing seeded contract."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
from django.test import Client
from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.organizations.services import set_active_organization
from apps.billing.models import PayableCertificate,PayableMeasurement

assert settings.DEBUG and settings.SETTINGS_MODULE=='config.settings.development'
c=Contract.objects.select_related('organization').get(pk='23737c99-9249-41e5-a866-8c78867b10e9',organization__slug='demo-construction-02',contract_number='UAT-SUB-02-03')
def fingerprint():
 data={'contract':Contract.objects.filter(pk=c.pk).values().get(),'certificates':list(PayableCertificate.objects.filter(contract=c).order_by('pk').values()),'measurements':list(PayableMeasurement.objects.filter(contract=c).order_by('pk').values())}
 return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
before=fingerprint()
actor=User.objects.get(username='account.demo-construction-02.owner',is_active=True)
client=Client(HTTP_HOST='localhost')
client.force_login(actor)
session=client.session
set_active_organization(session,c.organization)
session.save()
expression="document.querySelectorAll('.cd-claims tbody tr').length===3 && Chart.getChart('contract-financial-chart').data.datasets.map(d=>d.data[0]).join(',')==='8910000000,4455000000,16335000000' && document.querySelector('progress').value===30 && [...document.querySelectorAll('.cd-claims tbody a')].every(a=>a.href.includes('/billing/payable-certificates/')) && ![...document.querySelectorAll('.contract-detail a')].some(a=>/billing\\/(claims|baselines)/.test(a.href))"
base={'status':200,'screenshot':True,'noJsErrors':True,'noHttpErrors':True,'mustText':['آخرین صورت‌وضعیت‌های پرداختنی']}
scenarios=[{**base,'name':'live-capture','path':f'/contracts/{c.pk}/'}]+[{**base,'name':'live-payable-'+str(width),'path':f'/contracts/{c.pk}/','mobile':width==390,'steps':[{'inspect':check,'description':label} for label,check in [('rows',"document.querySelectorAll('.cd-claims tbody tr').length===3"),('chart amounts',"!!window.Chart && !!Chart.getChart('contract-financial-chart') && Chart.getChart('contract-financial-chart').data.datasets.map(d=>d.data[0]).join(',')==='8910000000,4455000000,16335000000'"),('progress ratio',"document.querySelector('progress')?.value===30"),('payable links',"[...document.querySelectorAll('.cd-claims tbody a')].every(a=>a.href.includes('/billing/payable-certificates/'))"),('no receivable links',"![...document.querySelectorAll('.contract-detail a')].some(a=>/billing\\/(claims|baselines)/.test(a.href))")]]} for width in (1440,390)]
env=os.environ.copy()
env['MVP02_SESSION']=client.cookies['sessionid'].value
env['MVP02_SCENARIOS']=json.dumps(scenarios)
result=subprocess.run(['node',str(ROOT/'scripts/verification/mvp02_browser.mjs'),'http://127.0.0.1:8000',str(Path(__file__).resolve().parent/'live-browser'),'seed-owner'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=180)
if result.returncode:
 print((result.stderr or result.stdout)[-3000:],flush=True)
 raise SystemExit(result.returncode)
rows=json.loads(result.stdout)
assert before==fingerprint()
summary={'scenarios':[{'name':r['name'],'status':r['status'],'width':r['width'],'scroll':r['scroll'],'jsErrors':r['jsErrors'],'httpErrors':r['httpErrors']} for r in rows],'business_data_before':before,'business_data_after':fingerprint(),'business_records_unchanged':True}
(Path(__file__).resolve().parent/'live-verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary),flush=True)
