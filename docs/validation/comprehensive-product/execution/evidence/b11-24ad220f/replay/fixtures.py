from datetime import date, timedelta
from importlib import import_module
from uuid import uuid4

from django.apps import apps
from django.db import transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.services import create_organization_with_owner
from apps.organizations.test_platform_console import PlatformConsoleTests
from apps.inventory.test_inbound_transfers import InboundTransferFixture
from apps.daily_reports.test_return_revisions import ReturnFixture
from apps.procurement.test_mvp04b2 import QuoteReceiptJourneyTests
from apps.workflows.test_workbench import WorkbenchTests
from apps.timekeeping.services import capture_attendance, finalize_attendance
from apps.documents.services import record_document_processing_assessment
from apps.projects.models import ProjectPhase

from b08_seed import seed as ops_seed
from b09_seed import seed as docs_seed, assess, persona


def fixture(cls, *args):
    value = cls()
    value.client = Client()
    value.setUp()
    return value


def seed(only=None):
    actors = {}
    sources = {}
    results = {}
    def group(name, fn):
        old_actors, old_sources = dict(actors), dict(sources)
        try:
            with transaction.atomic():
                value = fn()
            results[name] = 'PASS'
            return value
        except Exception as error:
            import traceback
            traceback.print_exc()
            actors.clear(); actors.update(old_actors)
            sources.clear(); sources.update(old_sources)
            results[name] = type(error).__name__
            return None

    def register(name, user, org):
        actors[name] = (user, org)

    def ops():
        f, b, claim, receipt, order = ops_seed()
        for name, x in [('ops', f), ('billing', b), ('history', f.historical)]:
            register(name, x.owner, x.organization)
            register(name+'-limited', x.restricted, x.organization)
            register(name+'-sibling', x.scoped, x.organization)
        register('foreign', f.outsider, f.other_organization)
        for name, obj in [('ops-project',f.project),('field-project',f.field_project),('ops-site',f.site),
                          ('order',order),('receipt',receipt),('stock',f.stock),('claim',claim),
                          ('billing-contract',b.contract),('history-report',f.historical.report),('ops-report',f.report),
                          ('billing-baseline',claim.baseline),('ops-equipment',f.equipment),('ops-employee',f.employee)]:
            sources[name]=obj
        return f

    def documents():
        f = docs_seed()
        for name, user in [('docs',f.owner),('docs-limited',f.denied),('docs-sibling',f.sibling)]:
            register(name,user,f.organization)
        register('docs-foreign',f.other_user,f.other_organization)
        sources.update({'document':f.doc, 'document-version':f.first, **{'dms-'+k:v for k,v in f.generic.items()},
                        **{'evidence-'+k:v for k,v in f.special.items()}})
        from apps.documents.association import link_in_context
        from apps.documents.models import DocumentLink
        for kind, obj in f.generic.items():
            if not DocumentLink.objects.filter(document=f.doc, **{kind:obj}).exists():
                link_in_context(user=f.owner,organization=f.organization,kind=kind,identifier=obj.pk,document_id=f.doc.pk)
        for kind,obj in f.special.items():
            if kind in ('guarantee','compliance','release'):
                continue
            from django.forms.widgets import HiddenInput
            from html.parser import HTMLParser
            class Hidden(HTMLParser):
                def handle_starttag(self,tag,attributes):
                    attrs=dict(attributes)
                    if tag=='input' and attrs.get('type')=='hidden' and attrs.get('name'):
                        data[attrs['name']]=attrs.get('value','')
            path=reverse('documents:evidence-register',args=[kind,obj.pk])
            client=f.login()
            response=client.get(path)
            if response.status_code!=200:
                continue
            data={}
            Hidden().feed(response.content.decode())
            data['versions' if kind in ('safety','quality') else 'version']=str(f.first.pk)
            if kind=='contractual':
                data['label']='شاهد آزمایشی بنیرا'
            if kind in ('safety','quality'):
                data['reason']='ارسال آزمایشی بنیرا'
            client.post(path,data)
        return f

    def field():
        from apps.organizations.models import Organization
        Organization.objects.filter(slug='b02-remediation').update(slug='b11-history')
        for user in User.objects.filter(username__startswith='b02-'):
            user.username='b11-history-'+user.username
            user.save(update_fields=['username'])
        class Field(ReturnFixture,TestCase):
            pass
        f=fixture(Field)
        f.entries(f.report)
        report=f.submit()
        register('field',f.owner,f.organization)
        register('field-author',f.author,f.organization)
        register('field-limited',persona(f,'b11-field-none',[]),f.organization)
        register('field-reviewer',f.reviewer,f.organization)
        reviewer,_,_=f.member('b11-hse',['safety_incidents.view','safety_incidents.record_decide','quality_issues.view','quality_issues.record_decide'],site=f.site)
        register('hse-reviewer',reviewer,f.organization)
        for app,noun,number,kind,severity in [('safety','incident','incident_number','near_miss','low'),('quality','issue','issue_number','defect','minor')]:
            service=import_module(f'apps.{app}.services')
            review=import_module(f'apps.{app}.record_review')
            obj=getattr(service,f'create_{app}_{noun}')(organization=f.organization,actor=f.owner,project=f.project,site=f.site,description='شرح آزمون بنیرا',**{number:f'B11-{app}', 'occurred_at' if app=='safety' else 'identified_at':f.moment(9),f'{noun}_type':kind,'severity':severity})
            getattr(review,f'submit_{app}_record')(organization=f.organization,actor=f.owner,**{f'{noun}_id':obj.pk},reason='ارسال آزمون')
            sources[app]=obj
        from apps.equipment.models import Equipment, EquipmentAssignment
        eq=Equipment.objects.create(organization=f.organization,code='B11-EQ',name='ماشین آزمون بنیرا',category='ماشین‌آلات')
        EquipmentAssignment.objects.create(organization=f.organization,equipment=eq,project=f.project,site=f.site,status='active',start_date=f.day)
        from apps.equipment.p8_services import create_work_order
        order=create_work_order(organization=f.organization,actor=f.owner,equipment=eq,number='B11-WORK',summary='سرویس نمونه ماشین')
        sources['field-work-order']=order
        phase=ProjectPhase.objects.create(organization=f.organization,site=f.site,code='B11-PH',name='مرحله آزمون')
        attendance=capture_attendance(organization=f.organization,actor=f.owner,employee=f.employee,calendar=f.calendar,project=f.project,site=f.site,work_date=f.day,check_in_at=f.moment(8),check_out_at=f.moment(10))
        attendance_reviewer,_,_=f.member('b11-attendance-reviewer',['attendance.review'])
        finalize_attendance(organization=f.organization,actor=attendance_reviewer,attendance=attendance)
        from apps.timekeeping.services import request_attendance_correction, create_leave_mission_request, create_overtime_request, create_timesheet
        correction=request_attendance_correction(organization=f.organization,requester=f.corrector,attendance=attendance,reason='اصلاح آزمایشی')
        context={'organization':f.organization,'actor':f.owner,'employee':f.employee,'project':f.project,'site':f.site,'reason':'آزمون'}
        mission=create_leave_mission_request(**context,kind='mission',category_code='field',starts_at=f.moment(11),ends_at=f.moment(12))
        overtime=create_overtime_request(**context,starts_at=f.moment(15),ends_at=f.moment(16))
        timesheet=create_timesheet(organization=f.organization,actor=f.owner,employee=f.employee,period_start=f.day,period_end=f.day,declared_minutes=120)
        sources.update({'field-correction':correction,'field-leave':mission,'field-overtime':overtime,'field-timesheet':timesheet})
        sources.update({'field-main-project':f.project,'field-main-site':f.site,'field-main-phase':phase,'field-report':report,'field-equipment':eq,'field-employee':f.employee,'field-attendance':attendance})
        return f

    def inventory():
        class Inv(InboundTransferFixture,TestCase):
            pass
        f=fixture(Inv)
        register('inventory',f.owner,f.organization)
        register('inventory-limited',persona(f,'b11-inventory-none',[]),f.organization)
        register('inventory-receiver',f.receiver,f.organization)
        register('inventory-sibling',f.sibling,f.organization)
        register('inventory-foreign',f.outsider,f.other_organization)
        from apps.inventory.p8_services import create_inventory_count
        count=create_inventory_count(organization=f.organization,actor=f.owner,count_number='B11-COUNT',warehouse=f.site)
        sources.update({'warehouse':f.site,'transfer':f.first,'shipping-project':f.shipping_project,'count':count})
        return f

    def procurement():
        for slug in ('procurement-co','other-procurement-co'):
            from apps.organizations.models import Organization
            Organization.objects.filter(slug=slug).update(slug='b11-ops-'+slug)
        for user in User.objects.filter(username__startswith='procurement-'):
            user.username='b11-ops-'+user.username
            user.save(update_fields=['username'])
        f=fixture(QuoteReceiptJourneyTests)
        from apps.organizations.models import BusinessPermission
        f.organization.memberships.get(user=f.owner).role_definition.permissions.add(*BusinessPermission.objects.filter(code__startswith='rfq'))
        register('rfq',f.owner,f.organization)
        register('rfq-limited',persona(f,'b11-rfq-none',[]),f.organization)
        register('rfq-foreign',f.outsider,f.other_organization)
        response=f.capture()
        from apps.procurement.models import QuoteRevision
        sources.update({'rfq':f.rfq,'invitation':f.invitation,'rfq-request':f.rfq.purchase_request})
        revision=QuoteRevision.objects.filter(organization=f.organization).first()
        if revision:
            sources['quote-revision']=revision
        from apps.organizations.models import BusinessPermissionCode
        from apps.procurement.portal_services import create_supplier_portal_invitation, accept_supplier_portal_invitation, submit_supplier_portal_quote
        f.organization.memberships.get(user=f.owner).role_definition.permissions.add(BusinessPermission.objects.get(code=BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE))
        external=User.objects.create_user(username='b11-external',email='supplier-b11@example.test')
        _,token=create_supplier_portal_invitation(organization=f.organization,actor=f.owner,rfq_invitation=f.invitation,invited_email=external.email,expires_at=timezone.now()+timedelta(days=1))
        grant=accept_supplier_portal_invitation(actor=external,token=token)
        register('supplier',external,None)
        sources['portal-grant']=grant
        from b09_seed import upload
        sources['portal-receipt']=submit_supplier_portal_quote(actor=external,grant=grant,upload=upload(),source_reference='B11-SUPPLIER',idempotency_key='b11-supplier')
        return f

    def workflow():
        for slug in ('procurement-co','other-procurement-co'):
            from apps.organizations.models import Organization
            Organization.objects.filter(slug=slug).update(slug='b11-rfq-'+slug)
        for user in User.objects.filter(username__startswith='procurement-'):
            user.username='b11-rfq-'+user.username
            user.save(update_fields=['username'])
        f=fixture(WorkbenchTests)
        from decimal import Decimal
        from apps.procurement.services import create_purchase_request, add_purchase_request_item, submit_purchase_request
        request=create_purchase_request(organization=f.organization, actor=f.member, project=f.project,request_number='B11-WF-REQUEST',title='درخواست آزمایشی کارتابل')
        add_purchase_request_item(organization=f.organization,actor=f.member,purchase_request=request,material=f.material,quantity=Decimal(2))
        submit_purchase_request(organization=f.organization,actor=f.member,purchase_request=request)
        register('workflow',f.owner,f.organization)
        register('workflow-reviewer',f.member,f.organization)
        register('workflow-limited',persona(f,'b11-wf-none',[]),f.organization)
        register('workflow-foreign',f.outsider,f.other_organization)
        sources.update({'work-item':f._item(request),'workflow-request':request})
        return f

    def platform():
        PlatformConsoleTests.setUpTestData()
        p=PlatformConsoleTests
        register('platform',p.admin,None)
        register('tenant',p.owner,p.company)
        sources['company']=p.company
        sources['platform-user']=p.owner
        sources['membership']=p.company.memberships.get(user=p.owner)
        return p

    def payable():
        from unittest.mock import patch
        from apps.billing import test_payable_certificates as fixture_module
        from tests.retirement_fixtures import explicit_fixture_roles
        from apps.billing.models import PayableMeasurement
        original=fixture_module.create_project
        def authorize(**kwargs):
            explicit_fixture_roles(kwargs['organization'])
            return original(**kwargs)
        with patch.object(fixture_module,'create_project',side_effect=authorize):
            f=fixture(fixture_module.PayableCertificateTests)
        f._measurement()
        certificate=f._approve(f._certificate())
        register('payable',f.owner,f.organization)
        register('payable-limited',persona(f,'b11-payable-none',[]),f.organization)
        sources['payable-certificate']=certificate
        sources['payable-measurement']=PayableMeasurement.objects.filter(organization=f.organization).first()

    def accounts():
        u=User.objects.create_user(username='b11-auth',email='b11-auth@example.test')
        required=User.objects.create_user(username='b11-required',email='b11-required@example.test',must_change_password=True)
        org=create_organization_with_owner(owner=required,name='شرکت رمز موقت آزمایشی',slug='b11-required')
        register('auth-user',u,None)
        register('required',required,org)
        register('anonymous',None,None)
        register('empty',u,create_organization_with_owner(owner=u,name='شرکت بدون داده آزمایشی',slug='b11-empty'))

    for name,fn in [('ops',ops),('documents',documents),('field',field),('inventory',inventory),
                    ('procurement',procurement),('workflow',workflow),('platform',platform),('payable',payable),('accounts',accounts)]:
        if only is None or name in only:
            group(name,fn)
    return actors,sources,results










