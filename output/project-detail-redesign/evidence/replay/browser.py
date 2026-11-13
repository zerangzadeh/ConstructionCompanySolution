import os,sys,json,socket,subprocess,time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit
root=Path(__file__).resolve().parent;repo=root.parents[1];out=repo/'output/project-detail-redesign/evidence'
sys.path.insert(0,'C:/Users/azera/AppData/Local/Temp/bonira-b02-01a1c63c/pylibs')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE']='true'
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.test import Client
from apps.accounts.models import User
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from playwright.sync_api import sync_playwright
cfg=json.loads((root/'fixtures.json').read_text())
with connection.cursor() as c:
 c.execute("select current_database(),current_setting('data_directory')");db,directory=c.fetchone()
assert db in ['project_redesign_original','project_redesign_retest'] and Path(directory).resolve()==repo/'.scratch/b11-validation/pg'

def start():
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 log=(root/'server.log').open('ab')
 proc=subprocess.Popen([sys.executable,'manage.py','runserver','--noreload','--insecure',f'127.0.0.1:{port}'],cwd=repo,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
 base=f'http://127.0.0.1:{port}'
 for _ in range(80):
  try:
   if urlopen(base+'/accounts/login/',timeout=1).status==200:return proc,base,log
  except Exception:time.sleep(.15)
 raise RuntimeError('Isolated Django did not start')
def context(browser,base,actor):
 client=Client();client.force_login(User.objects.get(pk=cfg['actors'][actor]));s=client.session;s[ACTIVE_ORGANIZATION_SESSION_KEY]=cfg['organization'];s.save()
 ctx=browser.new_context(viewport={'width':1440,'height':1000},locale='fa-IR',timezone_id='Asia/Tehran');ctx.add_cookies([{'url':base,'name':settings.SESSION_COOKIE_NAME,'value':s.session_key,'httpOnly':True}]);return ctx

def capture(page,name):
 result=[]
 for width,height in [(1440,1000),(1024,820),(390,844)]:
  page.set_viewport_size({'width':width,'height':height});page.evaluate('async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}')
  result.append(page.evaluate('''()=>({width:innerWidth,document:document.documentElement.scrollWidth,dir:document.documentElement.dir,lang:document.documentElement.lang,main:document.querySelectorAll('main').length,h1:document.querySelector('main h1')?.innerText,headings:[...document.querySelectorAll('main h2')].map(x=>x.innerText)})'''))
  page.screenshot(path=out/f'{name}-{width}.png',full_page=True,animations='disabled')
 return result

def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':
 phase=sys.argv[1];proc,base,log=start()
 try:
  with sync_playwright() as p:
   b=p.chromium.launch(channel='chrome',headless=True);ctx=context(b,base,'owner');page=ctx.new_page();r=page.goto(base+'/projects/'+cfg['project']+'/',wait_until='networkidle');assert r.status==200
   save(phase+'-responsive.json',{'browser':b.version,'database':db,'layouts':capture(page,phase)})
   b.close()
 finally:proc.terminate();proc.wait(timeout=15);log.close()
