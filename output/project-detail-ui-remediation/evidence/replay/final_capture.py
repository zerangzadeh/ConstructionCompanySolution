from browser import *
proc,base,log=start()
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);ctx=context(b,base,'owner');page=ctx.new_page()
  response=page.goto(base+'/projects/'+cfg['project']+'/',wait_until='networkidle');assert response.status==200
  layouts=capture(page,'after');assert [(x['width'],x['height']) for x in layouts]==[(1440,900),(1024,768),(390,844)]
  assert all(x['width']==x['document'] for x in layouts)
  save('after-responsive.json',{'browser':b.version,'database':db,'layouts':layouts})
  response=page.goto(base+'/projects/'+cfg['empty']+'/',wait_until='networkidle');assert response.status==200
  assert not page.locator('.project-workplan__preview').count()
  assert not page.locator('#progress meter,#costs meter').count()
  page.screenshot(path=out/'empty-390.png',full_page=True,animations='disabled')
  save('empty-responsive.json',{'width':page.viewport_size['width'],'height':page.viewport_size['height'],'document_width':page.evaluate('document.documentElement.scrollWidth'),'preview_omitted':True,'false_measurement_bars':False})
  b.close()
finally:proc.terminate();proc.wait(timeout=15);log.close()
print('Final exact viewport captures and compact empty-state retest PASS.')
