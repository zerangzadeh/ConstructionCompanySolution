"""Explicit local-demo subcontract seed; all writes use governed application services."""
import argparse
import calendar
import hashlib
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.accounting.models import JournalEntry
from apps.billing.models import PayableCertificate, PayableMeasurement, ProgressClaim, ProjectBaseline
from apps.billing.payable_services import create_payable_measurement, submit_payable_measurement, decide_payable_measurement, create_payable_certificate, submit_payable_certificate, approve_payable_certificate
from apps.contracts.models import Contract
from apps.contracts.services import create_contract, add_contract_item, transition_contract_status, create_contract_term_version, approve_contract_term_version
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate, add_estimate_item, approve_estimate
from apps.estimates.workflow import request_estimate_approval
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import Organization, BusinessPermissionCode as P
from apps.organizations.services import set_active_organization
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement, PaymentRequest

TENANT = 'demo-construction-02'
NUMBER = 'UAT-SUB-02-03'
MARKER = 'BONIRA-UAT-SUB-02-03-20261101'
HERE = Path(__file__).resolve().parent

def snapshot(c):
    return {'contract':Contract.objects.filter(pk=c.pk).values().get(), 'items':list(c.items.order_by('pk').values()), 'terms':list(c.term_versions.order_by('pk').values()), 'estimates':list(Estimate.objects.filter(contract=c).order_by('pk').values()), 'certificates':list(PayableCertificate.objects.filter(contract=c).order_by('pk').values()), 'measurements':list(PayableMeasurement.objects.filter(contract=c).order_by('pk').values())}

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

def financial_counts(org):
    return {model.__name__:model.objects.filter(organization=org).count() for model in (JournalEntry,Obligation,TreasuryMovement,PaymentRequest)}

def permission(actor, org, project, codes):
    for code in codes:
        require_business_permission(user=actor,organization=org,project=project,permission=code,message='اجازه ایجاد این داده آزمون وجود ندارد.')

def describe(contract, created):
    estimates=[]
    for e in Estimate.objects.filter(contract=contract).select_related('current_revision').order_by('estimate_number'):
        total=sum((i.line_total for i in e.current_revision.items.all()),Decimal(0))
        estimates.append({'number':e.estimate_number,'status':e.status,'amount':str(total),'path':reverse('estimates:detail',args=[e.pk])})
    certs=[{'number':c.certificate_number,'status':c.status,'gross':str(c.gross_amount),'net':str(c.net_amount),'period_start':c.period_start,'period_end':c.period_end,'path':reverse('billing:payable_certificate_detail',args=[c.pk])} for c in PayableCertificate.objects.filter(contract=contract).order_by('certificate_number')]
    return {'contract':contract.contract_number,'contract_id':str(contract.pk),'tenant':TENANT,'project':contract.project.code,'created':created,'currency':contract.organization.settings.currency,'contract_value':str(contract.contract_value),'contract_status':contract.status,'contract_path':reverse('contracts:detail',args=[contract.pk]),'payable_list_path':reverse('billing:payable_certificate_list'),'estimates':estimates,'certificates':certs,'measurements':PayableMeasurement.objects.filter(contract=contract).count()}

