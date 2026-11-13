from browser import *
import re
from urllib.parse import parse_qs,urlsplit
from django.urls import reverse
from apps.projects.models import Project,WBSNode,Activity
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
assert db=='project_ui_retest'
proc,base,log=start();results={};contexts={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True)
  def page_for(actor):
   if actor not in contexts:
    ctx=context(b,base,actor);page=ctx.new_page();page.set_default_timeout(12000);contexts[actor]=(ctx,page)
   return contexts[actor][1]
  owner=page_for('owner');issues=[]
  owner.on('pageerror',lambda err:issues.append(str(err)))
  owner.on('response',lambda res:issues.append(str(res.status)+' '+urlsplit(res.url).path) if res.status>=500 else None)
  def go(page,path,status=200):
   response=page.goto(base+path,wait_until='networkidle');assert response.status==status,(path,response.status);return page
  def check(name,fn):
   try:results[name]={'status':'PASS','detail':fn()}
   except Exception as exc:results[name]={'status':'FAIL','error':type(exc).__name__+': '+repr(exc)[:220]}
   save('chrome-final.json',{'browser':b.version,'database':db,'cases':results,'browser_issues':issues})
   print(name,results[name]['status'],flush=True)
  detail='/projects/'+cfg['project']+'/'
  source={'budget':str(Project.objects.get(pk=cfg['project']).estimated_budget),'active_contracts':Contract.objects.filter(project_id=cfg['project'],status='active').count(),'reports':DailyReport.objects.filter(project_id=cfg['project']).count(),'wbs':WBSNode.objects.filter(project_id=cfg['project'],archived_at__isnull=True).count(),'activities':Activity.objects.filter(project_id=cfg['project'],archived_at__isnull=True).count()}
  def responsive(width,height):
   owner.set_viewport_size({'width':width,'height':height});go(owner,detail)
   assert owner.locator('#workplan').evaluate('(e)=>e.previousElementSibling.id')=='overview'
   assert owner.locator('#workplan .erp-btn--primary').count()==1
   assert not owner.locator('#progress meter, #progress progress, #progress canvas').count()
   assert owner.locator('#workplan .project-workplan__stats dd').all_text_contents()==[str(source[k]).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹')) for k in ['wbs','activities']]+['۲']
   assert owner.locator('[data-kpi-tone=contracts] bdi').inner_text()==str(source['active_contracts']).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
   assert owner.locator('[data-kpi-tone=cost] bdi').inner_text().strip()=='—'
   trigger=owner.locator('.project-nav-more summary');trigger.focus();owner.keyboard.press('Enter');assert owner.locator('.project-nav-more').get_attribute('open') is not None
   owner.keyboard.press('Escape');assert owner.locator('.project-nav-more').get_attribute('open') is None
   assert trigger.evaluate('(e)=>document.activeElement===e')
   main=owner.locator('main');assert not re.search(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',main.inner_text())
   measure=owner.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth,dir:document.documentElement.dir})');assert measure['document']<=width+1 and measure['dir']=='rtl'
   return measure
  for width,height in [(1440,900),(1024,768),(390,844)]:check('responsive-keyboard-'+str(width),lambda w=width,h=height:responsive(w,h))
  def operational_preview():
   go(owner,detail)
   tree=owner.locator('.project-workplan__tree')
   assert tree.locator('> li').count()==3
   assert 'آماده‌سازی مسیر دسترسی' in tree.inner_text()
   branch=tree.locator('> li').first
   assert branch.locator('> div > span').inner_text()=='۳ فعالیت'
   assert branch.locator('ul li > div > span').last.inner_text()=='۲ فعالیت'
   assert owner.locator('.project-workplan__activities li').count()==5
   assert 'برنامه فعالیت:' in owner.locator('.project-workplan__activities').inner_text()
   assert owner.locator('#workplan .erp-btn').count()==1
   assert owner.locator('#workplan a').count()==2
   assert owner.locator('#workplan .erp-btn').inner_text().startswith('مدیریت ساختار شکست و فعالیت‌ها')
   assert owner.locator('.erp-project-quick a').count()==2
   assert owner.locator('.erp-project-quick [data-action-kind=view]').count()==0
   assert owner.locator('#costs meter, #progress meter, #progress canvas').count()==0
   assert owner.locator('[data-project-photo-fallback]').is_hidden() # mobile lightweight fallback omitted
   samples=[]
   for width,height in [(1440,900),(1024,768),(390,844)]:
    owner.set_viewport_size({'width':width,'height':height})
    row=owner.locator('.project-recent-record').filter(has_text='Supplier inspection')
    title=row.locator('.project-recent-record__title')
    assert title.inner_text()==cfg['long_description']
    measurements=title.evaluate('(e)=>({height:e.getBoundingClientRect().height,line:parseFloat(getComputedStyle(e).lineHeight),clamp:getComputedStyle(e).webkitLineClamp})')
    assert measurements['clamp']=='2' and measurements['height']<=measurements['line']*2+1
    trigger=row.locator('summary');trigger.focus();owner.keyboard.press('Enter')
    assert row.locator('details').get_attribute('open') is not None
    assert row.locator('details p').inner_text()==cfg['long_description']
    assert trigger.evaluate('(e)=>getComputedStyle(e).outlineStyle')!='none'
    owner.keyboard.press('Enter')
    samples.append({'width':width,'height':height,'full_title_keyboard':True,'visual_title':measurements})
   return {'root_subtree_activities':3,'child_subtree_activities':2,'sample_activities':5,'quick_create_only':True,'long_titles':samples}
  check('operational-hierarchy-action-dedup-and-full-titles',operational_preview)
  def photo_fallback():
   import base64,struct,zlib
   def png(width,height):
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    payload=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\x15\x63\xd6'*width)*height))+chunk(b'IEND',b'')
    return 'data:image/png;base64,'+base64.b64encode(payload).decode()
   results=[]
   for width,height,usable in [(1,1,False),(320,180,True)]:
    go(owner,detail);owner.set_viewport_size({'width':1440,'height':900})
    owner.evaluate('(src)=>{const img=document.createElement("img");img.dataset.projectPhoto="";img.className="project-hero__image";img.hidden=true;img.src=src;document.querySelector(".project-hero__body").append(img)}',png(width,height))
    owner.wait_for_function('document.querySelector("[data-project-photo]").complete')
    owner.add_script_tag(path=str(repo/'apps/projects/static/projects/project_dashboard.js'))
    assert owner.locator('[data-project-photo]').is_visible()==usable
    assert owner.locator('[data-project-photo-fallback]').is_visible()!=usable
    results.append({'natural_width':width,'natural_height':height,'photo_visible':usable,'scope':'presentation dimension guard; DMS authorization covered by Django'})
   return results
  check('photo-dimension-fallback',photo_fallback)
  def controls_navigation():
   go(owner,detail);link=owner.locator('#workplan .erp-btn--primary');href=link.get_attribute('href');link.click();owner.wait_for_load_state('networkidle')
   assert urlsplit(owner.url).path==href and cfg['project'] in owner.url
   assert 'ساختار شکست و فعالیت‌ها' in owner.locator('main h1').inner_text()
   assert owner.locator('#activities-title').count()==1 and owner.locator('#wbs-title').count()==1
   owner.get_by_role('link',name='بازگشت به مرکز کنترل پروژه',exact=True).click();owner.wait_for_load_state('networkidle');assert urlsplit(owner.url).path==detail
   return {'path':href,'project_retained':True,'return':detail}
  check('wbs-activities-and-return',controls_navigation)
  def destinations():
   go(owner,detail);owner.locator('.project-nav-more summary').click()
   urls=owner.locator('main a[href]').evaluate_all('(es)=>[...new Set(es.map(e=>e.getAttribute("href")))].filter(x=>x.startsWith("/")&&!x.startsWith("//"))')
   observed={}
   for url in urls:
    response=owner.context.request.get(base+url);observed[url]=response.status;assert response.status==200,(url,response.status)
   return observed
  check('all-dashboard-get-destinations',destinations)
  def quick_forms():
   data={}
   for path in ['/daily-reports/create/','/expenses/create/']:
    page=go(owner,path+'?project='+cfg['project']);assert page.locator('[name=project]').input_value()==cfg['project'];data[path]='authorized project preselected'
   return data
  check('quick-create-project-initialization',quick_forms)
  def equipment_navigation():
   go(owner,detail);owner.locator('.project-nav-more summary').click();owner.locator('.project-nav-more a').filter(has_text='تجهیزات پروژه').click();owner.wait_for_load_state('networkidle')
   assert parse_qs(urlsplit(owner.url).query)['project']==[cfg['project']]
   text=owner.locator('main').inner_text();assert 'جرثقیل برجی باغستان' in text and 'تجهیز پروژه دیگر' not in text
   search=owner.locator('#list-filter-bar [name=equipment]');search.fill('CRANE-01');search.press('Enter');owner.wait_for_load_state('networkidle')
   assert parse_qs(urlsplit(owner.url).query)['project']==[cfg['project']]
   clears=owner.locator('main a[data-table-filter-clear]');assert all(parse_qs(urlsplit(x).query).get('project')==[cfg['project']] for x in clears.evaluate_all('(es)=>es.map(e=>e.href)'))
   owner.locator('.erp-list-title a').first.click();owner.wait_for_load_state('networkidle')
   assert parse_qs(urlsplit(owner.url).query)['project']==[cfg['project']]
   owner.locator('main a').filter(has_text='عملیات تجهیزات').first.click();owner.wait_for_load_state('networkidle')
   query=parse_qs(urlsplit(owner.url).query);assert query['project']==[cfg['project']] and query['equipment']==[cfg['equipment']]
   text=owner.locator('main').inner_text();assert 'جرثقیل برجی باغستان' in text and 'تجهیز پروژه دیگر' not in text
   owner.get_by_role('link',name='بازگشت به داشبورد پروژه',exact=True).click();owner.wait_for_load_state('networkidle');assert urlsplit(owner.url).path==detail
   return {'project':cfg['project'],'assignment_association':True,'ownership_changed':False,'return':detail}
  check('equipment-list-detail-operations-return',equipment_navigation)
  def isolation():
   page=page_for('scoped');go(page,detail)
   statuses={}
   for path in ['/equipment/','/equipment/operations/']:
    statuses[path+'own']=page.context.request.get(base+path+'?project='+cfg['project']).status;assert statuses[path+'own']==200
    for key in ['sibling','foreign']:
     status=page.context.request.get(base+path+'?project='+cfg[key]).status;statuses[path+key]=status;assert status==403
   status=page.context.request.get(base+'/equipment/'+cfg['other_equipment']+'/?project='+cfg['project']).status;assert status==404
   limited=page_for('restricted');go(limited,detail);assert not limited.locator('#workplan a').count()
   assert not limited.locator('main a[href^="/equipment/"]').count()
   assert limited.context.request.get(base+'/equipment/?project='+cfg['project']).status==403
   return statuses
  check('project-role-positive-and-foreign-denial',isolation)
  def empty():
   owner.set_viewport_size({'width':390,'height':844})
   go(owner,'/projects/'+cfg['empty']+'/');assert 'هنوز ساختار اجرایی پروژه تعریف نشده است' in owner.locator('#workplan').inner_text()
   assert owner.locator('#workplan .erp-btn--primary').count()==1 and not owner.locator('#progress canvas, #progress meter').count()
   assert not owner.locator('#costs meter').count()
   owner.screenshot(path=out/'empty-390.png',full_page=True,animations='disabled')
   return {'start_action':True,'fabricated_progress':False,'fabricated_actual':False}
  check('empty-workplan-and-unavailable-measurements',empty)
  def protected():
   page=page_for('platform');observations=[]
   for path in [reverse('organizations:platform_company_list'),reverse('organizations:platform_company_detail',args=[cfg['company']])]:
    go(page,path)
    for width,height in [(1440,900),(1024,768),(390,844)]:
     page.set_viewport_size({'width':width,'height':height});page.evaluate('async()=>await document.fonts.ready')
     doc=page.evaluate('document.documentElement.scrollWidth');assert doc<=width+1;observations.append({'route':urlsplit(path).path,'width':width,'document':doc,'status':200})
   page=go(owner,'/projects/');assert page.locator('main h1').count()==1
   return observations
  check('protected-company-pages-and-projects-list',protected)
  save('chrome-final.json',{'browser':b.version,'database':db,'source_values':source,'cases':results,'browser_issues':issues})
  assert not issues,issues
  assert all(x['status']=='PASS' for x in results.values())
  b.close()
finally:proc.terminate();proc.wait(timeout=15);log.close()
