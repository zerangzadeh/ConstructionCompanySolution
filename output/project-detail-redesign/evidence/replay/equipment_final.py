from browser import *
from urllib.parse import urlsplit,parse_qs
assert db=='project_redesign_retest'
proc,base,log=start();result={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True)
  for actor in ['owner','scoped']:
   ctx=context(b,base,actor);page=ctx.new_page();observations=[]
   for width,height in [(1440,1000),(1024,820),(390,844)]:
    page.set_viewport_size({'width':width,'height':height})
    for path in ['/equipment/?project='+cfg['project'],'/equipment/'+cfg['equipment']+'/?project='+cfg['project'],'/equipment/operations/?project='+cfg['project']+'&equipment='+cfg['equipment']]:
     response=page.goto(base+path,wait_until='networkidle');assert response.status==200
     text=page.locator('main').inner_text();assert 'جرثقیل برجی باغستان' in text and 'تجهیز پروژه دیگر' not in text
     assert page.evaluate('document.documentElement.scrollWidth')<=width+1
     if actor=='scoped':
      assert not page.locator('main a[href="/equipment/create/"]').count()
      assert not page.locator('main form[action$="/status/"]').count()
     if '/operations/' in path:
      crumb=page.locator('main a[href^="/equipment/?project="]');assert crumb.count()==1
      urls=page.locator('main a[href]').evaluate_all('(es)=>[...new Set(es.map(e=>e.getAttribute("href")))].filter(x=>x.startsWith("/")&&!x.startsWith("//"))')
      for url in urls:
       r=ctx.request.get(base+url);assert r.status==200,(actor,url,r.status)
     observations.append({'width':width,'path':path,'status':200,'no_overflow':True})
     if actor=='owner' and width==390 and '/operations/' in path:page.screenshot(path=out/'equipment-operations-390.png',full_page=True,animations='disabled')
   result[actor]=observations
  owner_context=context(b,base,'owner');page=owner_context.new_page()
  page.goto(base+'/equipment/?project='+cfg['empty'],wait_until='networkidle')
  assert 'هنوز تخصیص تجهیزی برای این پروژه وجود ندارد' in page.locator('main').inner_text()
  result['empty_assignment_state']='PASS'
  b.close()
finally:proc.terminate();proc.wait(timeout=15);log.close();save('equipment-final.json',result)
print('Equipment owner/scoped roles: 18 responsive page states and action destinations PASS.')
