"""Bounded, idempotent local-demo seed for the explicitly requested contract.

Only creates editable estimates through existing services. Completed-contract
payable controls are preserved; no certificate, terms, posting or status bypass.
"""
import argparse
import hashlib
import json
import os
import sys
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
from apps.billing.models import PayableCertificate, PayableMeasurement, ProgressClaim, ProjectBaseline
from apps.contracts.models import Contract
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate, add_estimate_item
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.authorization import require_business_permission
from apps.organizations.services import set_active_organization

TARGET = 'CTR-02-03-04'
TARGET_ID = '22524f53-c0fa-4a3b-ab1a-df06b2e3acf9'
TENANT = 'demo-construction-02'
MARKER = 'BONIRA-CONTRACT-DETAIL-UAT-CTR-02-03-04-20261101'

def protected_snapshot(c):
    return {
        'contract': Contract.objects.filter(pk=c.pk).values().get(),
        'items': list(c.items.order_by('pk').values()),
        'terms': list(c.term_versions.order_by('pk').values()),
        'amendments': list(c.amendments.order_by('pk').values()),
        'certificates': list(PayableCertificate.objects.filter(contract=c).values_list('pk', flat=True)),
        'measurements': list(PayableMeasurement.objects.filter(contract=c).values_list('pk', flat=True)),
        'receivable_claims': list(ProgressClaim.objects.filter(contract=c).values_list('pk', flat=True)),
        'receivable_baselines': list(ProjectBaseline.objects.filter(contract=c).values_list('pk', flat=True)),
    }

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def run(apply):
    if not (settings.SETTINGS_MODULE == 'config.settings.development' and settings.DEBUG and connection.vendor == 'postgresql' and connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1','')):
        raise RuntimeError('Only the verified local development environment is permitted.')
    with transaction.atomic():
        contract = Contract.objects.select_for_update(of=('self',)).select_related('organization','project').get(pk=TARGET_ID, contract_number=TARGET, organization__slug=TENANT, deleted_at__isnull=True)
        org = contract.organization
        if org.status != 'active' or contract.project.deleted_at or contract.direction != 'payable' or contract.status != 'completed':
            raise RuntimeError('Verified tenant/contract context changed; inspect before proceeding.')
        actor = User.objects.get(username='account.demo-construction-02.owner', is_active=True)
        for permission in (P.CONTRACTS_VIEW, P.ESTIMATES_CREATE, P.ESTIMATE_ITEMS_ADD, P.ESTIMATES_VIEW):
            require_business_permission(user=actor, organization=org, permission=permission, project=contract.project, message="اجازه ایجاد داده آزمون این قرارداد وجود ندارد.")
        before = protected_snapshot(contract)
        items = list(contract.items.select_related('unit_of_measure').order_by('sort_order','pk'))
        if not items:
            raise RuntimeError('Existing contract lines are required; none are invented.')
        result = {'contract': TARGET, 'tenant': TENANT, 'project': contract.project.code, 'mode': 'apply' if apply else 'dry-run', 'contract_path': reverse('contracts:detail', args=[contract.pk]), 'estimates': [], 'payable_certificate': {'created': False, 'blocker': 'Existing payable_services._locked_subcontract requires an active contract. Target is completed and has no approved commercial terms.'}, 'contract_status': contract.status}
        for suffix, label, factor in (('A','برآورد پایه آزمایشی تأسیسات',Decimal('1')), ('B','برآورد سناریوی یک‌چهارم برای کنترل فرم',Decimal('0.25'))):
            number = f'UAT-{TARGET}-{suffix}'
            estimate = Estimate.objects.filter(organization=org, estimate_number=number).first()
            created = False
            if estimate is not None:
                if estimate.contract_id != contract.pk or estimate.project_id != contract.project_id or MARKER not in estimate.notes:
                    raise RuntimeError('Seed identifier collision with unrelated data.')
            elif apply:
                estimate = create_estimate(organization=org, project=contract.project, actor=actor, contract=contract, estimate_number=number, title=label, notes=f'{MARKER}\nداده Seed آزمایشی برای بررسی فرم جزئیات قرارداد؛ فاقد تأیید تجاری. مقادیر از ردیف‌های همین قرارداد با ضریب سناریو تهیه شده‌اند. ضریب سناریو: {factor}.')
                for item in items:
                    add_estimate_item(estimate=estimate, actor=actor, description=f'نمونه آزمون — {item.description}', quantity=(item.quantity * factor).quantize(Decimal("0.0001")), unit_price=item.unit_price, unit=item.unit, unit_of_measure=item.unit_of_measure, sort_order=item.sort_order)
                created = True
            total = sum(((item.quantity * factor * item.unit_price).quantize(Decimal('0.01')) for item in items), Decimal(0))
            entry = {'number': number, 'created': created, 'expected_total': str(total), 'line_count': len(items), 'status': estimate.status if estimate else 'planned-draft'}
            if estimate:
                actual = sum((row.line_total for row in estimate.current_revision.items.all()), Decimal(0))
                if created and actual != total:
                    raise RuntimeError('Seed total verification failed.')
                entry.update({'id':str(estimate.pk),'path':reverse('estimates:detail', args=[estimate.pk]), 'actual_total': str(actual)})
            result['estimates'].append(entry)
        after = protected_snapshot(contract)
        if before != after:
            raise RuntimeError('Protected existing contract data changed; rollback.')
        result['protected_before_sha256'] = digest(before)
        result['protected_after_sha256'] = digest(after)
        result['protected_records_unchanged'] = True
        if apply:
            client = Client(HTTP_HOST='localhost')
            client.force_login(actor)
            session = client.session
            set_active_organization(session, org)
            session.save()
            pages = []
            for path in [result['contract_path']] + [entry['path'] for entry in result['estimates']]:
                response = client.get(path)
                if response.status_code != 200:
                    raise RuntimeError(f'Render verification failed: {response.status_code}')
                pages.append({'path':path,'status':response.status_code})
            body = client.get(result['contract_path']).content.decode()
            if not all(entry['number'] in body for entry in result['estimates']):
                raise RuntimeError('Contract detail is missing the seeded estimate links.')
            result['render_checks'] = pages
        return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run(args.apply)
    payload = json.dumps(result,ensure_ascii=False,default=str,indent=2)
    if args.output:
        args.output.write_text(payload,encoding='utf-8')
    print(payload,flush=True)
