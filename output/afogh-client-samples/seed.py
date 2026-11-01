"""Bounded Afogh employer samples, ordinary services, local Development only."""
import argparse
import hashlib
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
from django.db import connection,transaction
from apps.accounts.models import User
from apps.contracts.models import Contract,ContractItem
from apps.contracts.services import create_contract,add_contract_item,transition_contract_status
from apps.estimates.models import Estimate,EstimateItem,EstimateRevision
from apps.estimates.services import create_estimate,add_estimate_item,approve_estimate,create_estimate_revision
from apps.organizations.models import Organization,PlatformPolicyVersion
from apps.billing.models import ProgressClaim,ProjectBaseline,ProgressRecord,PayableCertificate
from apps.accounting.models import JournalEntry
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement,PaymentRequest

MARKER='BONIRA-AFOGH-CLIENT-SAMPLES-20261101'
SPECS=[
 ('UAT-AFG-REC-01','CTR-02-01-01','0.50','اجرای سازه و محوطه‌سازی باغستان'),
 ('UAT-AFG-REC-02','CTR-02-02-01','0.75','تکمیل و تجهیز مرکز درمانی مهر'),
 ('UAT-AFG-REC-03','CTR-02-04-01','1.25','اجرای ساختمان اداری آفتاب'),
]

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

def finance(org):
 return {m.__name__:m.objects.filter(organization=org).count() for m in (JournalEntry,Obligation,TreasuryMovement,PaymentRequest)}

def guard():
 assert settings.DEBUG and settings.SETTINGS_MODULE=='config.settings.development'
 assert connection.vendor=='postgresql' and connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1','')

def base(apply=False):
 guard()
 with transaction.atomic():
  org=Organization.objects.select_for_update().get(slug='demo-construction-02',name='گروه عمرانی افق تهران',status='active',deleted_at__isnull=True)
  actor=User.objects.get(username='account.demo-construction-02.owner',is_active=True)
  approver=User.objects.get(username='admin',is_active=True)
  assert actor.pk!=approver.pk
  # Retain exact snapshots of pre-existing business rows by their initial PKs.
  protected=[]
  for model in (Contract,ContractItem,Estimate,EstimateItem,EstimateRevision,ProgressClaim,ProjectBaseline,ProgressRecord,PayableCertificate):
   rows=list(model.objects.filter(organization=org).order_by('pk').values())
   protected.append((model,[r['id'] for r in rows],digest(rows)))
  policy_hash=digest(list(PlatformPolicyVersion.objects.order_by('pk').values()))
  before_finance=finance(org)
  result=[]
  for number,source_number,factor,title in SPECS:
   source=Contract.objects.select_related('project','party').get(organization=org,contract_number=source_number,direction='receivable',deleted_at__isnull=True)
   items=list(source.items.select_related('unit_of_measure').order_by('sort_order','pk'))
   assert items and source.party_id
   value=sum((i.quantity*(i.unit_price*Decimal(factor)).quantize(Decimal('.01')) for i in items),Decimal(0)).quantize(Decimal(".01"))
   contract=Contract.objects.filter(organization=org,contract_number=number).first()
   if contract:
    assert MARKER in contract.notes and contract.contract_value==value and contract.project_id==source.project_id
   else:
    contract=create_contract(organization=org,project=source.project,actor=actor,contract_number=number,title='نمونه کارفرمایی — '+title,counterparty_name=source.counterparty_name,party=source.party,direction='receivable',contract_type='client',contract_value=value,signed_at=date(2026,10,24),start_date=date(2026,10,24),end_date=date(2027,10,23),notes=MARKER+' — داده نمونه محلی؛ فاقد اعتبار تجاری یا قانونی. مبالغ فرضی برای بررسی فرم‌ها؛ بدون شناسایی دریافتنی، ثبت حسابداری، وصول یا تسویه.')
    for item in items:
     add_contract_item(organization=org,actor=actor,contract=contract,description='نمونه — '+item.description,quantity=item.quantity,unit_price=(item.unit_price*Decimal(factor)).quantize(Decimal('.01')),unit=item.unit,unit_of_measure=item.unit_of_measure,sort_order=item.sort_order)
    contract=transition_contract_status(organization=org,actor=actor,contract=contract,status='active')
   estimates=[]
   for index,price_factor in ((1,Decimal('.90')),(2,Decimal('1.10'))):
    estimate_number=f'{number}-EST-{index}'
    estimate=Estimate.objects.filter(organization=org,estimate_number=estimate_number).first()
    if not estimate:
     estimate=create_estimate(organization=org,project=source.project,actor=actor,estimate_number=estimate_number,title=('برآورد پایه — ' if index==1 else 'برآورد تکمیلی — ')+title,contract=contract,notes=MARKER+' — قیمت‌های فرضی نمونه محلی')
     # Four lines with the source units; quantities/prices remain exact Decimal.
     for order,item in enumerate(contract.items.order_by('sort_order','pk'),1):
      for part,share in ((1,Decimal('.60')),(2,Decimal('.40'))):
       add_estimate_item(estimate=estimate,actor=actor,description=item.description+(' — مرحله اول' if part==1 else ' — مرحله دوم'),quantity=(item.quantity*share).quantize(Decimal(".0001")),unit_price=(item.unit_price*price_factor).quantize(Decimal('.01')),unit=item.unit,unit_of_measure=item.unit_of_measure,sort_order=order*10+part)
     if index==1:
      estimate=approve_estimate(estimate=estimate,actor=approver)
     elif number.endswith('03'):
      estimate=approve_estimate(estimate=estimate,actor=approver)
      create_estimate_revision(estimate=estimate,actor=actor,notes=MARKER+' — نسخه تکمیلی در حال بازنگری')
      estimate.refresh_from_db()
    else:
     assert MARKER in estimate.notes and estimate.contract_id==contract.pk
    estimates.append({'number':estimate.estimate_number,'id':str(estimate.pk),'status':estimate.status,'total':str(estimate.total_amount),'path':f'/estimates/{estimate.pk}/'})
   result.append({'number':number,'id':str(contract.pk),'project':source.project.code,'title':contract.title,'amount':str(value),'path':f'/contracts/{contract.pk}/','estimates':estimates})
  for model,ids,old_hash in protected:
   assert digest(list(model.objects.filter(pk__in=ids).order_by('pk').values()))==old_hash,model.__name__+' pre-existing rows changed'
  assert finance(org)==before_finance
  assert digest(list(PlatformPolicyVersion.objects.order_by('pk').values()))==policy_hash
  output={'stage':'base','applied':apply,'tenant':org.slug,'contracts':result,'existing_records_unchanged':True,'finance_before_after':before_finance,'policy_unchanged':True}
  if not apply: transaction.set_rollback(True)
  return output

