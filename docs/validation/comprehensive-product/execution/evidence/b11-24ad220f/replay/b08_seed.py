from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from django.db import connection, transaction
from django.test import Client, TestCase
from django.utils import timezone
def save(*args): pass

def clone(obj, **changes):
    data={f.attname:getattr(obj,f.attname) for f in obj._meta.concrete_fields
          if not f.primary_key and f.name not in {'created_at','updated_at'}}
    data.update(changes)
    return type(obj).objects.create(**data)

def db_state():
    """Content witnesses from every application table, independent of HTTP process."""
    result={}
    with connection.cursor() as c:
        for table in sorted(connection.introspection.table_names()):
            if table in {'django_session','django_migrations'} or table.startswith('auth_'):
                continue
            c.execute(f'SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text,\'\' ORDER BY row_to_json(t)::text),\'\')) FROM "{table}" t')
            result[table]=c.fetchone()
    return result

@transaction.atomic
def seed():
    from tests.test_mvp07_xlsx import P1Fixture
    from apps.inventory.test_mvp04e import InventoryJourneyFixture
    from apps.billing.test_mvp03 import JourneyFixture
    from apps.billing.services import submit_progress_claim, return_progress_claim, approve_progress_claim
    from apps.procurement.test_rfq import RequestForQuotationServiceTests
    from apps.procurement.models import PurchaseRequest, RequestForQuotation, PurchaseOrder, GoodsReceipt
    from apps.expenses.services import create_expense
    from apps.expenses.models import PlatformExpenseGroup
    from apps.inventory.services import create_stock_transaction, post_stock_transaction
    from apps.organizations.models import BusinessPermission, OrganizationRole, MembershipScopeGrant, MembershipRoleAssignment
    from apps.accounts.models import User
    from apps.projects.models import Project, ProjectSite
    from apps.daily_reports.models import DailyReport
    from apps.equipment.p8_models import EquipmentUsageLog
    class Ops(P1Fixture, InventoryJourneyFixture, TestCase):
        pass
    f=Ops(); f.client=Client(); f.setUp()
    for user,org in [(f.owner,f.organization),(f.member,f.organization),(f.outsider,f.other_organization)]:
        member=org.memberships.get(user=user)
        MembershipRoleAssignment.objects.get_or_create(organization=org,membership=member,role=member.role_definition,revoked_at__isnull=True,defaults={'reason':'B08 explicit fixture authority','source':'test_fixture'})
    rfq=RequestForQuotationServiceTests._draft(f)
    kpi_request=clone(rfq.purchase_request,request_number='B08-KPI-PR',status='draft',submitted_at=timezone.now()-timedelta(hours=48))
    for line in rfq.purchase_request.items.all():clone(line,purchase_request_id=kpi_request.pk)
    kpi_request.status='approved';kpi_request.save(update_fields=['status'])
    from apps.procurement.services import issue_purchase_order
    order,order_item=f.make_order(issued=False)
    order.purchase_request=kpi_request;order.save(update_fields=['purchase_request'])
    issue_purchase_order(organization=f.organization,actor=f.owner,purchase_order=order)
    receipt=f.create_receipt(order,'GRN-1');f.assertEqual(f.add(receipt,order_item,'4').status_code,302);f.assertEqual(f.post(receipt).status_code,302)
    receipt.refresh_from_db();item=receipt.items.get()
    receipt2=f.create_receipt(order,'B08-GRN-PART2');f.assertEqual(f.add(receipt2,order_item,'6').status_code,302);f.assertEqual(f.post(receipt2).status_code,302)
    stock=create_stock_transaction(organization=f.organization,actor=f.owner,
        transaction_number='B08-IN-1',transaction_type='receipt',material=f.material,
        unit_of_measure=f.unit,quantity=item.quantity,occurred_at=receipt.received_at,
        destination_warehouse=f.central,project=f.project,goods_receipt_item=item)
    post_stock_transaction(organization=f.organization,actor=f.owner,stock_transaction=stock)
    PlatformExpenseGroup.objects.get_or_create(code='other',defaults={'name':'سایر هزینه‌ها'})
    expense=create_expense(organization=f.organization,actor=f.owner,project=f.field_project,
        description='=1+1', amount=Decimal('12345.67'),incurred_on=date(2026,11,3),receipt_reference='B08-REC')
    # More than the default 25-row page for each list, and 50-row operations pane.
    request=rfq.purchase_request
    order=receipt.purchase_order
    for i in range(2,32):
        pr=clone(request,request_number=f'B08-PR-{i}',title='=1+1',status='draft')
        for line in request.items.all(): clone(line,purchase_request_id=pr.pk)
        pr.status='approved';pr.save(update_fields=['status'])
        rr=clone(rfq,rfq_number=f'B08-RFQ-{i}',title='=1+1',purchase_request_id=pr.pk)
        for line in rfq.lines.all(): clone(line,rfq_id=rr.pk,purchase_request_item_id=pr.items.first().pk)
        po=clone(order,order_number=f'B08-PO-{i}',status='draft',current_version_id=None,
                 issued_at=None,issued_by_id=None,purchase_request_id=pr.pk)
        for line in order.items.all(): clone(line,purchase_order_id=po.pk)
        gr=clone(receipt,receipt_number=f'B08-GRN-{i}',status='draft',posted_at=None,posted_by_id=None)
        for line in receipt.items.all(): clone(line,goods_receipt_id=gr.pk)
        create_expense(organization=f.organization,actor=f.owner,project=f.field_project,description=f'B08 هزینه {i}',amount=Decimal('12345.67'),incurred_on=date(2026,11,3),receipt_reference=f'B08-{i}')
        clone(f.report,reporting_date=f.report.reporting_date+timedelta(days=i),work_performed='=1+1')
        clone(f.estimate,estimate_number=f'B08-EST-{i}',current_revision_id=None,title='=1+1')
        eq=clone(f.equipment,code=f'B08-EQ-{i}',name='=1+1',serial_number='',registration_number='')
        clone(f.assignment,equipment_id=eq.pk)
        clone(f.attendance,work_date=f.attendance.work_date+timedelta(days=i),check_in_at=f.attendance.check_in_at+timedelta(days=i),check_out_at=f.attendance.check_out_at+timedelta(days=i))
        # Each stock fixture is a distinct synthetic draft, with no second stock posting.
        clone(stock,transaction_number=f'B08-IN-{i}',transaction_type='adjustment_in',goods_receipt_item_id=None,status='draft',
              posted_at=None,posted_by_id=None,reference='=1+1')
    for i in range(2,57):
        clone(f.usage,source_key=f'B08-USAGE-{i}',started_at=f.usage.started_at+timedelta(days=i),
              ended_at=f.usage.ended_at+timedelta(days=i),correction_reason='=1+1')
    class Bill(JourneyFixture, TestCase): pass
    b=Bill(); b.client=Client(); b.make_fixture(persian=True); b.login(b.owner)
    b.project.name='=1+1'; b.project.save(update_fields=['name'])
    claim=b._claim()
    submit_progress_claim(organization=b.organization,actor=b.owner,claim=claim)
    return_progress_claim(organization=b.organization,actor=b.manager,claim=claim,reason='نسخه تاریخی خروجی')
    claim.refresh_from_db()
    successor=claim.returned_revision
    submit_progress_claim(organization=b.organization,actor=b.owner,claim=successor)
    approve_progress_claim(organization=b.organization,actor=b.manager,claim=successor,reason='بررسی مستقل نسخه جدید')
    # Original is retained at 60, successor is a distinct draft. Never edit history.
    for i in range(2,32):
        clone(claim,claim_number=i,status='draft',revision_number=1,submission_snapshot={},
              submitted_at=None,submitted_by_id=None,returned_at=None,returned_by_id=None,
              returned_revision_id=None,return_reason='',gross_amount=0,net_amount=0,
              calculation_snapshot={})
    f.material.name='=1+1';f.material.save(update_fields=['name'])
    f.supplier.display_name='=1+1';f.supplier.save(update_fields=['display_name'])
    for obj,field,value in [(f.other_organization,'name',f.organization.name),(f.other_project,'name',f.project.name),(f.other_material,'name',f.material.name),(f.other_supplier,'display_name',f.supplier.display_name),(f.other_unit,'name',f.unit.name)]:
        setattr(obj,field,value);obj.save(update_fields=[field])
    def actor(org, username, project=None, permissions=None):
        user=User.objects.create_user(username=username)
        role=OrganizationRole.objects.create(organization=org,code=username,name='خواننده خروجی')
        role.permissions.set(BusinessPermission.objects.filter(is_active=True,**({'code__in':permissions} if permissions is not None else {})))
        member=org.memberships.create(user=user,role_definition=role,status='active',authorization_migrated_at=timezone.now())
        MembershipRoleAssignment.objects.create(organization=org,membership=member,role=role,reason='B08 explicit fixture authority',source='test_fixture')
        MembershipScopeGrant.objects.create(organization=org,membership=member,
             scope_type='project' if project else 'organization',project=project)
        return user
    sibling=Project.objects.create(organization=f.organization,code='B08-X',name='پروژه محدود')
    sibling_site=ProjectSite.objects.create(organization=f.organization,project=sibling,code='B08-X',name='کارگاه محدود')
    f.restricted=actor(f.organization,'b08-denied',permissions=[])
    f.scoped=actor(f.organization,'b08-scoped',project=sibling)
    f.nosource=actor(f.organization,'b08-no-source',permissions=['reporting.metric_result.view','reporting.portfolio.view'])
    b.restricted=actor(b.organization,'b08-billing-denied',permissions=[])
    bp=Project.objects.create(organization=b.organization,code='B08-X',name='پروژه محدود')
    b.scoped=actor(b.organization,'b08-billing-scoped',project=bp)
    from apps.daily_reports.test_return_revisions import ReturnFixture
    from apps.daily_reports.revision_services import save_correction
    from apps.daily_reports.submission_snapshots import HEADER_FIELDS
    class Historical(ReturnFixture,TestCase):pass
    h=Historical();h.client=Client();h.setUp();h.entries(h.report)
    first=h.submit();h.returned(first);latest=h.successor(first)
    header={name:getattr(latest,name) for name in HEADER_FIELDS};header['work_performed']='B08-LATEST-ONLY'
    save_correction(**h.args(latest,h.author),kind='header',values=header,expected_version=latest.edit_version,operation_key=uuid4())
    h.report=first;h.report.refresh_from_db()
    h.restricted=actor(h.organization,'b08-history-denied',permissions=[])
    hp=Project.objects.create(organization=h.organization,code='B08-X',name='پروژه محدود')
    h.scoped=actor(h.organization,'b08-history-scoped',project=hp)
    f.historical=h
    f.report.refresh_from_db()
    # Reporting uses actual persisted PR -> PO -> posted GRN lineage.
    from apps.reporting.services import refresh_metric,review_metric_result
    from apps.inventory.p8_models import InventoryValuationPool
    from apps.organizations.models import PlatformPolicyVersion
    # Order remains issued with unchanged quantities/version; an approved synthetic PR link.
    assert order.purchase_request_id==kpi_request.pk
    result=refresh_metric(organization=f.organization,actor=f.owner,metric_code='procurement_cycle_time',idempotency_key='b08-cycle')
    from apps.organizations.models import PlatformPolicy
    from apps.organizations.policy_specs import ACCOUNTING_MONEY_PRECISION_POLICY_CODE, ACCOUNTING_ROUNDING_POLICY_CODE, get_platform_policy_spec, initial_accounting_policy_parameters
    def monetary_policy(code):
        spec=get_platform_policy_spec(code)
        policy,_=PlatformPolicy.objects.get_or_create(code=code,defaults={'name':spec.name,'category':spec.category,'sensitivity':spec.sensitivity,'tenant_selectable':spec.tenant_selectable,'requires_source_provenance':False,'created_by':f.owner,'updated_by':f.owner})
        version=PlatformPolicyVersion.objects.filter(policy=policy,status='published').first()
        return version or PlatformPolicyVersion.objects.create(policy=policy,version=1,parameters=initial_accounting_policy_parameters(code),effective_from=date(2026,1,1),status='published',source_basis='product_defined',created_by=f.owner,published_by=f.owner,published_at=timezone.now(),reason='Existing P8 product-defined synthetic monetary fixture')
    precision=monetary_policy(ACCOUNTING_MONEY_PRECISION_POLICY_CODE)
    rounding=monetary_policy(ACCOUNTING_ROUNDING_POLICY_CODE)
    material2=clone(f.material,code='B08-MAT2',name='مصالح هم‌واحد دوم')
    for material,quantity,amount in [(f.material,'10.2500','128.1250'),(material2,'2.7500','34.3750')]:
        InventoryValuationPool.objects.create(organization=f.organization,material=material,quantity=Decimal(quantity),value_amount=Decimal(amount),average_cost=Decimal('12.50000000'),currency='IRR',monetary_precision_version=precision,rounding_policy_version=rounding)
    InventoryValuationPool.objects.create(organization=f.other_organization,material=f.other_material,quantity=Decimal('9999'),value_amount=Decimal('999999'),average_cost=Decimal('100.00990099'),currency='IRR',monetary_precision_version=precision,rounding_policy_version=rounding)
    inventory=refresh_metric(organization=f.organization,actor=f.owner,metric_code='inventory_quantity_value',idempotency_key='b08-inventory')
    review_metric_result(result=inventory,reviewer=f.member,reason='بررسی مستقل منبع مصنوعی')
    empty_metric=refresh_metric(organization=f.other_organization,actor=f.outsider,metric_code='procurement_cycle_time',idempotency_key='b08-empty')
    unreviewed=refresh_metric(organization=f.other_organization,actor=f.outsider,metric_code='inventory_quantity_value',idempotency_key='b08-unreviewed')
    assert empty_metric.value=={'average_seconds':None,'completed_cycles':0} and not empty_metric.coverage['complete']
    assert not hasattr(unreviewed,'review')
    save('fixture.json', {'organization':f.organization.pk,'project':f.project.pk,'field_project':f.field_project.pk,
        'site':f.site.pk,'sibling_project':sibling.pk,'sibling_site':sibling_site.pk,
        'billing_org':b.organization.pk,'claim':claim.pk,'claim_revision':claim.revision_number,
        'claim_successor':claim.returned_revision_id,'claim_net':claim.net_amount,
        'report':f.report.pk,'order':order.pk,'receipt':receipt.pk,
        'reporting_results':[result.pk,inventory.pk], 'synthetic_only':True})
    f.billing=b;f.claim=claim;f.receipt=receipt;f.stock=stock
    return f,b,claim,receipt,order


