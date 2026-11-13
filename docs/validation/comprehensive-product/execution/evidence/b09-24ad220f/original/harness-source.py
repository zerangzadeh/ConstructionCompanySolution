"""B09 real Chrome + PostgreSQL + private storage validation, isolated only."""
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,'C:/Users/azera/AppData/Local/Temp/bonira-b02-01a1c63c/pylibs')
os.environ['DJANGO_SETTINGS_MODULE']='b09_settings'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']='true'
import csv
import hashlib
import json
import re
import socket
import subprocess
import time
import traceback
from datetime import timedelta
from types import MethodType
from urllib.request import urlopen
from uuid import uuid4
import django
django.setup()
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.documents.models import Document, DocumentVersion, DocumentLink
from apps.documents.services import add_document_version, record_document_processing_assessment
from apps.documents.evidence import evidence_panel, references, resolve_evidence_source
from apps.organizations.models import BusinessPermission, OrganizationRole, MembershipScopeGrant, MembershipRoleAssignment
from apps.projects.models import Project
from core.product_surface import route_exposed, route_capability

EVIDENCE=REPO/'docs/validation/comprehensive-product/execution/evidence/b09-24ad220f'
PHASE=os.environ.get('B09_PHASE','original')
OUT=EVIDENCE/PHASE
OUT.mkdir(exist_ok=True)
assert settings.DATABASES['default']['NAME']=='b09_'+PHASE
with connection.cursor() as c:
    c.execute("SELECT current_database(), current_setting('data_directory'), version()")
    DB,DIRECTORY,PG_VERSION=c.fetchone()
    assert Path(DIRECTORY).resolve()==(ROOT/'pg').resolve()
MATRIX=[r for r in csv.DictReader((ROOT/'entry-TEST_EXECUTION_MATRIX_MVP.csv').open(encoding='utf-8-sig',newline='')) if r['Batch']=='B09']
assert len(MATRIX)==65
ASSETS=json.loads((EVIDENCE/'assets-and-scan.json').read_text())
assert ASSETS['scanner']['exit_code']==0 and 'found no threats' in ASSETS['scanner']['stdout']

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')

def upload(n=1):
    p=ROOT/'assets'/f'b09-v{n}.pdf'
    return SimpleUploadedFile(p.name,p.read_bytes(),content_type='application/pdf')

