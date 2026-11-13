from browser import *
from django.urls import reverse
proc,base,log=start();checks=[]
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True)
  for actor,paths in [('owner',['/projects/']),('platform',[reverse('organizations:platform_company_list'),reverse('organizations:platform_company_detail',args=[cfg['company']])])]:
   ctx=context(b,base,actor);page=ctx.new_page()
   for width,height in [(1440,900),(1024,768),(390,844)]:
    page.set_viewport_size({'width':width,'height':height})
    for path in paths:
     response=page.goto(base+path,wait_until='networkidle');assert response.status==200
     page.evaluate('async()=>await document.fonts.ready')
     assert page.locator('main h1').count()==1
     measured=page.evaluate('document.documentElement.scrollWidth');assert measured<=width+1
     checks.append({'path':path,'width':width,'height':height,'status':response.status,'document_width':measured})
   ctx.close()
  b.close()
finally:proc.terminate();proc.wait(timeout=15);log.close();save('protected-responsive.json',checks)
print('Protected Projects List and Platform Company List/Detail: 9 exact viewport states PASS.')
