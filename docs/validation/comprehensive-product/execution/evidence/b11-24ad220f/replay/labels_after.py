from sweep import Browser,host,load_fixtures,sessions,write,sync_playwright
import os,re
actors,s=load_fixtures()
proc,origin,log=host()
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome')
  run=Browser(b,origin,actors,sessions(actors))
  results={}
  for key,who,path in [('equipment','field','/equipment/create/'),('payable','payable','/billing/payable-measurements/new/'),('statutory','billing','/billing/taxpayer-invoices/new/')]:
   page,response=run.get(who,path)
   result={'status':response.status,'path':path,'role':who}
   result['controls']=page.locator('main').aria_snapshot(timeout=15000)[:5000]
   if key=='equipment':
    result['category']=page.locator('[name=category]').evaluate("(el)=>({labels:[...el.labels].map(e=>e.textContent.trim()),outer:el.outerHTML})")
   else:
    field='contract_item' if key=='payable' else 'source_claim'
    result['options']=page.locator(f'[name={field}] option').all_text_contents()
   results[key]=result
  write('labels-after.json',results)
  assert results['equipment']['controls'].count('combobox') == 2
  for key in ('payable','statutory'):
   options=results[key]['options']
   assert len(options)>1 and not any('object (' in item or re.search(r'[a-f0-9]{8}-[a-f0-9-]{27}',item) for item in options)
  assert all(v['status']==200 for v in results.values())
finally:
 proc.terminate();proc.wait(timeout=15);log.close()