def witness():
    result={}
    with connection.cursor() as c:
        for table in sorted(connection.introspection.table_names()):
            if table in {'django_session','django_migrations'} or table.startswith('auth_'):continue
            c.execute(f'SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text,\'\' ORDER BY row_to_json(t)::text),\'\')) FROM "{table}" t')
            result[table]=c.fetchone()
    files={p.relative_to(settings.DOCUMENT_PROTECTED_ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in Path(settings.DOCUMENT_PROTECTED_ROOT).rglob('*') if p.is_file()}
    return {'tables':result,'storage':files}

def assess(f,version,verdict='clean'):
    data=version.file.read();version.file.close()
    digest=hashlib.sha256(data).hexdigest()
    assert digest==version.sha256
    assert digest in {v['sha256'] for k,v in ASSETS.items() if k!='scanner'}
    return record_document_processing_assessment(version=version,actor=f.operator,verdict=verdict,
        adapter_code='b09-local-defender-verified-assets',adapter_version='MpCmdRun',
        details={'scope':'Actual local on-demand scan of hash-identical generated assets; external DMS scanner integration unverified',
                 'input_sha256':digest,'scanner_exit_code':ASSETS['scanner']['exit_code'],
                 'test_quarantine':verdict!='clean'})

def persona(f,name,codes,project=None):
    u=User.objects.create_user(username='b09-'+name)
    role=OrganizationRole.objects.create(organization=f.organization,code='b09-'+name,name=name)
    role.permissions.set(BusinessPermission.objects.filter(code__in=codes,is_active=True))
    m=f.organization.memberships.create(user=u,status='active',role_definition=role,authorization_migrated_at=timezone.now())
    MembershipRoleAssignment.objects.create(organization=f.organization,membership=m,role=role,reason='Isolated B09 explicit persona')
    MembershipScopeGrant.objects.create(organization=f.organization,membership=m,scope_type='project' if project else 'organization',project=project,reason='Isolated B09 explicit scope')
    return u

@transaction.atomic
def seed():
    from apps.documents.test_evidence_integration import EvidenceIntegrationTests
    from apps.documents.test_related_documents import RelatedDocumentsTests
    from apps.organizations.access_services import assign_platform_role
    f=EvidenceIntegrationTests();f.client=Client();f.setUp();f.media_override.disable()
    f._pdf_upload=lambda *args,**kwargs:upload(2 if kwargs.get('suffix') else 1)
    assigner=User.objects.create_superuser(username='b09-technical-assigner')
    approver=User.objects.create_superuser(username='b09-technical-approver')
    f.operator=User.objects.create_user(username='b09-processing-operator')
    assign_platform_role(actor=assigner,approver=approver,target=f.operator,role='platform_operations',reason='Isolated synthetic document processing assessment')
    f.clean_version=lambda version:assess(f,version)
    f.generic=dict(zip(('project','contract','estimate','expense','daily_report'),RelatedDocumentsTests.targets(f),strict=True))
    f.special={'safety':f.safety(),'quality':f.quality(),'field_observation':f.observation(),'material':f.material()}
    f.special.update(dict(f.commercial()))
    from apps.contracts.contractual_services import create_contractual_record
    f.special['contractual']=create_contractual_record(organization=f.organization,actor=f.owner,contract=f.contract,kind='claim',record_number='B09-CR',title='رکورد قراردادی شاهد',description='شاهد بدون اثر مالی خودکار',idempotency_key='b09-contractual-source')
    f.record=f.special['contractual']
    f.doc=f._create_document(reference='B09-EVIDENCE',title='سند شاهد آزمون بنیرا')
    assess(f,f.doc.current_version)
    from apps.contracts.models import Contract
    f.origin_contract=Contract.objects.create(organization=f.organization,project=f.project,contract_number='B09-ORIGIN',title='قرارداد منبع سند مشترک',counterparty_name='طرف نمونه',direction='receivable')
    f.second=f._create_document(reference='B09-CHOICE',title='سند قابل انتخاب بنیرا',target=f.origin_contract)
    assess(f,f.second.current_version)
    foreign_project=Project.objects.create(organization=f.other_organization,code='B09-F',name='FOREIGN B09 project')
    f.foreign=f._create_document(organization=f.other_organization,actor=f.other_user,target=foreign_project,reference='B09-FOREIGN',title='FOREIGN B09 PRIVATE')
    f.sibling_project=Project.objects.create(organization=f.organization,code='B09-SIB',name='پروژه خواهر محدود')
    codes=list(BusinessPermission.objects.filter(is_active=True).values_list('code',flat=True))
    views=[p for p in codes if p.endswith('.view')]
    dms=[p for p in codes if p in {'documents.view','documents.upload','documents.download'} or p.endswith('.view')]
    f.uploader=persona(f,'uploader',dms)
    f.linker=persona(f,'linker',dms)
    f.reviewer=f.manager
    f.readonly=persona(f,'readonly',views)
    f.nodownload=persona(f,'no-download',[p for p in codes if p!='documents.download'])
    f.denied=persona(f,'no-authority',[])
    f.sibling=persona(f,'sibling-project',codes,project=f.sibling_project)
    f.first=f.doc.current_version
    return f

class Runner:
    def __init__(self,browser,origin,f):
        self.browser=browser;self.origin=origin;self.f=f
        self.results={};self.supplemental={};self.pages={};self.responses=[];self.views={};self.current=None
    def actor(self,user=None,org=None):
        key=(str(user.pk) if user else 'anonymous',str(org.pk) if org else '')
        if key in self.pages:return self.pages[key]
        ctx=self.browser.new_context(viewport={'width':1440,'height':960},accept_downloads=True)
        page=ctx.new_page();page.set_default_timeout(7000);page.set_default_navigation_timeout(45000)
        if user:
            client=Client();client.force_login(user);s=client.session
            if org:s['active_organization_id']=str(org.pk)
            s.save();ctx.add_cookies([{'url':self.origin,'name':settings.SESSION_COOKIE_NAME,'value':s.session_key,'httpOnly':True}])
        self.pages[key]=page;return page
    def record(self,r,case,method='GET',expected=(200,)):
        expected=(expected,) if isinstance(expected,int) else expected
        fact={'method':method,'url':r.url.split(self.origin,1)[-1],'status':r.status,'case':case,'expected':expected}
        self.current['http'].append(fact)
        assert r.status in expected,f'{case}: {fact}'
        return r
    def get(self,page,path,expected=200,case='authorized page'):
        r=page.goto(self.origin+path,wait_until='domcontentloaded')
        return self.record(r,case,expected=expected)
    def request(self,page,path,data=None,method='GET',expected=200,case='probe',csrf=True,files=None):
        cookies={x['name']:x['value'] for x in page.context.cookies()}
        headers={'X-CSRFToken':cookies.get(settings.CSRF_COOKIE_NAME,'')} if csrf else {}
        if method=='GET':r=page.context.request.get(self.origin+path,max_redirects=0)
        elif files:
            multi=dict(data or {})
            for name,p in files.items():multi[name]={'name':p.name,'mimeType':'application/pdf' if p.suffix=='.pdf' else 'application/octet-stream','buffer':p.read_bytes()}
            r=page.context.request.post(self.origin+path,multipart=multi,headers=headers,max_redirects=0)
        else:r=page.context.request.post(self.origin+path,form=data or {},headers=headers,max_redirects=0)
        return self.record(r,case,method,expected)
    def denied(self,page,path,method='GET',data=None,expected=(403,404),case='denied'):
        before=witness()
        r=self.request(page,path,data,method,expected,case)
        assert witness()==before,'Denied request changed business/audit/storage'
        text=r.text()
        for marker in ('%PDF-1.7','FOREIGN B09 PRIVATE',str(settings.DOCUMENT_PROTECTED_ROOT),'protected_documents/'):
            assert marker not in text,'Private payload leaked in denied response'
        assert not r.headers.get('content-type','').startswith(('application/pdf','image/'))
        self.current.setdefault('denials',[]).append({'case':case,'no_business_audit_storage_delta':True,'no_protected_payload':True})
        return r
    def observe(self,page,name,shots=False):
        page.locator('main').first.wait_for()
        observations=[]
        for width in (1440,1024,390):
            page.set_viewport_size({'width':width,'height':960 if width>390 else 844})
            item=page.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,dir:document.documentElement.dir,lang:document.documentElement.lang,headings:[...document.querySelectorAll('main h1,main h2')].map(x=>x.innerText),selectors:[...document.querySelectorAll('main select')].map(x=>({name:x.name,searchable:!!x.tomselect})),feedback:[...document.querySelectorAll('main .errorlist,main [role=alert]')].map(x=>x.innerText),text:document.querySelector('main').innerText.slice(0,3500)})''')
            if shots:
                filename=f'{name}-{width}.png';page.screenshot(path=OUT/filename,animations='disabled');item['screenshot']=filename
            observations.append(item)
        page.set_viewport_size({'width':1440,'height':960})
        self.views[name]=observations;self.current.setdefault('design',[]).append(name)
        assert all(x['dir']=='rtl' and x['lang']=='fa' for x in observations),'Persian RTL failed'
        assert all(x['scrollWidth']<=x['width']+1 for x in observations),'Horizontal page overflow'
        assert not any(re.search(r'\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|\b[0-9a-f]{64}\b',x['text'],re.I) for x in observations),'Raw UUID/hash visible in business content'
        if page.locator('main [name=access_expires_at]').count():
            field=page.locator('main [name=access_expires_at]')
            self.current['expiry_widget']={'type':field.get_attribute('type'),'jalali':field.get_attribute('data-jalali-date')}
            assert field.get_attribute('data-jalali-date')=='datetime','Document expiry does not use the approved Jalali datetime input'
    def hidden(self,page,selector='main form'):
        return page.locator(selector).first.locator('input[type=hidden]').evaluate_all('(es)=>Object.fromEntries(es.map(e=>[e.name,e.value]))')
    def select(self,page,name,value):
        field=page.locator(f"main [name='{name}']").first
        if field.evaluate('e=>!!e.tomselect'):
            label=field.locator(f"option[value='{value}']").text_content().strip()
            control=page.locator('[id="'+field.evaluate('e=>e.tomselect.control_input.id')+'"]')
            control.fill(label.split(' · ')[0]);page.locator(f".ts-dropdown [data-value='{value}']:visible").first.click()
        else:field.select_option(str(value))
    def submit(self,page,path,selector='main form',expected=302):
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.split('?',1)[0]==self.origin+path) as captured:
            page.locator(selector).first.locator('button[type=submit],input[type=submit]').first.click()
            modal=page.locator('.swal2-confirm')
            if modal.is_visible():modal.click()
        self.record(captured.value,'Actual Chrome form submit','POST',expected)
        page.wait_for_load_state('domcontentloaded')
    def case(self,inventory,fn,scenario='CV-DOC-01'):
        key=inventory+'--'+scenario
        self.current={'execution_id':key,'http':[]}
        self.results[key]=self.current
        try:self.current.update(state=fn(),status='PASS')
        except Exception as exc:
            self.current.update(status='FAIL',error=str(exc),exception=type(exc).__name__)
            with (ROOT/f'{PHASE}-private-errors.log').open('a',encoding='utf-8') as stream:stream.write(key+'\n'+traceback.format_exc()+'\n')
        print(key,self.current['status'],flush=True)
        self.flush()
    def extra(self,key,fn):
        self.current={'http':[]};self.supplemental[key]=self.current
        try:self.current.update(state=fn(),status='PASS')
        except Exception as exc:
            self.current.update(status='FAIL',error=str(exc),exception=type(exc).__name__)
            with (ROOT/f'{PHASE}-private-errors.log').open('a',encoding='utf-8') as stream:stream.write(key+'\n'+traceback.format_exc()+'\n')
        print('SUPPLEMENT',key,self.current['status'],flush=True);self.flush()
    def flush(self):
        save('browser-rows.json',self.results);save('supplemental.json',self.supplemental);save('responsive.json',self.views)

def generic(run,f):
    from apps.documents.association import resolve_association_context
    from apps.documents.link_registry import registered_link_type
    p=run.actor(f.owner,f.organization);u=run.actor(f.uploader,f.organization);l=run.actor(f.linker,f.organization)
    denied=run.actor(f.denied,f.organization);foreign=run.actor(f.other_user,f.other_organization)
    sibling=run.actor(f.sibling,f.organization);reader=run.actor(f.readonly,f.organization)
    origins={}
    # One candidate is shared only where the actor has explicit authority for all contexts.
    for kind,target in f.generic.items():
        origins[kind]=resolve_association_context(user=f.owner,organization=f.organization,kind=kind,identifier=target.pk).source.url
    for action in ('choices','upload','link'):
        for kind,target in f.generic.items():
            def scenario(action=action,kind=kind,target=target):
                path=reverse('documents:contextual-'+action,args=[kind,target.pk])
                run.get(p,origins[kind]);assert p.locator(f"a[href='{path}']").count() or action=='choices'
                if action=='choices':run.observe(p,'generic-source-'+kind,shots=kind=='daily_report')
                page=l if action=='link' else u
                if action=='choices':
                    r=run.get(page,path);rows=r.json()['results']
                    assert str(f.second.pk) in {x['value'] for x in rows}
                    assert str(f.foreign.pk) not in {x['value'] for x in rows}
                    assert all('FOREIGN' not in x['label'] for x in rows)
                    run.get(page,path+'?q=NO-B09-MATCH');assert page.locator('body').inner_text().find('"results": []')>=0
                    state={'eligible_ids':[x['value'] for x in rows],'exact_source':str(target.pk)}
                else:
                    run.get(page,path);run.observe(page,f'context-{action}-{kind}',shots=kind=='project')
                    hidden=run.hidden(page)
                    assert hidden[kind]==str(target.pk)
                    if action=='upload':
                        page.locator('[name=title]').fill('سند زمینه‌ای '+kind)
                        page.locator('[name=reference]').fill('B09-UP-'+kind)
                        page.locator('[name=file]').set_input_files(str(ROOT/'assets'/'b09-v1.pdf'))
                        run.submit(page,path)
                        document=Document.objects.get(reference='B09-UP-'+kind,organization=f.organization)
                        assert not document.current_version.is_available
                        document_id=document.pk
                        run.denied(page,reverse('documents:download',args=[document_id]),case='Pending scan bytes denied')
                    else:
                        run.select(page,'document',f.second.pk);run.submit(page,path)
                        document=f.second;document_id=document.pk
                        # Replay retains a single relationship; form may reject already-selected choice.
                        before=DocumentLink.objects.filter(document=document).count()
                        run.request(page,path,{**hidden,'document':str(document.pk)},'POST',(302,400),case='Association replay')
                        assert DocumentLink.objects.filter(document=document).count()==before
                    link=DocumentLink.objects.get(document=document,**{kind:target})
                    typed=registered_link_type(kind).model
                    assert typed.objects.filter(document=document,**{kind:target}).count()==1
                    assert document.organization_id==target.organization_id==f.organization.pk
                    assert document.current_version.sha256==ASSETS['b09-v1.pdf']['sha256']
                    assert page.url.endswith(origins[kind])
                    state={'document':str(document_id),'target':str(target.pk),'typed_model':typed._meta.label,'compatibility_link':str(link.pk),'version':str(document.current_version_id),'sha256':document.current_version.sha256,'return':origins[kind]}
                for actor,label in ((denied,'No authority'),(foreign,'Foreign tenant'),(sibling,'Sibling project')):
                    run.denied(actor,path,case=label)
                run.denied(page,path+'?return_to=https://invalid.example/',case='Unsafe return denied')
                if action!='choices':
                    before=witness()
                    run.request(page,path,{'context_token':'forged','document':str(f.foreign.pk)},'POST',(400,403),case='Forged intent and foreign document')
                    assert witness()==before
                    run.denied(reader,path,method='POST',data={},case='Readonly mutation denied')
                return state
            run.case('INV-DOCUMENTS-CONTEXTUAL-'+action.upper()+'-TARGET-'+kind.upper().replace('_','-'),scenario)
        def aggregate(action=action):
            children=[k for k,v in run.results.items() if '-CONTEXTUAL-'+action.upper()+'-TARGET-' in k]
            assert len(children)==5 and all(run.results[k]['status']=='PASS' for k in children)
            return {'parameterized_evidence':children,'actual_browser_and_postgresql':True}
        run.case('INV-DOCUMENTS-CONTEXTUAL-'+action.upper(),aggregate)

    def listing():
        path=reverse('documents:list');run.get(p,path);assert f.doc.title in p.locator('main').inner_text()
        run.observe(p,'documents-list',True);run.denied(denied,path)
        run.get(foreign,path);assert f.doc.title not in foreign.locator('main').inner_text()
        return {'own_document_visible':True,'foreign_title_absent':True}
    run.case('INV-DOCUMENTS-LIST',listing)
    def detail():
        path=reverse('documents:detail',args=[f.doc.pk]);run.get(p,path);run.observe(p,'documents-detail',True)
        assert f.doc.title in p.locator('main').inner_text()
        assert str(settings.DOCUMENT_PROTECTED_ROOT) not in p.content()
        for a in (denied,foreign,sibling):run.denied(a,path)
        return {'current':str(f.first.pk),'source':str(f.project.pk)}
    run.case('INV-DOCUMENTS-DETAIL',detail)
    def new_upload():
        path=reverse('documents:upload');run.get(u,path);run.observe(u,'documents-upload',True)
        u.locator('[name=title]').fill('بارگذاری مستقل آزمون');u.locator('[name=reference]').fill('B09-ROOT-UP')
        run.select(u,'project',f.project.pk)
        u.locator('[name=file]').set_input_files(str(ROOT/'assets'/'b09-v1.pdf'))
        run.submit(u,path)
        d=Document.objects.get(reference='B09-ROOT-UP');assert d.current_version.sha256==ASSETS['b09-v1.pdf']['sha256']
        for a in (denied,reader):run.denied(a,path,method='POST')
        return {'document':str(d.pk),'hash':d.current_version.sha256,'pending_scan':not d.current_version.is_available}
    run.case('INV-DOCUMENTS-UPLOAD',new_upload)
    def version():
        detail=reverse('documents:detail',args=[f.doc.pk]);path=reverse('documents:version-add',args=[f.doc.pk]);run.get(u,detail)
        form=f"main form[action='{path}']"
        u.locator(form+' [name=file]').set_input_files(str(ROOT/'assets'/'b09-v2.pdf'));run.submit(u,path,form)
        f.doc.refresh_from_db();f.v2=f.doc.current_version
        assert f.v2.version_number==2 and f.v2.sha256==ASSETS['b09-v2.pdf']['sha256'] and not f.v2.is_available
        assert hashlib.sha256(f.first.file.read()).hexdigest()==ASSETS['b09-v1.pdf']['sha256'];f.first.file.close()
        for a in (denied,foreign,sibling):run.denied(a,path,'POST')
        return {'v1':str(f.first.pk),'v2':str(f.v2.pk),'hashes':[f.first.sha256,f.v2.sha256],'v1_unchanged':True}
    run.case('INV-DOCUMENTS-VERSION-ADD',version)
    def exact():
        path=reverse('documents:version-download',args=[f.doc.pk,f.first.pk]);run.get(p,reverse('documents:detail',args=[f.doc.pk]))
        before=AuditEvent.objects.count()
        with p.expect_download() as download:p.locator(f"a[href='{path}']").first.click()
        artifact=download.value;data=Path(artifact.path()).read_bytes();assert hashlib.sha256(data).hexdigest()==f.first.sha256
        assert AuditEvent.objects.count()==before+1
        for a in (denied,foreign,sibling,run.actor(f.nodownload,f.organization)):run.denied(a,path)
        run.denied(p,reverse('documents:version-download',args=[f.doc.pk,f.foreign.current_version_id]),case='Mixed version/document')
        return {'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'version':1,'download_audit_delta':1}
    run.case('INV-DOCUMENTS-VERSION-DOWNLOAD',exact)
    def current():
        path=reverse('documents:download',args=[f.doc.pk]);run.denied(p,path,case='Unassessed current version')
        assess(f,f.doc.current_version)
        r=run.request(p,path);assert r.headers['content-type']=='application/pdf'
        assert r.headers.get('x-content-type-options')=='nosniff' and 'attachment' in r.headers.get('content-disposition','')
        assert hashlib.sha256(r.body()).hexdigest()==ASSETS['b09-v2.pdf']['sha256']
        for a in (denied,foreign,sibling,run.actor(f.nodownload,f.organization)):run.denied(a,path)
        return {'current':str(f.doc.current_version_id),'sha256':hashlib.sha256(r.body()).hexdigest(),'actual_scanner_evidence':'../assets-and-scan.json'}
    run.case('INV-DOCUMENTS-DOWNLOAD',current)
    def links():
        target=f.generic['estimate'];path=reverse('documents:link-add',args=[f.doc.pk]);run.get(l,reverse('documents:detail',args=[f.doc.pk]))
        form=f"main form[action='{path}']";run.select(l,'estimate',target.pk);run.submit(l,path,form)
        assert DocumentLink.objects.filter(document=f.doc,estimate=target).count()==1
        count=DocumentLink.objects.count();run.request(l,path,{'estimate':str(target.pk)},'POST',(302,400),case='Legacy add replay');assert DocumentLink.objects.count()==count
        for a in (reader,foreign,sibling):run.denied(a,path,'POST',{'estimate':str(target.pk)})
        return {'exact_estimate':str(target.pk),'replay_single_link':True}
    run.case('INV-DOCUMENTS-LINK-ADD',links)
    def photo():
        from apps.documents.photo_services import create_photo
        data=(ROOT/'assets'/'b09-photo.png').read_bytes()
        photo=create_photo(organization=f.organization,actor=f.owner,project=f.project,target=f.project,source='upload',title='تصویر آزمون بنیرا',upload=SimpleUploadedFile('b09-photo.png',data,content_type='image/png'))
        path=reverse('documents:photo-preview',args=[photo.pk]);run.denied(p,path,case='Pending photo denied');assess(f,photo.current_version)
        r=run.request(p,path);assert r.headers['content-type']=='image/png';assert r.body()==data
        assert r.headers['cache-control']=='private, no-store'
        assert r.headers.get('x-content-type-options')=='nosniff'
        for a in (foreign,sibling,run.actor(f.nodownload,f.organization)):run.denied(a,path)
        return {'photo':str(photo.pk),'sha256':hashlib.sha256(r.body()).hexdigest(),'size':len(data)}
    run.case('INV-DOCUMENTS-PHOTO-PREVIEW',photo)
    for route in ('employee-list','employee-detail','employee-version-download'):
        def employee(route=route):
            args=[] if route=='employee-list' else [f.doc.pk]+([f.first.pk] if route=='employee-version-download' else [])
            path=reverse('documents:'+route,args=args)
            for a in (p,reader,foreign):
                run.denied(a,path,expected=(403,404),case='MVP ESS exclusion')
                run.denied(a,path,'POST',expected=(403,404),case='MVP ESS exclusion POST')
            self_exposed=route_exposed('documents:'+route)
            run.current['runtime_exposed']=self_exposed
            assert not self_exposed,'Employee document route inherits shared MVP exposure despite approved ESS exclusion'
            return {'scope':'Conditional security control only; approved ESS exclusion retained','exposed':False}
        run.case('INV-DOCUMENTS-'+route.upper(),employee)
    def archive():
        d=f._create_document(reference='B09-ARCHIVE',title='سند بایگانی آزمایشی');assess(f,d.current_version)
        path=reverse('documents:archive',args=[d.pk]);run.get(p,reverse('documents:detail',args=[d.pk]));form=f"main form[action='{path}']"
        p.locator(form+' [name=reason]').fill('نگهداری سابقه آزمون');run.submit(p,path,form)
        d.refresh_from_db();assert d.archived_at and d.versions.count()==1 and d.links.count()==1
        run.denied(p,reverse('documents:download',args=[d.pk]),case='Archived bytes denied')
        for a in (reader,foreign):run.denied(a,path,'POST',{'reason':'forged'})
        return {'document':str(d.pk),'history_preserved':True,'archive_actor':str(d.archived_by_id)}
    run.case('INV-DOCUMENTS-ARCHIVE',archive)

def specialized(run,f):
    from apps.contracts.models import ContractualRecord
    p=run.actor(f.owner,f.organization);reviewer=run.actor(f.reviewer,f.organization)
    foreign=run.actor(f.other_user,f.other_organization);denied=run.actor(f.denied,f.organization);sibling=run.actor(f.sibling,f.organization)
    # Select version one while version two is current, except Material's governed current-only rule.
    for kind,target in f.special.items():
        def choice(kind=kind,target=target):
            path=reverse('documents:evidence-choices',args=[kind,target.pk]);r=run.get(p,path)
            values={x['value'] for x in r.json()['results']}
            expected=f.doc.current_version_id if kind=='material' else f.first.pk
            assert str(expected) in values
            assert str(f.foreign.current_version_id) not in values
            for a in (foreign,denied):run.denied(a,path)
            if kind!='material':run.denied(sibling,path,case='Sibling source')
            run.denied(p,path+'?next=//invalid.example/',case='Unsafe source return')
            return {'source':str(target.pk),'kind':kind,'eligible_versions':sorted(values),'selected_expected':str(expected)}
        run.case('INV-DOCUMENTS-EVIDENCE-CHOICES-EVIDENCE-'+kind.upper().replace('_','-'),choice,'CV-DOC-02')
        if kind in {'guarantee','compliance','release'}:
            def commercial(kind=kind):
                path=reverse('documents:commercial-evidence-choices',args=[kind]);r=run.get(p,path)
                values={x['value'] for x in r.json()['results']};assert str(f.first.pk) in values
                assert str(f.foreign.current_version_id) not in values
                for a in (foreign,denied):
                    before=witness();response=run.request(a,path,expected=(200,403),case='Commercial selector tenant/permission')
                    if response.status==200:assert str(f.first.pk) not in response.text()
                    assert witness()==before
                return {'kind':kind,'authorized_versions':sorted(values),'foreign_absent':True}
            run.case('INV-DOCUMENTS-COMMERCIAL-EVIDENCE-CHOICES-EVIDENCE-'+kind.upper(),commercial,'CV-DOC-02')
    for family in ('EVIDENCE-CHOICES','COMMERCIAL-EVIDENCE-CHOICES'):
        def aggregate(family=family):
            children=[k for k in run.results if k.startswith('INV-DOCUMENTS-'+family+'-EVIDENCE-')]
            assert len(children)==(8 if family=='EVIDENCE-CHOICES' else 3)
            assert all(run.results[k]['status']=='PASS' for k in children)
            return {'parameterized_evidence':children}
        run.case('INV-DOCUMENTS-'+family,aggregate,'CV-DOC-02')
    for kind,target in f.special.items():
        if kind in {'guarantee','compliance','release'}:continue
        def register(kind=kind,target=target):
            path=reverse('documents:evidence-register',args=[kind,target.pk]);run.get(p,path)
            run.observe(p,'evidence-register-'+kind,shots=kind=='contractual')
            hidden=run.hidden(p);key='versions' if kind in {'safety','quality'} else 'version'
            selected=f.doc.current_version if kind=='material' else f.first
            before=witness();run.request(p,path,{**hidden,key:str(selected.pk),'context_token':'forged'},'POST',400,case='Forged signed source intent');assert witness()==before
            # Domain selectors retain exact IDs, labels and independently enforced scope.
            run.select(p,key,selected.pk)
            if kind=='contractual':p.locator('[name=label]').fill('شاهد تاریخی نسخه یک')
            if kind in {'safety','quality'}:p.locator('[name=reason]').fill('ارسال شواهد برای بررسی مستقل')
            run.submit(p,path)
            source=resolve_evidence_source(user=f.owner,organization=f.organization,kind=kind,identifier=target.pk)
            assert str(selected.pk) in {str(x[0]) for x in references(source)}
            before=witness()
            run.request(p,path,{**hidden,key:str(selected.pk),'label':'شاهد تاریخی نسخه یک','reason':'تکرار'},'POST',(302,400,403),case='Evidence replay')
            assert witness()==before
            for a in (foreign,denied):run.denied(a,path,'POST',{**hidden,key:str(selected.pk)})
            return {'source':str(target.pk),'kind':kind,'version':str(selected.pk),'sha256':selected.sha256,'source_references':references(source)}
        run.case('INV-DOCUMENTS-EVIDENCE-REGISTER-EVIDENCE-'+kind.upper().replace('_','-'),register,'CV-DOC-02')
    def aggregate_registration():
        children=[k for k in run.results if k.startswith('INV-DOCUMENTS-EVIDENCE-REGISTER-EVIDENCE-')]
        assert len(children)==5 and all(run.results[k]['status']=='PASS' for k in children)
        for kind in ('guarantee','compliance','release'):
            path=reverse('documents:evidence-register',args=[kind,f.special[kind].pk]);run.denied(p,path,case='No generic commercial registration')
        return {'supported_registration_evidence':children,'commercial_registration':'Domain-owned create/revision forms only'}
    run.case('INV-DOCUMENTS-EVIDENCE-REGISTER',aggregate_registration,'CV-DOC-02')
    def submit_observation():
        observation=f.special['field_observation']
        source=evidence_panel(user=f.owner,organization=f.organization,kind='field_observation',identifier=observation.pk).source.url
        run.get(p,source);path=reverse('daily_reports:field_observation_submit',args=[observation.pk])
        run.submit(p,path,f"main form[action='{path}']")
        observation.refresh_from_db();assert observation.status=='submitted'
        run.denied(p,reverse('documents:evidence-register',args=['field_observation',observation.pk]),case='Submitted observation immutable evidence')
        return {'status':observation.status,'canonical_hash':observation.canonical_hash,'evidence':list(observation.evidence_links.values())}
    run.extra('observation-submission-pinned-history',submit_observation)
    # A new pending version must never change an existing persisted witness.
    before_pins={k:references(resolve_evidence_source(user=f.owner,organization=f.organization,kind=k,identifier=t.pk)) for k,t in f.special.items()}
    f.v3=add_document_version(document=f.doc,actor=f.owner,upload=upload(2))
    assess(f,f.v3,'unsafe')
    for kind,target in f.special.items():
        def detail(kind=kind,target=target):
            panel=evidence_panel(user=f.owner,organization=f.organization,kind=kind,identifier=target.pk)
            assert panel.rows,'No persisted exact evidence'
            row=panel.rows[0];run.get(p,panel.source.url);assert p.locator(f"a[href='{row.view_url}']").count()
            run.observe(p,'specialized-source-'+kind)
            p.locator(f"a[href='{row.view_url}']").first.click();p.wait_for_load_state('domcontentloaded')
            assert 'نسخه شاهد' in p.locator('main').inner_text()
            run.observe(p,'evidence-detail-'+kind,shots=kind in {'guarantee','safety'})
            assert references(resolve_evidence_source(user=f.owner,organization=f.organization,kind=kind,identifier=target.pk))==before_pins[kind]
            if row.download_url:
                r=run.request(p,row.download_url);version=DocumentVersion.objects.get(pk=row.version_id)
                assert hashlib.sha256(r.body()).hexdigest()==version.sha256
                run.denied(run.actor(f.nodownload,f.organization),row.download_url,case='Evidence independent download permission')
            for a in (foreign,denied):run.denied(a,row.view_url)
            if kind!='material':run.denied(sibling,row.view_url,case='Sibling source detail')
            run.denied(p,reverse('documents:evidence-detail',args=[kind,target.pk,f.foreign.current_version_id]),case='Unlinked foreign witness')
            run.denied(p,reverse('documents:evidence-detail',args=[kind,target.pk,f.v3.pk]),case='Unregistered current quarantined version')
            return {'source':str(target.pk),'persisted_pins':before_pins[kind],'witness_version':str(row.version_id),'witness_number':row.version,'current_number':row.current_version,'immutable_after_new_version':True}
        run.case('INV-DOCUMENTS-EVIDENCE-DETAIL-EVIDENCE-'+kind.upper().replace('_','-'),detail,'CV-DOC-02')
    def aggregate_detail():
        children=[k for k in run.results if k.startswith('INV-DOCUMENTS-EVIDENCE-DETAIL-EVIDENCE-')]
        assert len(children)==8 and all(run.results[k]['status']=='PASS' for k in children)
        return {'eight_source_evidence':children,'pin_comparison':before_pins}
    run.case('INV-DOCUMENTS-EVIDENCE-DETAIL',aggregate_detail,'CV-DOC-02')

def contractual(run,f):
    from apps.contracts.models import ContractualRecord
    p=run.actor(f.owner,f.organization);reviewer=run.actor(f.reviewer,f.organization)
    foreign=run.actor(f.other_user,f.other_organization);denied=run.actor(f.denied,f.organization)
    def listing():
        path=reverse('contracts:contractual_list');run.get(p,path);assert f.record.title in p.locator('main').inner_text();run.observe(p,'contractual-list')
        run.denied(denied,path);run.get(foreign,path);assert f.record.title not in foreign.locator('main').inner_text()
        return {'record':str(f.record.pk),'tenant_filtered':True}
    run.case('INV-CONTRACTS-CONTRACTUAL-LIST',listing,'CV-DOC-02')
    def create():
        path=reverse('contracts:contractual_create');run.get(p,path);run.observe(p,'contractual-create',True)
        run.select(p,'contract',f.contract.pk);run.select(p,'kind','claim')
        for name,value in {'record_number':'B09-NEW-CR','title':'ادعای قراردادی آزمون','description':'بدون اثر مالی خودکار','requested_amount':'125.5','requested_eot_days':'2'}.items():p.locator(f'[name={name}]').fill(value)
        run.submit(p,path);f.new_record=ContractualRecord.objects.get(record_number='B09-NEW-CR');assert f.new_record.status=='draft'
        run.denied(denied,path,'POST');run.denied(foreign,reverse('contracts:contractual_detail',args=[f.new_record.pk]))
        limited=run.actor(f.sibling,f.organization);run.get(limited,path)
        assert str(f.contract.pk) not in limited.locator('[name=contract]').inner_html(),'Sibling-project contract metadata appears in the contractual source selector'
        return {'record':str(f.new_record.pk),'contract':str(f.new_record.contract_id),'status':f.new_record.status}
    run.case('INV-CONTRACTS-CONTRACTUAL-CREATE',create,'CV-DOC-02')
    def detail():
        path=reverse('contracts:contractual_detail',args=[f.record.pk]);run.get(p,path);run.observe(p,'contractual-detail',True)
        assert p.locator('#document-evidence').count()==1
        assert f.record.evidence_links.filter(document_version=f.first).count()==1
        for a in (foreign,denied):run.denied(a,path)
        return {'exact_evidence':str(f.first.pk),'source':str(f.record.pk)}
    run.case('INV-CONTRACTS-CONTRACTUAL-DETAIL',detail,'CV-DOC-02')
    def submit():
        path=reverse('contracts:contractual_submit',args=[f.record.pk]);run.get(p,reverse('contracts:contractual_detail',args=[f.record.pk]))
        form=f"main form[action='{path}']";run.submit(p,path,form)
        f.record.refresh_from_db();assert f.record.status=='submitted'
        before=witness();run.request(p,path,{},'POST',302,case='Submission replay');assert witness()==before
        for a in (foreign,denied):run.denied(a,path,'POST')
        return {'status':f.record.status,'evidence':list(f.record.evidence_links.values_list('document_version_id',flat=True))}
    run.case('INV-CONTRACTS-CONTRACTUAL-SUBMIT',submit,'CV-DOC-02')
    def decide():
        path=reverse('contracts:contractual_decide',args=[f.record.pk]);source=reverse('contracts:contractual_detail',args=[f.record.pk])
        run.get(reviewer,source)
        data={'outcome':'approved','reason':'بررسی مستقل شاهد نسخه یک','entitlement_approved':'true','approved_amount':'100','approved_eot_days':'1','delay_responsibility':'شاهد آزمایشی'}
        run.denied(p,path,'POST',data,case='Maker checker self-decision')
        before=witness();run.request(reviewer,path,{**data,'reason':''},'POST',302,case='Mandatory reason');assert witness()==before
        form=f"main form[action='{path}']"
        for name,value in data.items():
            el=reviewer.locator(form+f" [name='{name}']")
            if el.evaluate('e=>e.tagName')=='SELECT':el.select_option(value)
            else:el.fill(value)
        run.submit(reviewer,path,form)
        f.record.refresh_from_db();assert f.record.status=='approved' and f.record.approved_amount==100
        assert f.record.evidence_links.get().document_version_id==f.first.pk
        snapshot=f.record.submission_snapshot.copy()
        newer=add_document_version(document=f.doc,actor=f.owner,upload=upload(2));assess(f,newer,'unsafe')
        f.record.refresh_from_db()
        assert f.record.submission_snapshot==snapshot and f.record.evidence_links.get().document_version_id==f.first.pk
        run.get(reviewer,source)
        run.denied(p,reverse('documents:evidence-register',args=['contractual',f.record.pk]),case='Approved contractual evidence registration denied')
        before=witness();run.request(reviewer,path,data,'POST',(302,403),case='Decision replay');assert witness()==before
        for a in (foreign,denied):run.denied(a,path,'POST',data)
        return {'status':f.record.status,'approved_amount':f.record.approved_amount,'exact_evidence':str(f.first.pk),'independent_actor':str(f.reviewer.pk)}
    run.case('INV-CONTRACTS-CONTRACTUAL-DECIDE',decide,'CV-DOC-02')
    def revision():
        path=reverse('contracts:contractual_revision',args=[f.record.pk]);run.get(p,reverse('contracts:contractual_detail',args=[f.record.pk]))
        form=f"main form[action='{path}']";p.locator(form+' [name=reason]').fill('اصلاح مرتبط بدون بازنویسی سابقه')
        run.submit(p,path,form)
        f.revised=ContractualRecord.objects.get(supersedes=f.record);assert f.revised.status=='draft' and f.revised.version==2
        assert f.record.evidence_links.get().document_version_id==f.first.pk
        for a in (foreign,denied):run.denied(a,path,'POST',{'revision_action':'correction','reason':'forged'})
        return {'predecessor':str(f.record.pk),'successor':str(f.revised.pk),'version':f.revised.version,'original_evidence_preserved':True}
    run.case('INV-CONTRACTS-CONTRACTUAL-REVISION',revision,'CV-DOC-02')
    def withdraw():
        target=f.new_record;path=reverse('contracts:contractual_withdraw',args=[target.pk]);run.get(p,reverse('contracts:contractual_detail',args=[target.pk]))
        form=f"main form[action='{path}']";p.locator(form+' [name=reason]').fill('استرداد ادعای آزمایشی')
        run.submit(p,path,form);target.refresh_from_db();assert target.status=='withdrawn'
        before=witness();run.request(p,path,{'reason':'استرداد ادعای آزمایشی'},'POST',(302,403),case='Withdrawal replay');assert witness()==before
        for a in (foreign,denied):run.denied(a,path,'POST',{'reason':'forged'})
        return {'record':str(target.pk),'status':target.status,'reason':target.withdrawal_reason}
    run.case('INV-CONTRACTS-CONTRACTUAL-WITHDRAW',withdraw,'CV-DOC-02')

def supplemental(run,f):
    p=run.actor(f.owner,f.organization)
    def quarantine():
        path=reverse('documents:download',args=[f.doc.pk]);run.denied(p,path,case='Latest quarantined version denied')
        run.get(p,reverse('documents:detail',args=[f.doc.pk]));assert 'قرنطینه' in p.locator('main').inner_text()
        run.observe(p,'quarantined-document',True)
        exact=reverse('documents:version-download',args=[f.doc.pk,f.first.pk]);r=run.request(p,exact);assert hashlib.sha256(r.body()).hexdigest()==f.first.sha256
        for field,value in [('file','replacement.pdf'),('sha256','0'*64),('file_size',1)]:
            v=DocumentVersion.objects.get(pk=f.first.pk);setattr(v,field,value)
            try:v.save()
            except ValidationError:pass
            else:raise AssertionError('Immutable version changed')
        assert hashlib.sha256(DocumentVersion.objects.get(pk=f.first.pk).file.read()).hexdigest()==f.first.sha256
        return {'v1_still_deliverable':True,'v3_quarantined_denied':True,'metadata_replacement_denied':True}
    run.extra('quarantine-immutability',quarantine)
    def stale():
        target=f.special['material'];path=reverse('documents:evidence-register',args=['material',target.pk]);run.get(p,path);hidden=run.hidden(p)
        before=witness();run.request(p,path,{**hidden,'version':str(f.first.pk)},'POST',400,case='Stale non-current Material witness');assert witness()==before
        return {'stale_v1_rejected':True,'historical_v2_preserved':target.document_links.filter(document_version=f.v2).exists()}
    run.extra('material-stale-selection',stale)
    def expiration():
        d=f._create_document(reference='B09-EXPIRY',title='سند منقضی آزمایشی',access_expires_at=timezone.now()+timedelta(hours=1));assess(f,d.current_version)
        # Deliberate fixture clock boundary, not a production metadata edit.
        Document.objects.filter(pk=d.pk).update(access_expires_at=timezone.now()-timedelta(seconds=1))
        run.denied(p,reverse('documents:download',args=[d.pk]),case='Expired bytes denied')
        return {'expired_document':str(d.pk),'bytes_denied':True}
    run.extra('expiry-delivery',expiration)
    def uploads():
        path=reverse('documents:contextual-upload',args=['project',f.project.pk]);run.get(p,path);hidden=run.hidden(p)
        before=witness();run.request(p,path,{**hidden,'title':'invalid','document_type':'general','confidentiality':'internal'},'POST',400,case='Disallowed signature',files={'file':ROOT/'assets'/'invalid.exe'});assert witness()==before
        run.denied(p,path,'POST',{},case='Missing CSRF',expected=403) if False else None
        before=witness();run.request(p,path,hidden,'POST',403,csrf=False,case='Missing CSRF');assert witness()==before
        run.denied(p,'/documents/context/project/../../private/',expected=404,case='Path traversal')
        run.denied(p,reverse('documents:detail',args=[uuid4()]),case='Forged document UUID')
        run.denied(p,'/documents/'+str(f.doc.pk)+'/versions/not-a-uuid/download/',expected=404,case='Malformed exact version identifier')
        run.denied(run.actor(),'/media/'+f.first.file.name,expected=404,case='Anonymous direct media path')
        try:f.first.file.storage.url(f.first.file.name)
        except ValueError:pass
        else:raise AssertionError('Private storage published URL')
        run.get(p,path)
        p.locator('[name=title]').fill('مقادیر فرم پس از خطا')
        p.locator('[name=reference]').fill('B09-INVALID-RETAINED')
        p.locator('[name=file]').set_input_files(str(ROOT/'assets'/'invalid.exe'))
        run.submit(p,path,expected=400)
        assert p.locator('[name=title]').input_value()=='مقادیر فرم پس از خطا'
        assert p.locator('[name=reference]').input_value()=='B09-INVALID-RETAINED'
        assert p.locator('.errorlist,[role=alert]').count()
        run.observe(p,'invalid-upload-retained-values',True)
        return {'invalid_upload_no_storage_write':True,'csrf_required':True,'path_traversal_denied':True,'raw_storage_url_disabled':True}
    run.extra('invalid-files-csrf-private-storage',uploads)
    def expired_intent():
        from django.core import signing
        from unittest.mock import patch
        path=reverse('documents:contextual-link',args=['project',f.project.pk]);run.get(p,path)
        hidden=run.hidden(p)
        intent=signing.loads(hidden['context_token'],salt='documents.contextual-association.v1')
        with patch('django.core.signing.time.time',return_value=time.time()-7200):
            old=signing.dumps(intent,salt='documents.contextual-association.v1')
        before=witness()
        r=run.request(p,path,{**hidden,'document':str(f.foreign.pk),'context_token':old},'POST',400,case='Correctly signed but expired intent')
        assert witness()==before
        assert 'FOREIGN B09 PRIVATE' not in r.text()
        return {'expired_signed_token_rejected':True,'no_delta':True}
    run.extra('expired-signed-intent',expired_intent)
    def concurrent_versions():
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        d=f._create_document(reference='B09-CONCURRENT',title='نسخه‌های همزمان')
        barrier=Barrier(2)
        def worker(n):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                v=add_document_version(document=Document.objects.get(pk=d.pk),actor=User.objects.get(pk=f.owner.pk),upload=upload(n))
                return {'id':str(v.pk),'number':v.version_number,'sha256':v.sha256}
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,(1,2)))
        assert sorted(x['number'] for x in results)==[2,3]
        d.refresh_from_db();assert d.current_version.version_number==3 and d.versions.count()==3
        assert {x['sha256'] for x in results}=={ASSETS['b09-v1.pdf']['sha256'],ASSETS['b09-v2.pdf']['sha256']}
        assert d.versions.get(version_number=1).sha256==ASSETS['b09-v1.pdf']['sha256']
        return {'separate_database_connections':True,'workers':results,'current_version':str(d.current_version_id),'v1_preserved':True}
    run.extra('concurrent-version-allocation',concurrent_versions)
    def no_download_controls():
        page=run.actor(f.nodownload,f.organization)
        path=reverse('documents:detail',args=[f.doc.pk]);run.get(page,path)
        assert page.locator("main a[href*='/download/']").count()==0
        run.denied(run.actor(),reverse('documents:version-download',args=[f.doc.pk,f.first.pk]),expected=302,case='Anonymous exact download requires login')
        return {'authorized_metadata_visible':True,'download_controls_absent':True,'anonymous_bytes_denied':True}
    run.extra('independent-download-ui',no_download_controls)
    def contractual_concurrency():
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from apps.contracts.contractual_services import create_contractual_record,add_contractual_evidence,submit_contractual_record,decide_contractual_record
        from apps.contracts.models import ContractualRecord
        from apps.organizations.models import Organization
        record=create_contractual_record(organization=f.organization,actor=f.owner,contract=f.contract,kind='claim',record_number='B09-RACE',title='بررسی همزمان شاهد',description='شاهد تغییرناپذیر',idempotency_key='b09-decision-race')
        barrier=Barrier(2)
        def attach(n):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                return str(add_contractual_evidence(organization=Organization.objects.get(pk=f.organization.pk),actor=User.objects.get(pk=f.owner.pk),record=ContractualRecord.objects.get(pk=record.pk),label='شاهد یکسان همزمان',document_version=DocumentVersion.objects.get(pk=f.first.pk)).pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:links=list(pool.map(attach,(1,2)))
        assert len(set(links))==1 and record.evidence_links.count()==1,'Concurrent contractual evidence retry duplicated the link'
        submit_contractual_record(organization=f.organization,actor=f.owner,record=record)
        barrier=Barrier(2)
        before=AuditEvent.objects.filter(entity_id=record.pk,action='contractual_record.approved').count()
        def decide(user_id):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                try:
                    value=decide_contractual_record(organization=Organization.objects.get(pk=f.organization.pk),actor=User.objects.get(pk=user_id),record=ContractualRecord.objects.get(pk=record.pk),approved=True,reason='بررسی مستقل همزمان',entitlement_approved=True,approved_amount='25',approved_eot_days=0)
                    return {'status':value.status,'actor':str(user_id)}
                except Exception as exc:
                    from django.core.exceptions import PermissionDenied
                    assert isinstance(exc,(ValidationError,PermissionDenied)),repr(exc)
                    return {'rejected':type(exc).__name__,'actor':str(user_id)}
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:decisions=list(pool.map(decide,(f.reviewer.pk,f.nodownload.pk)))
        assert sum(x.get('status')=='approved' for x in decisions)==1 and sum('rejected' in x for x in decisions)==1
        record.refresh_from_db();assert record.status=='approved' and record.evidence_links.get().document_version_id==f.first.pk
        audits=list(AuditEvent.objects.filter(entity_id=record.pk).values('action','actor_id'))
        assert len([x for x in audits if 'approved' in x['action']])==1
        return {'record':str(record.pk),'concurrent_evidence_ids':links,'decisions':decisions,'exact_version':str(f.first.pk),'source_audit':audits,'separate_connections':True}
    run.extra('contractual-evidence-and-decision-concurrency',contractual_concurrency)
    def quarantine_matrix():
        selected={}
        for kind,target in f.special.items():
            panel=evidence_panel(user=f.owner,organization=f.organization,kind=kind,identifier=target.pk)
            for row in panel.rows:selected[str(row.version_id)]=DocumentVersion.objects.get(pk=row.version_id)
        for version in selected.values():assess(f,version,'unsafe')
        facts={}
        for kind,target in f.special.items():
            panel=evidence_panel(user=f.owner,organization=f.organization,kind=kind,identifier=target.pk)
            assert panel.rows
            row=panel.rows[0];assert not row.available and not row.download_url
            run.get(p,row.view_url);assert 'قرنطینه' in p.locator('main').inner_text() or 'ارزیابی' in p.locator('main').inner_text()
            version=DocumentVersion.objects.get(pk=row.version_id)
            run.denied(p,reverse('documents:version-download',args=[version.document_id,version.pk]),case=kind+' unsafe exact witness denied')
            facts[kind]={'metadata_authorized':True,'version':str(row.version_id),'download_denied':True,'source_pin_preserved':True}
        return {'policy_fixture':'Append-only unsafe assessment injected to exercise quarantine policy on benign synthetic files; no malware or deployed scanner detection claim','variants':facts,'restored_to_clean':False}
    run.extra('all-eight-quarantine-policies',quarantine_matrix)

def main():
    (OUT/'harness-source.py').write_bytes(Path(__file__).read_bytes())
    surface=[{'execution_id':r['Execution_ID'],'route':r['Route_Name'],'exposed':route_exposed(r['Route_Name']),'capability':route_capability(r['Route_Name'])} for r in MATRIX]
    save('surface.json',surface)
    f=seed()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    (ROOT/f'{PHASE}-origin.txt').write_text(origin)
    with (ROOT/f'{PHASE}-server.log').open('w',encoding='utf-8') as log:
        server=subprocess.Popen([sys.executable,'manage.py','runserver',f'127.0.0.1:{port}','--insecure','--noreload'],cwd=REPO,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(150):
                try:urlopen(origin+'/accounts/login/',timeout=1);break
                except OSError:
                    if server.poll() is not None:raise RuntimeError('Isolated server exited')
                    time.sleep(.2)
            with sync_playwright() as pw:
                with pw.chromium.launch(channel='chrome',headless=True) as browser:
                    save('environment.json',{'chrome':browser.version,'postgresql':PG_VERSION,'database':DB,'isolated_cluster':DIRECTORY,'private_storage':str(settings.DOCUMENT_PROTECTED_ROOT),'profile':'MVP','actor_model':'Separate authenticated Chrome contexts with explicit test memberships; non-superuser business actors','scan':'Actual local Defender scan, recorded through governed Platform Operations service for hash-identical synthetic bytes. Deployed scanner/external storage unverified'})
                    run=Runner(browser,origin,f)
                    for fn in (generic,specialized,contractual,supplemental):
                        save(fn.__name__+'-before-state.json',witness())
                        try:fn(run,f)
                        except Exception:
                            with (ROOT/f'{PHASE}-private-errors.log').open('a',encoding='utf-8') as stream:stream.write(fn.__name__+' GROUP\n'+traceback.format_exc()+'\n')
                            print(fn.__name__,'GROUP FAILED',flush=True)
                    missing={r['Execution_ID'] for r in MATRIX}-run.results.keys()
                    for key in missing:run.results[key]={'execution_id':key,'status':'BLOCKED','error':'A required fixture/earlier group did not complete; see private harness trace'}
                    run.flush();save('final-state.json',witness())
                    save('document-versions.json',list(DocumentVersion.objects.values('id','organization_id','document_id','version_number','original_file_name','content_type','file_size','sha256')))
                    save('source-pins.json',{k:references(resolve_evidence_source(user=f.owner,organization=f.organization,kind=k,identifier=t.pk)) for k,t in f.special.items()})
                    print('COUNTS',json.dumps({s:sum(x['status']==s for x in run.results.values()) for s in ('PASS','FAIL','BLOCKED')}),flush=True)
        finally:server.terminate();server.wait(timeout=20)

if __name__=='__main__':main()
