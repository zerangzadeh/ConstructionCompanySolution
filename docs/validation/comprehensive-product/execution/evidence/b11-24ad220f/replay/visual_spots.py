from sweep import *
actors,s=load_fixtures();proc,origin,log=host();out={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  for name,actor,path,width,height in [('equipment','field','/equipment/create/',390,844),('payable','payable','/billing/payable-measurements/new/',1440,900),('taxpayer','billing','/billing/taxpayer-invoices/new/',390,844)]:
   page,r=run.get(actor,path);assert r.status==200;page.set_viewport_size({'width':width,'height':height});page.evaluate('async()=>await document.fonts.ready')
   page.screenshot(path=OUT/(name+'-final.png'),full_page=True,animations='disabled')
   out[name]={'path':path,'viewport':width,'status':r.status,'h1':page.locator('main h1').all_text_contents(),'controls':page.locator('main').aria_snapshot()}
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('visual-spots.json',out)
