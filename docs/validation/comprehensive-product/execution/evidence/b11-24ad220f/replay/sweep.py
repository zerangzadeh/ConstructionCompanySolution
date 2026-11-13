"""B11 Chrome route and state observations against the isolated MVP profile."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import UUID

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = REPO / 'docs/validation/comprehensive-product/execution/evidence/b11-24ad220f'
sys.path.insert(0,'C:/Users/azera/AppData/Local/Temp/bonira-b02-01a1c63c/pylibs')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import connection
from django.test import Client
from django.test.utils import setup_test_environment
from django.urls import resolve, reverse, Resolver404
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.product_surface import route_exposed, route_capability, is_platform_workspace_route
from playwright.sync_api import sync_playwright

ROWS = [r for r in csv.DictReader((ROOT/'entry-TEST_EXECUTION_MATRIX_MVP.csv').open(encoding='utf-8-sig',newline='')) if r['Batch']=='B11']
WIDTHS = ((1440,900),(1024,768),(390,844))
MISSING = UUID(int=1)
DB = settings.DATABASES['default']['NAME']
with connection.cursor() as cursor:
    cursor.execute("select current_database(), current_setting('data_directory'), current_setting('server_version')")
    database,directory,pg_version=cursor.fetchone()
assert DB == database and Path(directory).resolve() == ROOT/'pg'
assert settings.PRODUCT_SURFACE_PROFILE == 'MVP'

def write(file,obj):
    (OUT/file).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')

def model_first(org, label, **filters):
    model = apps.get_model(label)
    query = model.objects
    if org and any(f.name == 'organization' for f in model._meta.fields):
        query = query.filter(organization=org)
    return query.filter(**filters).first()

def sessions(actors):
    result = {}
    for name,(user,org) in actors.items():
        if user is None:
            result[name]=None
            continue
        client=Client()
        client.force_login(user)
        s=client.session
        if org:
            s['active_organization_id']=str(org.pk)
        s.save()
        result[name]=s.session_key
    return result

def load_fixtures():
    from fixtures import seed
    from apps.accounts.models import User
    from apps.organizations.models import Organization
    seed_file=ROOT/os.environ.get('B11_FIXTURE_FILE','private-fixtures.json')
    if not seed_file.exists():
        assert not User.objects.exists()
        setup_test_environment()
        actors,sources,results=seed()
        seed_file.write_text(json.dumps({'actors':{k:[str(u.pk) if u else None,str(o.pk) if o else None] for k,(u,o) in actors.items()},
                                         'sources':{k:[v._meta.label,str(v.pk)] for k,v in sources.items()},
                                         'results':results}),encoding='utf-8')
        write(DB+'-fixture-groups.json',results)
        return actors,sources
    obj=json.loads(seed_file.read_text())
    actors={k:(User.objects.get(pk=u) if u else None, Organization.objects.get(pk=o) if o else None) for k,(u,o) in obj['actors'].items()}
    sources={k:apps.get_model(label).objects.get(pk=pk) for k,(label,pk) in obj['sources'].items()}
    return actors,sources

def actor_for(row):
    route=row['Route_Name']; mod=row['Module']; raw=row['URL']
    if route.startswith('accounts:password_reset') or route=='accounts:login': return 'anonymous'
    if route=='accounts:required_password_change': return 'required'
    if route=='organizations:create' or is_platform_workspace_route(route): return 'platform'
    if route=='organizations:role_catalog': return 'role-reader'
    if mod in ('documents',) or route.startswith('contracts:contractual'): return 'docs'
    if mod in ('safety','quality','projects','timekeeping','workforce','daily_reports'): return 'field'
    if mod=='inventory' and any(word in route for word in ('transfer','custody','warehouse','count','reservation')): return 'inventory'
    if route.startswith('billing:payable_'): return 'payable'
    if mod=='billing' or mod=='contracts': return 'billing'
    if route=='workflows:manager_workspace': return 'team-manager'
    if route=='workflows:my_requests': return 'requests-person'
    if mod=='workflows': return 'workflow'
    if route in ('procurement:portal_accept','procurement:portal_context','procurement:portal_receipt','procurement:portal_submit'): return 'supplier'
    if mod=='procurement' and ('rfq' in route or 'portal' in route or 'custody' in route): return 'rfq'
    return 'ops'

def route_plan(row,actors,sources):
    route=row['Route_Name']; raw=row['URL']; mod=row['Module']
    actor=actor_for(row)
    if actor not in actors: actor='ops' if 'ops' in actors else 'field' if 'field' in actors else 'anonymous'
    org=actors[actor][1]
    special=re.search(r'/evidence/(\w+)/',raw)
    kind=special.group(1) if special else 'safety'
    target=re.search(r'/context/(\w+)/',raw)
    target_type=target.group(1) if target else 'project'
    time_match=re.search(r'/records/(\w+)/',raw)
    record_kind=time_match.group(1) if time_match else 'attendance'
    action='capture' if route=='procurement:rfq_buyer_action' else 'archive'
    map_objects={
        'organization_id':'company','user_id':'platform-user','baseline_id':'billing-baseline',
        'claim_id':'claim','document_id':'document','source_id':'evidence-'+kind,'version_id':'document-version',
        'target_id':'dms-'+target_type,'rfq_id':'rfq','order_id':'order','receipt_id':'portal-receipt' if route=='procurement:portal_receipt' else 'receipt',
        'invitation_id':'invitation','revision_id':'quote-revision','equipment_id':'field-equipment' if actor=='field' else 'ops-equipment',
        'employee_id':'field-employee','phase_id':'field-main-phase','report_id':'ops-report' if '?format=print' in raw else 'field-report',
        'incident_id':'safety','issue_id':'quality','transfer_id':'transfer','warehouse_id':'warehouse',
        'transaction_id':'stock','work_item_id':'work-item','work_order_id':'field-work-order','count_id':'count','grant_id':'portal-grant',
        'request_id':'rfq-request' if actor=='rfq' else 'workflow-request' if actor=='workflow' else None,
        'project_id':'field-main-project','site_id':'field-main-site',
        'contract_id':'billing-contract','certificate_id':'payable-certificate','measurement_id':'payable-measurement'
    }
    if route=='daily_reports:detail' and '?format=print' in raw and 'ops' in actors:
        actor='ops'; org=actors[actor][1]
    if mod=='equipment':
        actor='field' if 'field' in actors else actor
        org=actors[actor][1]
        map_objects['equipment_id']='field-equipment'
    if route=='organizations:member_detail' or route.startswith('organizations:member_') and 'platform' not in route:
        actor='tenant' if 'tenant' in actors else actor; org=actors[actor][1]
        map_objects['membership_id']='membership'
    if mod=='procurement' and route.startswith('procurement:request_') and 'workflow' in actors:
        actor='workflow'; org=actors[actor][1]; map_objects['request_id']='workflow-request'
    fallback_models={
        'guarantee_id':'billing.ContractGuarantee','evidence_id':'billing.ContractComplianceEvidence',
        'release_id':'billing.RetentionRelease','invoice_id':'billing.TaxpayerInvoice','assessment_id':'billing.ContractorComplianceAssessment',
        'measurement_id':'billing.PayableMeasurement','certificate_id':'billing.PayableCertificate',
        'term_id':'contracts.ContractTermVersion','observation_id':'daily_reports.FieldObservation',
        'estimate_id':'estimates.Estimate','expense_id':'expenses.Expense','category_id':'materials.MaterialCategory',
        'material_id':'materials.Material','party_id':'parties.BusinessParty','count_id':'inventory.InventoryCount',
        'assignment_id':'equipment.EquipmentAssignment','allocation_id':'equipment.EquipmentCostAllocation',
        'envelope_id':'equipment.EquipmentCostSourceEnvelope','work_order_id':'equipment.EquipmentWorkOrder',
        'timesheet_id':'timekeeping.Timesheet','award_id':'procurement.RFQAward','grant_id':'procurement.SupplierPortalAccessGrant'
    }
    records={'attendance':'timekeeping.AttendanceRecord','correction':'timekeeping.AttendanceCorrectionRequest','leave':'timekeeping.LeaveMissionRequest','overtime':'timekeeping.OvertimeRequest'}
    if 'record_id' in raw:
        fallback_models['record_id']={'billing':'billing.ProgressRecord','contracts':'contracts.ContractualRecord',
                                    'equipment':'equipment.MaintenanceRecord','timekeeping':records[record_kind]}.get(mod)
    if mod=='daily_reports' and 'observation_id' in raw and 'docs' in actors:
        actor='docs'; org=actors[actor][1]; map_objects['observation_id']='evidence-field_observation'
    if route.startswith('billing:guarantee_') or route.startswith('billing:compliance_evidence_') or route.startswith('billing:retention_release_'):
        if 'docs' in actors:
            actor='docs'; org=actors[actor][1]
    if mod=='documents' and route=='documents:evidence-detail' and kind in ('guarantee','compliance','release'):
        map_objects['source_id']='evidence-'+kind
    if route=='documents:employee-detail': map_objects['document_id']='document'
    if mod in ('expenses','materials') and 'category_id' in raw:
        map_objects['category_id']='expense-category' if mod=='expenses' else 'material-category'
    missing=[]
    def convert(match):
        key=match.group(1).split(':')[-1]
        if key=='target_type': return target_type
        if key=='kind': return kind if mod=='documents' else record_kind
        if key=='action': return action
        if key in ('uidb64','token'):
            u=actors['auth-user'][0]
            return urlsafe_base64_encode(force_bytes(u.pk)) if key=='uidb64' else default_token_generator.make_token(u)
        obj=sources.get(map_objects.get(key))
        if key=='version_id' and route=='documents:evidence-detail':
            from apps.documents.evidence import resolve_evidence_source,references
            from apps.documents.models import DocumentVersion
            source=resolve_evidence_source(user=actors[actor][0],organization=org,kind=kind,identifier=sources['evidence-'+kind].pk)
            pinned=list(references(source))
            obj=DocumentVersion.objects.filter(pk=pinned[0][0]).first() if pinned else None
        if key=='record_id' and mod=='timekeeping' and record_kind=='attendance':
            obj=sources.get('field-attendance')
        if key=='record_id' and mod=='equipment':
            obj=sources.get('maintenance')
        if key=='record_id' and mod=='contracts':
            obj=sources.get('evidence-contractual')
        if obj is None and fallback_models.get(key):
            try:
                obj=model_first(org,fallback_models[key])
            except LookupError:
                pass
        if obj is None:
            missing.append(key)
        return str(obj.pk if obj else MISSING)
    path=re.sub(r'<([^>]+)>',convert,raw)
    try:
        match=resolve(urlsplit(path).path)
        capability=route_capability(match.view_name,match.kwargs)
        exposed=route_exposed(match.view_name,match.kwargs,user=actors[actor][0])
        actual=match.view_name
    except Resolver404:
        actual='UNRESOLVED'; capability=''; exposed=False
    return {'actor':actor,'path':path,'missing':missing,'route':actual,'capability':capability,'exposed':exposed}

def host():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    log=(ROOT/'private-django.log').open('ab')
    proc=subprocess.Popen([sys.executable,'manage.py','runserver','--noreload','--insecure',f'127.0.0.1:{port}'],cwd=REPO,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(80):
        try:
            with urlopen(origin+'/accounts/login/',timeout=1) as response:
                assert response.status==200
                return proc,origin,log
        except OSError:
            if proc.poll() is not None: break
            time.sleep(.25)
    proc.terminate(); log.close()
    raise RuntimeError('Private Django listener did not become ready')

OBSERVE = r"""() => {
const main = document.querySelector('main');
const root = main || document.body;
const visible = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility === 'visible' && !el.closest('[inert],[aria-hidden=true]');
const name = el => el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') || '').split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ').trim() || [...(el.labels || [])].map(l => l.textContent.trim()).join(' ') || el.getAttribute('title') || el.getAttribute('alt') || (el.matches('button,a,[role=button]') ? el.textContent.trim() : '');
const controls = [...root.querySelectorAll('input:not([type=hidden]),select,textarea,[role=combobox],button,a[href]')].filter(visible);
const forms = [...root.querySelectorAll('form')].filter(visible);
const text = root.innerText || '';
const heads = [...root.querySelectorAll('h1,h2')].filter(visible).map(el => el.innerText.trim().slice(0,100));
const safe = value => (value || '').replace(/([a-f0-9]{8}-[a-f0-9-]{27})/ig,'[uuid]').slice(0,150);
const duplicates = [...new Set(controls.filter(el => el.matches('a[href]')).map(el => el.getAttribute('href')))].filter(href => href && href.startsWith('/') && controls.filter(el => el.getAttribute('href')===href).length>1);
return {width: document.documentElement.clientWidth, scrollWidth:document.documentElement.scrollWidth,
  lang:document.documentElement.lang,dir:getComputedStyle(document.documentElement).direction,
  font:getComputedStyle(root).fontFamily, localFont:document.fonts.check('14px Vazirmatn'),
  mains:document.querySelectorAll('main').length, heads:heads.slice(0,14).map(safe),
  table: [...root.querySelectorAll('table')].filter(visible).length,
  forms:forms.length, primary:[...root.querySelectorAll('.btn-primary')].filter(visible).length,
  visibleInputs:controls.filter(el=>el.matches('input,select,textarea,[role=combobox]')).length,
  unnamed:controls.filter(el=>!name(el).trim() && !el.matches('a[href]')).slice(0,14).map(el=>({tag:el.tagName,id:el.id,field:el.name||'',role:el.getAttribute('role'),type:el.type||'',html:safe(el.outerHTML)})),
  duplicates:duplicates.map(safe).slice(0,8),
  uuidCount:(text.match(/\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b/gi)||[]).length,
  jalali:(text.match(/(?:۱۳|۱۴|13|14)[0-9۰-۹]{2}[/\-][0-9۰-۹]{1,2}[/\-][0-9۰-۹]{1,2}/g)||[]).slice(0,4),
  textLength:text.length, path:location.pathname};
}"""

class Browser:
    def __init__(self,browser,origin,actors,auth):
        self.browser=browser;self.origin=origin;self.actors=actors;self.auth=auth;self.contexts={}
    def page(self, actor):
        if actor not in self.contexts:
            ctx=self.browser.new_context(viewport={'width':1440,'height':900},locale='fa-IR',timezone_id='Asia/Tehran')
            if self.auth[actor]:
                ctx.add_cookies([{'url':self.origin,'name':settings.SESSION_COOKIE_NAME,'value':self.auth[actor],'httpOnly':True}])
            page=ctx.new_page()
            page.set_default_timeout(4000)
            page.set_default_navigation_timeout(12000)
            failures=[]
            page.on('pageerror',lambda err:failures.append({'js':str(err)[:160]}))
            page.on('response',lambda response: failures.append({'status':response.status,'path':urlsplit(response.url).path}) if response.status >=500 else None)
            page.on('requestfailed',lambda request: failures.append({'network':request.failure,'path':urlsplit(request.url).path}) if request.failure not in ('net::ERR_ABORTED',) else None)
            self.contexts[actor]=(ctx,page,failures)
        return self.contexts[actor][1]
    def get(self,actor,path):
        page=self.page(actor)
        return page,page.goto(self.origin+path,wait_until='domcontentloaded')
    def bounds(self,page):
        items=[]
        for width,height in WIDTHS:
            page.set_viewport_size({'width':width,'height':height})
            page.evaluate("async () => { await document.fonts.ready; await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); }")
            value=page.evaluate(OBSERVE)
            items.append(value)
        return items
    def request(self,actor,path,method='GET',**kwargs):
        ctx=self.page(actor).context
        return ctx.request.fetch(self.origin+path,method=method,max_redirects=0,timeout=12000,**kwargs)
    def link(self,page,path,region='main'):
        p=urlsplit(path)
        return page.locator(f'{region} a[href]').evaluate_all("""(els,p) => els.map(e=>({href:e.getAttribute('href'),text:e.innerText.trim(),visible:!!e.getClientRects().length})).filter(e=>{const u=new URL(e.href,location.href);return u.pathname===p[0] && (!p[1] || u.search===p[1]);})""",[p.path,'?'+p.query if p.query else ''])

def negatives(run,plan,row):
    actor=plan['actor']; path=plan['path']
    if actor in ('anonymous','required'):
        return {}
    checks={}
    for variant in ('limited','sibling','foreign'):
        key=actor+'-'+variant
        if is_platform_workspace_route(row['Route_Name']):
            key='tenant' if variant=='limited' else key
        if key not in run.actors and variant=='foreign' and '<uuid:' in row['URL']:
            key='foreign' if actor!='ops' else 'docs-foreign'
        if key in run.actors:
            response=run.request(key,path)
            checks[key]={'status':response.status,'location':urlsplit(response.headers.get('location','')).path}
    return checks

def row_observation(run,plan,row):
    route=row['Route_Name']
    actor=plan['actor']; path=plan['path']
    result={**plan,'path':re.sub(r'(/accounts/password/reset/)[^/]+/[^/]+/',r'\1[redacted]/',path)}
    if plan['route']!=route:
        result['condition']='Inventory route resolves to '+plan['route'];return result
    if row['Method']=='POST':
        if plan['missing']:
            result['condition']='Missing positive action fixture: '+', '.join(plan['missing'])
            return result
        response=run.request(actor,path,'GET')
        denied=run.request(actor,path,'POST',form={})
        result.update({'get_status':response.status,'token_free_post_status':denied.status,
                       'condition':'Action requires visible source control and valid state'})
        parents={
            'contracts:term_insurance_select':r'/terms/[^/]+/insurance/$',
            'daily_reports:field_observation_save':r'/save/$',
            'inventory:transaction_post':r'/post/$',
            'materials:governance_action':r'/actions/[^/]+/$',
            'parties:governance_action':r'/actions/[^/]+/$',
            'procurement:portal_submit':r'/submit/$',
        }
        if route.startswith('procurement:') and route not in parents:
            parents[route]=r'/[^/]+/$'
        if route.startswith('workflows:'):
            parent=reverse('workflows:workbench')
        elif route.startswith('organizations:'):
            parent=path
        elif route in parents:
            parent=re.sub(parents[route],'/',path)
        else:
            parent=''
        if parent:
            page,pr=run.get(actor,parent)
            result['source_page']={'url':parent,'status':pr.status}
            if pr.status==200 and urlsplit(page.url).path==urlsplit(parent).path:
                controls=page.locator(f"main form[action='{path}'] button, main a[href='{path}']")
                result['source_page']['matching_controls']=controls.count()
                result['source_page']['control_names']=controls.all_text_contents()[:8]
        result['negative']=negatives(run,plan,row)
        return result
    if route in ('documents:archive','documents:link-add','documents:version-add'):
        response=run.request(actor,path)
        result['action_get_status']=response.status
        path=reverse('documents:detail',args=[path.split('/')[2]])
        result['source_control_page']=path
    if not plan['exposed'] and plan['capability']=='full_hr':
        response=run.request('docs',path)
        result.update({'get_status':response.status,'condition':'MVP profile exclusion'})
        return result
    if plan['missing']:
        result['condition']='Missing positive source fixture: '+', '.join(plan['missing'])
        return result
    page=run.page(actor)
    flags=run.contexts[actor][2]
    flags.clear()
    page.set_viewport_size({'width':1440,'height':900})
    _,response=run.get(actor,path)
    final=urlsplit(page.url).path
    result.update({'status':response.status if response else None,'final':re.sub(r'(/accounts/password/reset/)[^/]+/[^/]+/',r'\1[redacted]/',final)})
    if response and response.status==200 and (final==urlsplit(path).path or route=='accounts:password_reset_confirm'):
        if 'application/json' in response.headers.get('content-type',''):
            result['content_type']='json'
        else:
            result['widths']=run.bounds(page)
            # Native keyboard behavior at the narrowest width, without invoking any action.
            page.evaluate("() => { document.activeElement?.blur(); window.scrollTo(0,0); }")
            trace=[]
            for _ in range(3):
                page.keyboard.press('Tab')
                trace.append(page.evaluate("""() => {const e=document.activeElement, s=getComputedStyle(e);return {tag:e.tagName,focusVisible:e.matches(':focus-visible'),outline:s.outlineStyle,outlineWidth:s.outlineWidth,insideMain:!!e.closest('main'),named:!!(e.innerText?.trim()||e.getAttribute('aria-label')||e.labels?.length||e.getAttribute('aria-labelledby'))};}"""))
            result['keyboard_entry']=trace
            if any(x['scrollWidth']>x['width']+1 or x['uuidCount'] for x in result['widths']):
                shot=OUT/'reproductions';shot.mkdir(exist_ok=True)
                bad=next(x for x in reversed(result['widths']) if x['scrollWidth']>x['width']+1 or x['uuidCount'])
                page.set_viewport_size({'width':bad['width'],'height':dict(WIDTHS)[bad['width']]})
                # Never save credential or recovery pages.
                if not route.startswith('accounts:'):
                    page.screenshot(path=shot/(row['Inventory_ID'].lower()+'.png'),animations='disabled')
    result['browser_issues']=list(flags)
    result['negative']=negatives(run,plan,row)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--only')
    parser.add_argument('--label',default='original')
    args=parser.parse_args()
    actors,sources=load_fixtures()
    auth=sessions(actors)
    plans={r['Execution_ID']:route_plan(r,actors,sources) for r in ROWS}
    proc,origin,log=host()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            write('environment.json',{'chrome':browser.version,'postgresql':pg_version,'database':DB,'profile':'MVP','viewports':WIDTHS,'fixtures':'synthetic, private cluster and storage'})
            run=Browser(browser,origin,actors,auth)
            outcomes={}
            for row in ROWS:
                key=row['Execution_ID']
                if args.only and not re.search(args.only,key,re.I):continue
                try:
                    outcomes[key]=row_observation(run,plans[key],row)
                except Exception as exc:
                    outcomes[key]={'actor':plans[key]['actor'],'condition':'Harness exception '+type(exc).__name__}
                    import traceback
                    traceback.print_exc()
                if len(outcomes)%10==0:
                    write(args.label+'-route-observations.json',outcomes)
                    print('Rows observed',len(outcomes),flush=True)
            write(args.label+'-route-observations.json',outcomes)
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=15)
        log.close()

if __name__=='__main__':
    main()