def run(apply):
    if not (settings.SETTINGS_MODULE=='config.settings.development' and settings.DEBUG and connection.vendor=='postgresql' and connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1','')):
        raise RuntimeError('Only the verified local development database is permitted.')
    with transaction.atomic():
        org=Organization.objects.select_for_update().get(slug=TENANT,status='active',deleted_at__isnull=True)
        source=Contract.objects.select_related('organization','project','party').get(organization=org,contract_number='CTR-02-03-05',direction='payable',contract_type='subcontract',status='active',deleted_at__isnull=True)
        protected=Contract.objects.get(organization=org,contract_number='CTR-02-03-04')
        before={source.contract_number:snapshot(source),protected.contract_number:snapshot(protected)}
        finances=financial_counts(org)
        actor=User.objects.get(username='account.demo-construction-02.owner',is_active=True)
        approver=User.objects.get(username='admin',is_active=True)
        if actor.pk==approver.pk:
            raise RuntimeError('Independent actors required.')
        permission(actor,org,source.project,[P.CONTRACTS_CREATE,P.CONTRACTS_TRANSITION,P.CONTRACT_ITEMS_ADD,P.CONTRACT_TERMS_MANAGE,P.PAYABLE_MEASUREMENTS_RECORD,P.PAYABLE_CERTIFICATES_CREATE,P.PAYABLE_CERTIFICATES_REVISE,P.PAYABLE_CERTIFICATES_SUBMIT,P.PAYABLE_CERTIFICATES_VIEW,P.ESTIMATES_CREATE,P.ESTIMATE_ITEMS_ADD,P.ESTIMATES_REVISE,P.ESTIMATES_VIEW])
        permission(approver,org,source.project,[P.CONTRACT_TERMS_APPROVE,P.PAYABLE_MEASUREMENTS_VERIFY,P.PAYABLE_CERTIFICATES_APPROVE,P.ESTIMATES_APPROVE])
        rows=list(source.items.select_related('unit_of_measure').order_by('sort_order','pk'))
        if len(rows)!=2 or sum((i.line_total for i in rows),Decimal(0))!=source.contract_value:
            raise RuntimeError('Verified source contract line data changed.')
        contract=Contract.objects.filter(organization=org,contract_number=NUMBER).first()
        if contract and MARKER not in contract.notes:
            raise RuntimeError('Seed number collision with unrelated data.')
        if not apply:
            return {'mode':'dry-run','target':NUMBER,'project':source.project.code,'contract_value':str(source.contract_value),'estimates':3,'certificates':3,'verified_measurements':6,'statuses':['approved','approved','submitted'],'terms':'Existing service defaults: no retention/recovery/insurance deduction; explicitly synthetic commercial conditions on a NEW demo contract only.','existing_contracts_unchanged':list(before),'existing_seed':bool(contract)}
        created=contract is None
        if created:
            contract=create_contract(organization=org,project=source.project,actor=actor,contract_number=NUMBER,title='قرارداد پیمانکاری آزمایشی نما — کنترل فرم',counterparty_name=source.counterparty_name,party=source.party,direction='payable',contract_type='subcontract',contract_value=source.contract_value,signed_at=date(2026,6,25),start_date=date(2026,7,1),end_date=date(2027,6,30),notes=f'{MARKER}\nفقط داده Seed آزمایشی برای کنترل فرم؛ فاقد اعتبار تجاری یا قانونی. قیمت‌ها از قرارداد نمونه همان شرکت کپی شده‌اند. شرایط آزمایشی از پیش‌فرض سرویس بدون کسور استفاده می‌کند؛ هیچ دریافت یا پرداخت و ثبت حسابداری ایجاد نمی‌شود.')
            for item in rows:
                add_contract_item(organization=org,actor=actor,contract=contract,description=f'آزمایشی — {item.description}',quantity=item.quantity,unit_price=item.unit_price,unit=item.unit,unit_of_measure=item.unit_of_measure,wbs_node=item.wbs_node,sort_order=item.sort_order)
            contract=transition_contract_status(organization=org,actor=actor,contract=contract,status='active')
            term=create_contract_term_version(organization=org,actor=actor,contract=contract,effective_from=date(2026,7,1),reason=f'{MARKER} — فقط شرایط نمونه بدون کسور، بر اساس پیش‌فرض سرویس؛ بدون ادعای قانونی یا تجاری')
            approve_contract_term_version(organization=org,actor=approver,term_version=term,reason=f'{MARKER} — تأیید مستقل داده آزمایشی بدون کسور')
            for n,factor in enumerate((Decimal('1'),Decimal('0.5'),Decimal('0.25')),1):
                e=create_estimate(organization=org,project=source.project,actor=actor,contract=contract,estimate_number=f'UAT-EST-SUB-02-03-{n:02}',title=f'برآورد آزمایشی پیمانکاری — سناریوی {n}',notes=f'{MARKER}\nصرفاً داده آزمون؛ ضریب سناریو {factor}. فاقد اعتبار تجاری.')
                for item in rows:
                    add_estimate_item(estimate=e,actor=actor,description=f'آزمایشی — {item.description}',quantity=(item.quantity*factor).quantize(Decimal('0.0001')),unit_price=item.unit_price,unit=item.unit,unit_of_measure=item.unit_of_measure,sort_order=item.sort_order)
                if n==1:
                    request_estimate_approval(estimate=e,actor=actor)
                    approve_estimate(estimate=e,actor=approver)
            cumulative=Decimal(0)
            for n,factor in enumerate((Decimal('0.10'),Decimal('0.20'),Decimal('0.15')),1):
                month=6+n
                cumulative+=factor
                for item in contract.items.order_by('sort_order','pk'):
                    m=create_payable_measurement(organization=org,actor=actor,contract_item=item,measured_on=date(2026,month,15),period_quantity=(item.quantity*factor).quantize(Decimal('0.0001')),cumulative_quantity=(item.quantity*cumulative).quantize(Decimal('0.0001')),evidence_reference=f'{MARKER}-P{n:02}-L{item.sort_order:02} — شاهد اندازه‌گیری صرفاً آزمایشی')
                    submit_payable_measurement(organization=org,actor=actor,measurement=m)
                    decide_payable_measurement(organization=org,actor=approver,measurement=m,approved=True,reason=f'{MARKER} — کنترل مستقل اندازه‌گیری آزمایشی')
                end=date(2026,month,calendar.monthrange(2026,month)[1])
                cert=create_payable_certificate(organization=org,actor=actor,contract=contract,period_start=date(2026,month,1),period_end=end,measurement_cutoff=end)
                expected=(source.contract_value*factor).quantize(Decimal('0.0001'))
                if cert.gross_amount!=expected or cert.net_amount!=expected:
                    raise RuntimeError('Certificate amount differs from exact source measurement.')
                submit_payable_certificate(organization=org,actor=actor,certificate=cert)
                if n<3:
                    approve_payable_certificate(organization=org,actor=approver,certificate=cert,reason=f'{MARKER} — تأیید مستقل گواهی آزمایشی؛ بدون شناسایی بدهی و پرداخت')
        contract.refresh_from_db()
        result=describe(contract,created)
        if len(result['estimates'])!=3 or len(result['certificates'])!=3 or result['measurements']!=6:
            raise RuntimeError('Seed set is partial or changed; inspect instead of overwriting.')
        after={source.contract_number:snapshot(source),protected.contract_number:snapshot(protected)}
        if before!=after or financial_counts(org)!=finances:
            raise RuntimeError('Protected prior records or downstream finance changed; rollback.')
        if ProgressClaim.objects.filter(contract=contract).exists() or ProjectBaseline.objects.filter(contract=contract).exists():
            raise RuntimeError('Receivable records must never be added to this payable seed.')
        client=Client(HTTP_HOST='localhost')
        client.force_login(actor)
        session=client.session
        set_active_organization(session,org)
        session.save()
        paths=[result['contract_path'],result['payable_list_path']]+[e['path'] for e in result['estimates']]+[c['path'] for c in result['certificates']]
        result['render_checks']=[]
        for path in paths:
            response=client.get(path)
            if response.status_code!=200:
                raise RuntimeError(f'Seed render failed: {path} {response.status_code}')
            result['render_checks'].append({'path':path,'status':200})
        result.update({'protected_before_sha256':fingerprint(before),'protected_after_sha256':fingerprint(after),'previous_contracts_unchanged':True,'downstream_financial_counts_before':finances,'downstream_financial_counts_after':financial_counts(org),'receivable_records_created':False,'notes':'Contract Detail currently does not consume payable certificates. Review these records through payable certificate pages; UI code and exposure were not changed.'})
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run(args.apply)
    payload=json.dumps(result,ensure_ascii=False,default=str,indent=2)
    if args.output:
        args.output.write_text(payload,encoding='utf-8')
    print(payload,flush=True)
