import os
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']='1'
import json, re, traceback
from decimal import Decimal
from uuid import uuid4
from urllib.parse import urlsplit
from common import root, guard
from django.apps import apps
from django.conf import settings
from django.urls import reverse
from core.jalali import gregorian_to_jalali
from playwright.sync_api import sync_playwright
from apps.daily_reports.submission_snapshots import verify_submission as _verify_submission

guard(readonly=True)
cfg=json.loads((root/'actors.json').read_text(encoding='utf-8'))
ids=cfg['ids']; base='http://127.0.0.1:'+(root/'web-port.txt').read_text()
out=root/'chrome';out.mkdir(exist_ok=True)
checks=[];pages=[];traffic=[]
def verify_submission(report):
    _verify_submission(report)
    return True
def save():
    (out/'results.json').write_text(json.dumps({'checks':checks,'pages':pages,'traffic':traffic},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def check(label, ok, **data):
    checks.append({'check':label,'pass':bool(ok),**data});save()
    print(label, bool(ok),data,flush=True)
    assert ok,label
def obj(app,name,**kwargs):return apps.get_model(app,name).objects.get(**kwargs)
def visit(p,url):
    response=p.goto(base+url,wait_until='load');assert response.status==200,(url,response.status)
def fill(f,**values):
    for name,value in values.items():
        el=f.locator(f'[name="{name}"]');value=str(value)
        if el.evaluate('e=>e.tagName')=='SELECT':
            if el.is_visible():el.select_option(value)
            else:el.evaluate('(e,v)=>{if(e.tomselect)e.tomselect.setValue(v);else{e.value=v;e.dispatchEvent(new Event("change",{bubbles:true}));}}',value)
        else:
            if el.get_attribute('data-jalali-mode') and value.startswith('2026-'):
                y,m,d=gregorian_to_jalali(*map(int,value[:10].split('-')))
                value=f'{y:04}/{m:02}/{d:02}'+(' '+value[11:] if len(value)>10 else '')
            el.fill(value)
            if el.get_attribute('data-jalali-mode'):el.press('Escape')
def click(f):
    f.locator('button[type=submit]').first.click()
    f.page.wait_for_timeout(150)
    confirm=f.page.locator('.swal2-confirm:visible')
    if confirm.count():confirm.click()
    f.page.wait_for_load_state('load')
def post(p,url,data):
    csrf=next(c['value'] for c in p.context.cookies() if c['name']==settings.CSRF_COOKIE_NAME)
    return p.request.post(base+url,form={k:str(v) for k,v in data.items()},headers={'X-CSRFToken':csrf},max_redirects=0).status
def capture(p,label):
    for width,height in [(1440,900),(390,844)]:
        p.set_viewport_size({'width':width,'height':height});p.wait_for_timeout(100)
        page=p.evaluate('''()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,dir:document.documentElement.dir,main:document.querySelectorAll('main').length,headings:[...document.querySelectorAll('main h1,main h2')].map(e=>e.innerText)})''')
        pages.append({'label':label,'path':urlsplit(p.url).path,**page})
        p.screenshot(path=out/f'{label}-{width}.png',full_page=True)
        check(label+f'-layout-{width}',page['scroll']<=width and page['main']==1 and page['dir']=='rtl')
    p.set_viewport_size({'width':1440,'height':900})
def login(browser,key):
    context=browser.new_context(viewport={'width':1440,'height':900})
    context.route(re.compile(r'^https?://(?!'+re.escape(urlsplit(base).netloc)+r'(?:/|$))'),lambda route:route.abort())
    p=context.new_page();p.set_default_timeout(45000)
    p.on('response',lambda r:traffic.append([key,r.request.method,urlsplit(r.url).path,r.status]) if r.request.resource_type in {'document','xhr','fetch'} else None)
    visit(p,reverse('accounts:login')+'?next=/daily-reports/')
    f=p.locator('form').first;fill(f,username=cfg['actors'][key],password=cfg['password']);click(f)
    assert not p.locator('[name=password]').count(),key
    return p

def equipment_usage(owner):
    visit(owner, reverse('equipment:usage_create'))
    form = owner.locator('main form[method=post]').first
    fill(form, equipment=ids['equipment'], deployment=ids['deployment'],
         operator=ids['employee'], started_at='2026-11-01T08:00',
         ended_at='2026-11-01T10:00', runtime_hours='20',
         evidence_reference='GATE-CHROME-USAGE')
    click(form)
    check('equipment-invalid-runtime-rejected',
          not apps.get_model('equipment','EquipmentUsageLog').objects.filter(evidence_reference='GATE-CHROME-USAGE').exists()
          and 'حداکثر برابر مدت' in owner.locator('main').inner_text())
    form = owner.locator('main form[method=post]').first
    fill(form, runtime_hours='2')
    capture(owner, 'equipment-usage')
    click(form)
    usage = obj('equipment', 'EquipmentUsageLog', evidence_reference='GATE-CHROME-USAGE')
    check('equipment-qualified-usage-created',
          str(usage.deployment_id)==ids['deployment'] and str(usage.operator_id)==ids['employee']
          and usage.runtime_hours==Decimal('2') and usage.started_at.hour==4 and usage.started_at.minute==30,
          usage=usage.pk, deployment=usage.deployment_id, utc_start=usage.started_at, utc_end=usage.ended_at)

if os.getenv('GATE_CHROME_ONLY') == 'equipment':
    out = root/'chrome-equipment'
    out.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        (out/'browser-version.txt').write_text(browser.version)
        try:
            equipment_usage(login(browser, 'owner'))
            check('no-http-500', all(row[3]<500 for row in traffic))
        finally:
            save()
            browser.close()
    raise SystemExit(0)

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(channel='chrome',headless=True)
    (out/'browser-version.txt').write_text(browser.version)
    try:
        author=login(browser,'author');reviewer=login(browser,'reviewer')
        first=obj('daily_reports','DailyReport',pk=ids['report'])
        detail=reverse('daily_reports:detail',args=[first.pk]);returned=reverse('daily_reports:return',args=[first.pk])
        visit(author,detail)
        check('daily-author-return-denied',not author.locator(f'form[action="{returned}"]').count() and post(author,returned,{'operation_key':uuid4(),'reason':'درخواست نویسنده'})==403)
        visit(reviewer,detail)
        f=reviewer.locator(f'form[action="{returned}"]')
        key=f.locator('[name=operation_key]').input_value()
        check('daily-return-reason-required',post(reviewer,returned,{'operation_key':key,'reason':''})==400 and obj('daily_reports','DailyReport',pk=first.pk).status=='submitted')
        fill(f,reason='اصلاح شرح و تعداد نیروی انسانی در آزمون یکپارچگی');capture(reviewer,'daily-return');click(f)
        first.refresh_from_db()
        check('daily-return-retains-seal',first.status=='returned' and first.submission_hash==ids['hash'] and verify_submission(first),report=first.pk,submission_hash=first.submission_hash)
        visit(author,detail);click(author.locator(f'form[action="{reverse("daily_reports:correction_start",args=[first.pk])}"]'))
        second=obj('daily_reports','DailyReport',previous_revision=first)
        f=author.locator('form[data-correction-header]');fill(f,work_performed='شرح اصلاحی آزمون یکپارچگی');click(f)
        visit(author,reverse('daily_reports:correction_entry',args=[second.pk,'labor',second.labor_entries.get().pk]))
        f=author.locator('form[data-correction-entry]');fill(f,worker_count=3);click(f)
        capture(author,'daily-correction')
        click(author.locator(f'form[action="{reverse("daily_reports:correction_submit",args=[second.pk])}"]'))
        second.refresh_from_db()
        check('daily-correction-resubmitted',second.status=='submitted' and second.revision_number==2 and second.submission_hash!=first.submission_hash and second.labor_entries.get().worker_count==3 and first.labor_entries.get().worker_count==2 and verify_submission(second),report=second.pk,previous=second.previous_revision_id,submission_hash=second.submission_hash)
        visit(reviewer,reverse('daily_reports:detail',args=[second.pk]));click(reviewer.locator(f'form[action="{reverse("daily_reports:approve",args=[second.pk])}"]'))
        second.refresh_from_db();first.refresh_from_db()
        check('daily-independent-final-approval',second.status=='approved' and second.approved_by_id!=second.created_by_id and first.status=='returned' and verify_submission(first) and verify_submission(second))
        capture(reviewer,'daily-approved-history')
        owner=login(browser,'owner');hse=login(browser,'hse');sibling=login(browser,'sibling')
        for app,name in [('safety','SafetyIncident'),('quality','QualityIssue')]:
            record=obj(app,name,pk=cfg['records'][app]['id']);url=reverse(f'{app}:record_decision',args=[record.pk])
            visit(owner,reverse(f'{app}:detail',args=[record.pk]))
            data={'submission_id':cfg['records'][app]['submission'],'outcome':'approved','reason':'بررسی مستقل آزمون یکپارچگی'}
            check(app+'-creator-denied',post(owner,url,data)==403)
            visit(sibling,reverse(f'{app}:list'))
            check(app+'-sibling-denied',post(sibling,url,data)==403)
            visit(hse,reverse(f'{app}:detail',args=[record.pk]));hse.locator(f'main a[href="{url}"]').click()
            check(app+'-reason-required',post(hse,url,{**data,'reason':''})==400)
            f=hse.locator('main form[method=post]').first;fill(f,outcome='approved',reason=data['reason']);capture(hse,app+'-approval-form');click(f)
            record.refresh_from_db()
            check(app+'-approved-state-and-history',record.review_status=='approved' and record.status==cfg['records'][app]['status'] and record.review_revisions.count()==2,record=record.pk,operational_status=record.status,review_status=record.review_status)
            capture(hse,app+'-approved')
        equipment_usage(owner)
        check('no-http-500',all(row[3]<500 for row in traffic))
    except Exception:
        (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:
        save();browser.close()
print('PASS: targeted Chrome Daily Report Return/correction/resubmit/approval, Safety/Quality independent approval, qualified Equipment Usage.')
