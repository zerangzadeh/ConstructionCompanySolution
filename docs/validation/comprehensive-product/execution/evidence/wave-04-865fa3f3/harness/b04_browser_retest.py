"""B04 real Chrome journeys; ORM connection is deliberately read-only."""
import os
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']='1'
import json,re,traceback
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo
from common import root,db,guard
from django.apps import apps
from django.conf import settings
from django.urls import reverse
from core.jalali import gregorian_to_jalali
from playwright.sync_api import sync_playwright

guard(readonly=True)
cfg=json.loads((root/db/'actors.json').read_text(encoding='utf-8'));ids=cfg['ids']
base='http://127.0.0.1:'+(root/'retest-web-port.txt').read_text().strip()
out=root/db/os.environ.get('B04_OUT','browser');out.mkdir(exist_ok=True)
results={};observations=[];traffic=[]
def model(app,name):return apps.get_model(app,name)
def get(app,name,**kw):return model(app,name).objects.get(**kw)
def mark(route,ok,**details):
    results.setdefault(route,[]).append({'ok':bool(ok),**details})
    print(route,bool(ok),details,flush=True)
    save()
def save():
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (out/'pages.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'traffic.json').write_text(json.dumps(traffic,ensure_ascii=False,indent=2),encoding='utf-8')
def visit(p,url):return p.goto(base+url,wait_until='load').status
def main(p):return p.locator('main').first
def text(p):return main(p).inner_text() if p.locator('main').count() else p.locator('body').inner_text()
def form(p,suffix=None):
    return main(p).locator(f'form[action$="{suffix}"]' if suffix else 'form[method="post"]').first
def fill(f,**values):
    for name,v in values.items():
        el=f.locator(f'[name="{name}"]');v=str(v)
        if el.evaluate('e=>e.tagName')=='SELECT':
            # Select the real rendered option through its existing enhanced control.
            if el.is_visible():el.select_option(v)
            else:el.evaluate('(e,v)=>{if(e.tomselect)e.tomselect.setValue(v);else{e.value=v;e.dispatchEvent(new Event("change",{bubbles:true}));}}',v)
        else:
            mode=el.get_attribute('data-jalali-mode')
            if mode and re.match(r'^2026-',v):
                y,m,d=gregorian_to_jalali(*map(int,v[:10].split('-')))
                v=f'{y:04}/{m:02}/{d:02}'+((' '+v[11:]) if len(v)>10 else '')
            if el.get_attribute('type')=='hidden':el.evaluate('(e,v)=>e.value=v',v)
            else:el.fill(v)
            if mode:el.press('Escape')
def click(f):
    p=f.page
    if f.locator('[name=effective_date]').count() and not f.locator('[name=effective_date]').input_value():fill(f,effective_date='2026-11-12')
    f.locator('button:not([type="button"]),input[type="submit"]').last.click()
    p.wait_for_timeout(130)
    confirm=p.locator('.swal2-confirm:visible')
    if confirm.count():confirm.click()
    p.wait_for_load_state('load')
def post(p,url,values=None,csrf=True):
    token=next((c['value'] for c in p.context.cookies() if c['name']==settings.CSRF_COOKIE_NAME),'')
    return p.request.post(base+url,form=values or {},headers={'X-CSRFToken':token} if csrf else {},max_redirects=0).status
def capture(p,label,shots=False):
    for width,height in [(1440,900),(1024,768),(390,844)]:
        p.set_viewport_size({'width':width,'height':height});p.wait_for_timeout(70)
        d=p.evaluate('''()=>{let m=document.querySelector('main')||document.body,v=e=>!!e.getClientRects().length;return {width:innerWidth,scroll:document.documentElement.scrollWidth,dir:document.documentElement.dir,main:document.querySelectorAll('main').length,headings:[...m.querySelectorAll('h1,h2')].map(e=>e.innerText),links:[...m.querySelectorAll('a[href]')].filter(v).map(e=>[e.innerText,e.getAttribute('href')]),fields:[...m.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='hidden').map(e=>[e.name,e.type,e.value,e.disabled]),errors:[...m.querySelectorAll('.errorlist,[role=alert]')].map(e=>e.innerText)}}''')
        observations.append({'label':label,'path':urlsplit(p.url).path,**d})
        if shots:p.screenshot(path=out/f'{label}-{width}.png',full_page=True,animations='disabled')
    p.set_viewport_size({'width':1440,'height':900});save()
def create(p,route,values,app,name,lookup,shots=False):
    existing=model(app,name).objects.filter(**lookup).first()
    if existing:return existing
    status=visit(p,reverse(route));assert status==200,(route,status)
    f=form(p);fill(f,**values);capture(p,route.replace(':','-'),shots)
    click(f)
    obj=model(app,name).objects.filter(**lookup).first()
    mark(route,obj is not None,path=urlsplit(p.url).path,errors=text(p)[:1200] if obj is None else '',pk=obj.pk if obj else None)
    return obj
def transition(p,route,obj,values,state,app,name,kwargs=None):
    url=reverse(route,kwargs=kwargs) if kwargs else reverse(route,args=[obj.pk])
    # Follow the actual visible control whenever it exists, otherwise retain endpoint-only limitation.
    f=main(p).locator(f'form[action="{url}"]')
    if not f.count():
        response=visit(p,url)
        if response==200:f=form(p)
        else:
            mark(route,False,blocked='No visible operator form',GET=response);return False
    f=f.first
    fill(f,**values);click(f)
    fresh=get(app,name,pk=obj.pk)
    mark(route,fresh.status==state,state=fresh.status,expected=state)
    return fresh.status==state
def login(browser,username):
    c=browser.new_context(viewport={'width':1440,'height':900})
    c.route(re.compile(r'^https?://(?!'+re.escape(urlsplit(base).netloc)+r'(?:/|$))'),lambda r:r.abort())
    p=c.new_page();p.set_default_timeout(60000);p.set_default_navigation_timeout(60000)
    p.on('response',lambda r:traffic.append([username,r.request.method,urlsplit(r.url).path,r.status]) if r.request.resource_type in {'document','fetch','xhr'} else None)
    visit(p,reverse('accounts:login')+'?next=/equipment/')
    fill(p.locator('form').first,username=username,password=cfg['password']);click(p.locator('form').first)
    assert not p.locator('[name=password]').count(),username
    return p
def task(label,fn):
    try:fn()
    except Exception as exc:
        mark('HARNESS:'+label,False,error=str(exc),traceback=traceback.format_exc())

def equipment(owner,reviewer,reader,foreign,scoped,wrong):
    eq=create(owner,'equipment:create',dict(code='B04-EQ-UI',name='لودر آزمون مرورگر',category='خاکبرداری',ownership_type='owned',acquired_on='2026-11-12'), 'equipment','Equipment',dict(organization_id=ids['org'],code='B04-EQ-UI'),True)
    if not eq:return
    for route in ['equipment:list','equipment:operations_workbench','equipment:assignment_list','equipment:maintenance_list']:
        status=visit(owner,reverse(route));capture(owner,route.replace(':','-'),route.endswith(':list'))
        mark(route,status==200 and main(owner).locator('h1').count()==1,headings=main(owner).locator('h1').all_text_contents())
    detail=reverse('equipment:detail',args=[eq.pk]);visit(owner,detail);capture(owner,'equipment-detail',True)
    mark('equipment:detail',eq.name in text(owner),foreign_status=visit(foreign,detail))
    assignment=create(owner,'equipment:assignment_create',dict(equipment=eq.pk,project=ids['project'],site=ids['site'],start_date='2026-11-12',purpose='آزمون B04'), 'equipment','EquipmentAssignment',dict(equipment=eq),True)
    if assignment:
        visit(owner,reverse('equipment:assignment_create'));f=form(owner);fill(f,equipment=eq.pk,project=ids['project'],site=ids['site'],start_date='2026-11-12');click(f)
        mark('equipment:assignment_create',model('equipment','EquipmentAssignment').objects.filter(equipment=eq).count()==1,overlap_rejected=text(owner)[-900:])
        url=reverse('equipment:assignment_status_change',args=[assignment.pk]);visit(owner,url);fill(form(owner),target_status='cancelled' if assignment.status=='scheduled' else 'completed');click(form(owner))
        assignment.refresh_from_db();mark('equipment:assignment_status_change',assignment.status in ['completed','cancelled'],state=assignment.status)
    visit(owner,detail)
    transition(owner,'equipment:status_change',eq,{'target_status':'retired'},'retired','equipment','Equipment')
    visit(owner,detail);archive=reverse('equipment:archive',args=[eq.pk]);f=main(owner).locator(f'form[action="{archive}"]')
    if f.count():click(f.first)
    else:post(owner,archive)
    eq.refresh_from_db();mark('equipment:archive',eq.archived_at is not None,archived=eq.archived_at)
    maintenance=create(owner,'equipment:maintenance_create',dict(equipment=ids['equipment'],record_number='B04-M1',maintenance_type='preventive',summary='سرویس دوره‌ای آزمون',scheduled_date='2026-11-12',project=ids['project'],site=ids['site'],description='بازرسی روغن'), 'equipment','MaintenanceRecord',dict(organization_id=ids['org'],record_number='B04-M1'))
    if maintenance:
        visit(owner,reverse('equipment:maintenance_detail',args=[maintenance.pk]));capture(owner,'maintenance-detail')
        mark('equipment:maintenance_detail','سرویس دوره‌ای آزمون' in text(owner))
        url=reverse('equipment:maintenance_status_change',args=[maintenance.pk]);visit(owner,url);fill(form(owner),target_status='completed');click(form(owner));maintenance.refresh_from_db()
        mark('equipment:maintenance_status_change',maintenance.status=='completed',state=maintenance.status)
    reading=create(owner,'equipment:meter_reading_create',dict(meter=ids['meter'],value='103',observed_at='2026-11-12T11:00',source_key='B04-meter-ui'), 'equipment','MeterReading',dict(organization_id=ids['org'],source_key='B04-meter-ui'))
    if reading:mark('equipment:meter_reading_create',reading.observed_at.astimezone(ZoneInfo('Asia/Tehran')).hour==11,stored=reading.observed_at,expected_local='11:00')
    visit(owner,reverse('equipment:meter_reading_create'));fill(form(owner),meter=ids['meter'],value='99',observed_at='2026-11-12T12:00',source_key='B04-meter-low');click(form(owner))
    mark('equipment:meter_reading_create',not model('equipment','MeterReading').objects.filter(source_key='B04-meter-low').exists(),lower_meter_error=text(owner)[-800:])
    usage=create(owner,'equipment:usage_create',dict(equipment=ids['equipment'],started_at='2026-11-12T13:00',ended_at='2026-11-12T15:00',runtime_hours='2',source_key='B04-usage-ui'), 'equipment','EquipmentUsageLog',dict(organization_id=ids['org'],source_key='B04-usage-ui'),True)
    if usage:
        mark('equipment:usage_create',usage.started_at.astimezone(ZoneInfo('Asia/Tehran')).hour==13,stored=usage.started_at,runtime=usage.runtime_hours,deployment=usage.deployment_id,operator=usage.operator_id)
        url=reverse('equipment:usage_create');v=dict(equipment=ids['equipment'],started_at='2026-11-12T15:00',ended_at='2026-11-12T13:00',runtime_hours='2',source_key='B04-invalid-usage')
        visit(owner,url);fill(form(owner),**v);click(form(owner));capture(owner,'usage-invalid',True)
        mark('equipment:usage_create',not model('equipment','EquipmentUsageLog').objects.filter(source_key='B04-invalid-usage').exists() and owner.locator('[name=runtime_hours]').count()>0,invalid_page=text(owner)[:800])
    plan=create(owner,'equipment:maintenance_plan_create',dict(equipment=ids['equipment'],name='برنامه نگهداری B04',maintenance_type='preventive',interval_days='30'), 'equipment','MaintenancePlan',dict(organization_id=ids['org'],name='برنامه نگهداری B04'))
    wo=create(owner,'equipment:work_order_create',dict(equipment=ids['equipment'],number='B04-WO1',summary='دستورکار مرورگر B04',scheduled_for='2026-11-12',**({'plan':plan.pk} if plan else {})), 'equipment','EquipmentWorkOrder',dict(organization_id=ids['org'],number='B04-WO1'))
    if wo:
        visit(owner,reverse('equipment:work_order_detail',args=[wo.pk]));capture(owner,'work-order-detail',True);mark('equipment:work_order_detail',wo.summary in text(owner))
        create(owner,'equipment:work_order_evidence_create',{},'equipment','MaintenanceWorkOrderEvidence',{}) if False else None
        for route,vals,app,name,lookup in [
          ('equipment:work_order_evidence_create',dict(reference='B04 synthetic reference',result_notes='بازرسی انجام شد'),'equipment','MaintenanceWorkOrderEvidence',dict(work_order=wo)),
          ('equipment:spare_link_create',{},'equipment','MaintenanceSparePartReference',dict(work_order=wo))]:
            url=reverse(route,args=[wo.pk]);s=visit(owner,url);capture(owner,route.replace(':','-'))
            if route.endswith('spare_link_create'):
                fill(form(owner),inventory_transaction=ids['spare']);click(form(owner));mark(route,model(app,name).objects.filter(**lookup).exists());continue
            fill(form(owner),**vals);click(form(owner));mark(route,model(app,name).objects.filter(**lookup).exists())
        for state in ['scheduled','in_progress','completed']:
            visit(owner,reverse('equipment:work_order_transition',args=[wo.pk]));fill(form(owner),target_status=state,completion_notes='اتمام آزمون');click(form(owner));wo.refresh_from_db();mark('equipment:work_order_transition',wo.status==state,state=wo.status)
    # Form admission and foreign tenant denial are independently observed.
    for route in ['equipment:create','equipment:assignment_create','equipment:usage_create']:
        mark(route,visit(reader,reverse(route)) in [403,404],restricted_status=urlsplit(reader.url).path)
    mark('equipment:detail',visit(foreign,reverse('equipment:detail',args=[ids['equipment']])) in [403,404],boundary='foreign tenant')

def costs(owner,reviewer):
    policy=create(owner,'equipment:cost_policy_create',dict(code='B04-POL',version='1',effective_from='2026-11-01',monetary_policy_code='B04-synthetic',monetary_policy_version='1',decimal_places='2'), 'equipment','EquipmentCostPolicyVersion',dict(organization_id=ids['org'],code='B04-POL'),True)
    if not policy:return
    rate=create(owner,'equipment:cost_rate_create',dict(policy=policy.pk,equipment=ids['equipment'],rate_amount='125000',effective_from='2026-11-01'), 'equipment','EquipmentCostRate',dict(policy=policy))
    visit(reviewer,reverse('equipment:cost_workbench'))
    for action,state in [('review','reviewed'),('publish','published')]:
        transition(reviewer,'equipment:cost_policy_transition',policy,{},state,'equipment','EquipmentCostPolicyVersion',kwargs={'policy_id':policy.pk,'action':action})
    allocation=create(owner,'equipment:cost_allocation_create',dict(usage=ids['usage'],source_key='B04-allocation'), 'equipment','EquipmentCostAllocation',dict(organization_id=ids['org'],source_key='B04-allocation'))
    if allocation:
        mark('equipment:cost_allocation_create',allocation.amount==Decimal('375000'),amount=allocation.amount,measure=allocation.measure,rate=allocation.rate_snapshot,source=allocation.usage_id,site=allocation.site_id)
        visit(reviewer,reverse('equipment:cost_workbench'));transition(reviewer,'equipment:cost_allocation_finalize',allocation,{},'finalized','equipment','EquipmentCostAllocation')
        envelope=create(owner,'equipment:cost_handoff_create',dict(allocation=allocation.pk), 'equipment','EquipmentCostSourceEnvelope',dict(allocation=allocation),True)
        if envelope:
            visit(reviewer,reverse('equipment:cost_workbench'));transition(reviewer,'equipment:cost_handoff_review',envelope,{},'reviewed','equipment','EquipmentCostSourceEnvelope')
            visit(owner,reverse('equipment:cost_handoff_create'));fill(form(owner),allocation=allocation.pk);click(form(owner));mark('equipment:cost_handoff_create',model('equipment','EquipmentCostSourceEnvelope').objects.filter(allocation=allocation).count()==1,replay_count=model('equipment','EquipmentCostSourceEnvelope').objects.filter(allocation=allocation).count())
            url=reverse('equipment:cost_handoff_reconcile',args=[envelope.pk]);visit(reviewer,url);fill(form(reviewer),consumer_reference='B04 synthetic reconciliation',reconciliation_note='بدون دریافت کننده ثبت مالی');click(form(reviewer));envelope.refresh_from_db();mark('equipment:cost_handoff_reconcile',envelope.consumer_reference=='B04 synthetic reconciliation',state=envelope.status,feedback=text(reviewer)[-1100:])
        visit(reviewer,reverse('equipment:cost_allocation_reverse',args=[allocation.pk]));fill(form(reviewer),reason='برگشت آزمون');click(form(reviewer));allocation.refresh_from_db();mark('equipment:cost_allocation_reverse',allocation.status=='reversed',state=allocation.status)
    visit(owner,reverse('equipment:cost_workbench'));capture(owner,'cost-workbench-populated',True);mark('equipment:cost_workbench','B04-POL' in text(owner))
    fuel=create(owner,'equipment:fuel_create',dict(equipment=ids['equipment'],occurred_at='2026-11-12T15:15',quantity='20',unit='litre',source_key='B04-fuel'), 'equipment','FuelLog',dict(organization_id=ids['org'],source_key='B04-fuel'))
    if fuel:mark('equipment:fuel_create',fuel.occurred_at.astimezone(ZoneInfo('Asia/Tehran')).hour==15,stored=fuel.occurred_at,quantity=fuel.quantity)
    create(owner,'equipment:operator_qualification_create',dict(equipment=ids['equipment'],employee=ids['employee'],workforce_qualification=ids['qualification'],effective_from='2026-11-01',effective_to='2026-12-01'), 'equipment','OperatorEquipmentQualification',dict(organization_id=ids['org'],employee_id=ids['employee']))
    down=create(owner,'equipment:downtime_create',dict(equipment=ids['equipment'],reason_code='SERVICE',started_at='2026-11-12T16:00',reason='بازرسی آزمایشی'), 'equipment','DowntimeEvent',dict(organization_id=ids['org'],reason_code='SERVICE'))
    if down:mark('equipment:downtime_create',down.started_at.astimezone(ZoneInfo('Asia/Tehran')).hour==16,stored=down.started_at)

def hseq(owner,reviewer,reader,foreign,scoped,wrong):
    for app,name,num,when,kind,severity in [('safety','SafetyIncident','incident_number','occurred_at','near_miss','low'),('quality','QualityIssue','issue_number','identified_at','defect','minor')]:
        route=app+':create';vals=dict(project=ids['project'],site=ids['site'],phase=ids['phase'],description='شرح مصنوعی آزمون B04',severity=severity,**{num:'B04-'+app,when:'2026-11-10T09:30',('incident_type' if app=='safety' else 'issue_type'):kind})
        obj=create(scoped,route,vals,app,name,{num+'__iexact':vals[num]},True)
        if not obj:continue
        local=getattr(obj,when).astimezone(ZoneInfo('Asia/Tehran'));mark(route,local.hour==9 and local.minute==30,stored=getattr(obj,when),local=local)
        detail=reverse(app+':detail',args=[obj.pk]);visit(scoped,detail);capture(scoped,app+'-reported',True)
        mark(app+':detail',obj.description in text(scoped),project=obj.project_id,site=obj.site_id,review_status=obj.review_status)
        mark(app+':detail',visit(foreign,detail) in [403,404] and visit(wrong,detail) in [403,404],boundary='foreign and sibling site')
        mark(app+':create',visit(reader,reverse(route)) in [403,404],boundary='reader')
        visit(reviewer,detail)
        steps=[('review',{},'under_review'),('assign',dict(responsible_user=get('accounts','User',username='b02-b04-scoped').pk,due_date='2026-11-20'),'assigned'),('corrective_action',dict(corrective_action='ایمن سازی و اصلاح آزمون'),'action_in_progress')]
        steps+= [('resolve',dict(resolution_summary='خطر برطرف شد'),'resolved')] if app=='safety' else [('submit_for_verification',dict(corrective_action_result='اصلاح انجام شد'),'awaiting_verification'),('verify',dict(verification_summary='بازرسی مستقل تایید شد'),'verified')]
        steps += [('close',dict(closure_summary='اتمام و حفظ سابقه'),'closed')]
        for action,values,state in steps:
            visit(reviewer,detail);transition(reviewer,app+':'+action,obj,values,state,app,name)
        visit(reviewer,detail);capture(reviewer,app+'-closed',True);obj.refresh_from_db()
        revisions=list(obj.review_revisions.values('sequence','state','reason'))
        mark(app+':detail',obj.status=='closed',operational_status=obj.status,review_status=obj.review_status,review_revisions=revisions,record_review_controls=main(reviewer).locator('form[action*="record"]').count())
        before=model('audit','AuditEvent').objects.filter(entity_id=str(obj.pk)).count()
        status=post(reader,reverse(app+':close',args=[obj.pk]),{'closure_summary':'forged'})
        mark(app+':close',status in [403,404] and before==model('audit','AuditEvent').objects.filter(entity_id=str(obj.pk)).count(),restricted_post=status)
        visit(reviewer,reverse(app+':list'));capture(reviewer,app+'-list',True);mark(app+':list',('B04-'+app).upper() in text(reviewer))

def expenses(maker,approver,reader,foreign):
    group=get('expenses','PlatformExpenseGroup',code='other')
    category=create(maker,'expenses:category_create',dict(code='B04-CAT',name='هزینه کارگاهی B04',primary_group=group.pk),'expenses','ExpenseCategory',dict(organization_id=ids['expense_org'],code__iexact='B04-CAT'))
    if category:
        visit(maker,reverse('expenses:category_detail',args=[category.pk]));capture(maker,'expense-category-detail');mark('expenses:category_detail',category.name in text(maker))
        visit(maker,reverse('expenses:category_list'));capture(maker,'expense-category-list');mark('expenses:category_list',category.name in text(maker))
    vals=dict(project=ids['expense_project'],description='هزینه مستقیم آزمون B04',amount='125000',incurred_on='2026-11-12',category='other',vendor_name='فروشنده آزمون',receipt_reference='B04-receipt',classification='direct',source_reference='B04-INV1')
    if category:vals['expense_category']=category.pk
    draft=create(maker,'expenses:draft_create',vals,'expenses','Expense',dict(organization_id=ids['expense_org'],source_reference='B04-INV1'),True)
    if draft:
        detail=reverse('expenses:detail',args=[draft.pk]);visit(maker,detail);capture(maker,'expense-draft-detail',True);mark('expenses:detail',draft.description in text(maker),amount=draft.amount,status=draft.status)
        f=form(maker,'/allocate/');fill(f,project=ids['expense_project'],wbs_node=ids['wbs'],cbs_node=ids['cbs'],cost_center=ids['cost_center'],amount='125000',allocation_basis_reference='تخصیص مصنوعی بودجه پذیرفته شده');click(f)
        mark('expenses:allocate',draft.allocations.count()==1,allocations=list(draft.allocations.values('amount','project_id','wbs_node_id','cbs_node_id','cost_center_id')))
        visit(maker,detail);transition(maker,'expenses:submit',draft,{},'submitted','expenses','Expense')
        mark('expenses:approve',post(maker,reverse('expenses:approve',args=[draft.pk])) in [400,403],boundary='self approval')
        visit(approver,detail);transition(approver,'expenses:approve',draft,{},'approved','expenses','Expense');capture(approver,'expense-approved',True)
        n=model('audit','AuditEvent').objects.filter(entity_id=str(draft.pk)).count();s=post(approver,reverse('expenses:approve',args=[draft.pk]));mark('expenses:approve',s in [400,403] and n==model('audit','AuditEvent').objects.filter(entity_id=str(draft.pk)).count(),replay_status=s)
        mark('expenses:detail',visit(foreign,detail) in [403,404],boundary='foreign')
    vals.update(description='هزینه بازگشتی B04',amount='75000',source_reference='B04-INV2',receipt_reference='B04-receipt-2')
    second=create(maker,'expenses:draft_create',vals,'expenses','Expense',dict(organization_id=ids['expense_org'],source_reference='B04-INV2'))
    if second:
        detail=reverse('expenses:detail',args=[second.pk]);visit(maker,detail);fill(form(maker,'/allocate/'),project=ids['expense_project'],wbs_node=ids['wbs'],cbs_node=ids['cbs'],cost_center=ids['cost_center'],amount='75000',allocation_basis_reference='مبنای آزمون');click(form(maker,'/allocate/'))
        visit(maker,detail);transition(maker,'expenses:submit',second,{},'submitted','expenses','Expense')
        visit(approver,detail);transition(approver,'expenses:return',second,{'reason':'اصلاح رسید آزمایشی'},'returned','expenses','Expense')
        visit(maker,detail);transition(maker,'expenses:void',second,{'reason':'ابطال مصنوعی'},'void','expenses','Expense')
    legacy=create(maker,'expenses:create',dict(project=ids['expense_project'],description='هزینه ثبت قدیمی B04',amount='25000',incurred_on='2026-11-12',category='other',receipt_reference='B04-legacy'),'expenses','Expense',dict(organization_id=ids['expense_org'],description='هزینه ثبت قدیمی B04'))
    template=create(maker,'expenses:recurrences',dict(project=ids['expense_project'],description='تکرار مصنوعی B04',amount='75000',classification='direct',frequency='weekly',starts_on='2026-11-12',source_reference_prefix='B04-REC'),'expenses','RecurringExpenseTemplate',dict(organization_id=ids['expense_org'],description='تکرار مصنوعی B04'))
    if template:
        url=reverse('expenses:recurrence_propose',args=[template.pk]);visit(maker,reverse('expenses:recurrences'));fill(form(maker,'/propose/'),occurrence_on='2026-11-12');click(form(maker,'/propose/'));mark('expenses:recurrence_propose',model('expenses','Expense').objects.filter(organization_id=ids['expense_org'],source_reference__startswith='B04-REC').exists(),feedback=text(maker)[-1200:])
    if category:
        url=reverse('expenses:category_archive',args=[category.pk]);s=post(maker,url);category.refresh_from_db();mark('expenses:category_archive',category.archived_at is not None,status=s,archived=category.archived_at)
    visit(maker,reverse('expenses:list'));capture(maker,'expenses-list',True);mark('expenses:list','B04' in text(maker))
    mark('expenses:draft_create',visit(reader,reverse('expenses:draft_create')) in [403,404],boundary='reader')

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True,args=['--disable-gpu','--no-first-run'],env={**os.environ,'TEMP':str(root),'TMP':str(root)})
    print('Chrome',browser.version,flush=True)
    people={name:login(browser,name) for name in cfg['actors']}
    owner=people['b02-owner'];reviewer=people['b02-b04-reviewer'];reader=people['b02-b04-reader'];foreign=people['b04-foreign'];scoped=people['b02-b04-scoped'];wrong=people['b02-b04-sibling']
    selected=os.environ.get('B04_PART','all')
    if selected in ['all','equipment']:task('equipment',lambda:equipment(owner,reviewer,reader,foreign,scoped,wrong))
    if selected in ['all','costs']:task('costs',lambda:costs(owner,reviewer))
    if selected in ['all','hseq']:task('hseq',lambda:hseq(owner,reviewer,reader,foreign,scoped,wrong))
    if selected in ['all','expenses']:task('expenses',lambda:expenses(people['expense-control-maker'],people['expense-control-approver'],reader,foreign))
    browser.close()
save()