def claims_stage(org, actor, approver, contracts):
 from apps.billing.services import add_baseline_item,approve_progress_claim,approve_project_baseline,create_progress_claim,create_progress_record,create_project_baseline,request_progress_verification,request_project_baseline_approval,return_progress_claim,submit_progress_claim,verify_progress_record
 from apps.contracts.services import create_contract_term_version,approve_contract_term_version
 from apps.organizations.policy_services import resolve_effective_platform_regulatory_policy
 from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE
 policy=PlatformPolicyVersion.objects.get(pk='c8e9de14-242d-4866-aa67-463f85a892f8',status='published',policy__code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE)
 policy_hash=digest(list(PlatformPolicyVersion.objects.order_by('pk').values()))
 before_finance=finance(org)
 output=[]
 for idx,entry in enumerate(contracts):
  contract=Contract.objects.get(organization=org,pk=entry['id'],direction='receivable')
  assert MARKER in contract.notes
  existing=ProgressClaim.objects.filter(organization=org,contract=contract)
  if existing.exists():
   assert existing.count()==5 and set(existing.values_list('status',flat=True))=={'draft','approved','returned','submitted'}
  else:
   term=create_contract_term_version(organization=org,actor=actor,contract=contract,effective_from=date(2026,10,24),insurance_classification=policy.insurance_classification,reason=MARKER+' — تأیید کاربر برای مصرف پیکربندی موجود فقط روی این نمونه محلی')
   approve_contract_term_version(organization=org,actor=approver,term_version=term,reason=MARKER+' — بررسی مستقل شرایط نمونه')
   baseline=create_project_baseline(organization=org,actor=actor,project=contract.project,contract=contract,effective_date=date(2026,10,24))
   for item in contract.items.order_by('sort_order','pk'):
    add_baseline_item(organization=org,actor=actor,baseline=baseline,line_key=f'AFG-L{item.sort_order:02}',description=item.description,unit=item.unit,planned_quantity=item.quantity,unit_rate=item.unit_price,contract_item=item,sort_order=item.sort_order)
   request_project_baseline_approval(organization=org,actor=actor,baseline=baseline)
   baseline=approve_project_baseline(organization=org,actor=approver,baseline=baseline,reason=MARKER+' — تأیید مستقل مبنای نمونه')
   cumulative=Decimal(0)
   factors=(('0.10','0.15','0.10','0.10'),('0.15','0.10','0.05','0.20'),('0.05','0.20','0.15','0.10'))[idx]
   for period_index,status in enumerate(('approved','submitted','returned','draft')):
    start=24+period_index*2;end=start+1;factor=Decimal(factors[period_index]);cumulative+=factor
    resolved=resolve_effective_platform_regulatory_policy(code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,consumer='billing.progress_claim.calculate',on_date=date(2026,10,end),insurance_classification=policy.insurance_classification)
    assert resolved.pk==policy.pk
    for item in baseline.items.order_by('sort_order','pk'):
     record=create_progress_record(organization=org,actor=actor,baseline=baseline,baseline_item=item,period_start=date(2026,10,start),period_end=date(2026,10,end),measured_on=date(2026,10,start),source_type='demo',source_reference=f'{MARKER}-{contract.contract_number}-{start}-{item.line_key}',period_quantity=(item.planned_quantity*factor).quantize(Decimal('.0001')),cumulative_quantity=(item.planned_quantity*cumulative).quantize(Decimal('.0001')),evidence=MARKER+' — شاهد اندازه‌گیری صرفاً نمونه محلی')
     request_progress_verification(organization=org,actor=actor,record=record)
     verify_progress_record(organization=org,actor=approver,record=record,reason=MARKER+' — کنترل مستقل اندازه‌گیری نمونه')
    claim=create_progress_claim(organization=org,actor=actor,baseline=baseline,period_start=date(2026,10,start),period_end=date(2026,10,end),measurement_cutoff=date(2026,10,end))
    if status!='draft': submit_progress_claim(organization=org,actor=actor,claim=claim)
    if status=='approved': approve_progress_claim(organization=org,actor=approver,claim=claim,reason=MARKER+' — تأیید مستقل نمونه؛ بدون شناسایی دریافتنی')
    elif status=='returned': return_progress_claim(organization=org,actor=approver,claim=claim,reason=MARKER+' — بازگشت نمونه برای اصلاح و ایجاد نسخه جدید')
  claims=list(ProgressClaim.objects.filter(organization=org,contract=contract).order_by('claim_number','revision_number'))
  for c in claims:
   assert c.regulatory_rule_version_id==policy.pk
   assert c.gross_amount==sum((i.current_amount for i in c.items.all()),Decimal(0))
   assert c.net_amount==c.gross_amount+c.adjustment_amount
  output.append({'contract':contract.contract_number,'baseline_path':f'/billing/baselines/?contract={contract.pk}', 'claims':[{'number':c.claim_number,'revision':c.revision_number,'status':c.status,'gross':str(c.gross_amount),'net':str(c.net_amount),'path':f'/billing/claims/{c.pk}/'} for c in claims]})
 assert finance(org)==before_finance
 assert digest(list(PlatformPolicyVersion.objects.order_by('pk').values()))==policy_hash
 return output


