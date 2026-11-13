from sweep import *
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.jalali import format_jalali
actors,s=load_fixtures();proc,origin,log=host();out={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  page,r=run.get('rfq',reverse('procurement:portal_invitation_manage',args=[s['invitation'].pk]));assert r.status==200
  with timezone.override(ZoneInfo('Asia/Tehran')):expected=format_jalali(s['portal-grant'].portal_invitation.expires_at,include_time=True)
  assert expected in page.locator('main').inner_text().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789'))
  out['invitation']={'status':r.status,'expected_local_jalali':expected,'local_jalali_rendered':True,'widths':run.bounds(page)}
  contrast={}
  for actor,path in [('field','/equipment/create/'),('platform','/organizations/platform/member-roles/')]:
   page,r=run.get(actor,path);assert r.status==200
   samples=page.locator('main h1, main label, main .erp-btn--primary').evaluate_all('''es=>es.filter(e=>e.getClientRects().length).slice(0,16).map(e=>{const s=getComputedStyle(e);let x=e,bg;while(x){bg=getComputedStyle(x).backgroundColor;if(bg!=="rgba(0, 0, 0, 0)"&&bg!=="transparent")break;x=x.parentElement}return {tag:e.tagName,foreground:s.color,background:bg||"rgb(255,255,255)",size:s.fontSize,weight:s.fontWeight}})''')
   def lum(color):
    a=[int(x)/255 for x in re.findall(r'\d+',color)[:3]];a=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in a];return .2126*a[0]+.7152*a[1]+.0722*a[2]
   for sample in samples:
    x,y=sorted([lum(sample['foreground']),lum(sample['background'])]);sample['ratio']=round((y+.05)/(x+.05),2);sample['minimum']=3 if float(sample['size'][:-2])>=24 or (float(sample['size'][:-2])>=18.66 and int(sample['weight'])>=700) else 4.5
   contrast[actor]=samples
  out['contrast_spot_checks']=contrast
  assert all(x['ratio']>=x['minimum'] for samples in contrast.values() for x in samples)
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('invitation-and-contrast-final.json',out)