def full(apply=False):
 guard()
 with transaction.atomic():
  org=Organization.objects.select_for_update().get(slug='demo-construction-02')
  protected=[]
  for model in (Contract,ContractItem,Estimate,EstimateItem,EstimateRevision,ProgressClaim,ProjectBaseline,ProgressRecord,PayableCertificate):
   rows=list(model.objects.filter(organization=org).order_by('pk').values())
   protected.append((model,[r['id'] for r in rows],digest(rows)))
  base_result=base(True)
  org=Organization.objects.select_for_update().get(slug='demo-construction-02')
  actor=User.objects.get(username='account.demo-construction-02.owner',is_active=True)
  approver=User.objects.get(username='admin',is_active=True)
  # Bounded policy reuse is explicitly approved in HUMAN_AUTHORIZATION.md.
  assert Path(__file__).with_name('HUMAN_AUTHORIZATION.md').exists()
  result={'base':base_result,'claims':claims_stage(org,actor,approver,base_result['contracts']),'applied':apply}
  # HTTP rendering validates the final shape while transactionally visible.
  from django.test import Client
  from apps.organizations.services import set_active_organization
  client=Client(HTTP_HOST='localhost');client.force_login(actor)
  session=client.session;set_active_organization(session,org);session.save()
  paths=[r['path'] for r in base_result['contracts']]+[e['path'] for r in base_result['contracts'] for e in r['estimates']]+[c['path'] for r in result['claims'] for c in r['claims']]
  paths += ['/billing/claims/','/billing/baselines/','/billing/progress/','/estimates/','/contracts/']
  result['http_checks']=[{'path':path,'status':client.get(path).status_code} for path in paths]
  assert all(r['status']==200 for r in result['http_checks'])
  for model,ids,old_hash in protected:
   assert digest(list(model.objects.filter(pk__in=ids).order_by('pk').values()))==old_hash,model.__name__+' pre-existing rows changed'
  result['pre_existing_business_rows_unchanged']=True
  if not apply: transaction.set_rollback(True)
  return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--full',action='store_true');parser.add_argument('--output',required=True)
 args=parser.parse_args()
 result=full(args.apply) if args.full else base(args.apply)
 Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Sample stage complete; applied:',args.apply)
