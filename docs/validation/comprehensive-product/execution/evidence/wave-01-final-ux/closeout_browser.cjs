const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/azera/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='E:/Construction_Company_Solution',e=path.join(root,'docs/validation/comprehensive-product/execution/evidence/wave-01-final-ux');
const fixture=JSON.parse(fs.readFileSync(path.join(process.env.TEMP,'bonira-wave01-final-ux/fixture.json'),'utf8'));
const origin='http://127.0.0.1:8189',phase=process.argv[2],out={phase,checks:[],screenshots:[],errors:[]};
let browser;
function assert(v,m){if(!v)throw Error(m)}
async function step(id,fn){try{out.checks.push({id,status:'PASS',actual:await fn()})}catch(err){out.checks.push({id,status:'FAIL',actual:err.message.split('\n').slice(0,3).join(' ')})}finally{write()}}
function write(){fs.writeFileSync(path.join(e,'browser-'+phase+'.json'),JSON.stringify(out,null,2))}
async function go(p,url){const r=await p.goto(origin+url);await p.evaluate(()=>document.fonts.ready);return r.status()}
async function submit(p,button){await Promise.all([p.waitForNavigation({waitUntil:'load'}),button.click()]);await p.evaluate(()=>document.fonts.ready)}
async function capture(p,name){await p.screenshot({path:path.join(e,name+'.png'),fullPage:true,animations:'disabled'});out.screenshots.push(name+'.png')}
async function metrics(p){return p.evaluate(()=>({width:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,dir:document.documentElement.dir,rows:document.querySelectorAll('main table tbody tr').length,tableWidth:document.querySelector('main table')?.getBoundingClientRect().width,controls:[...document.querySelectorAll('main button,main input:not([type=hidden]),main select,main .erp-list-row-action a')].filter(x=>x.getBoundingClientRect().width&&getComputedStyle(x).visibility!=='hidden').map(x=>{const r=x.getBoundingClientRect();return {label:x.getAttribute('aria-label')||x.textContent.trim()||x.name,x:r.x,y:r.y,width:r.width,height:r.height}})}))}
async function rows(p){return p.locator('main table tbody').innerText()}
(async()=>{
 browser=await chromium.launch({channel:'chrome',headless:true});out.chrome=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:900},locale:'fa-IR',timezoneId:'Asia/Tehran'});
 await context.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());
 const p=await context.newPage();p.setDefaultTimeout(6000);p.on('pageerror',err=>out.errors.push(err.message));
 await go(p,'/accounts/login/');await p.locator('[name=username]').fill(fixture.username);await p.locator('[name=password]').fill(fixture.password);await submit(p,p.locator('button[type=submit]'));
 const audit='/organizations/platform/activity/',companies='/organizations/platform/companies/';
 if(phase==='before')await step('UX-R-OBS-01-reproduction',async()=>{
   await go(p,audit);const original=await rows(p);await p.locator('[name=start]').fill('1405/13/50');await p.waitForTimeout(900);await p.waitForLoadState('load');
   const actual={query:new URL(p.url()).search,display:await p.locator('[name=start]').inputValue(),resultsChanged:original!==await rows(p)};
   await capture(p,'audit-invalid-before-1440');assert(actual.query.includes('1405'),'No invalid navigation');assert(actual.display==='','Invalid input not lost');return actual;
 });
 if(phase==='after'){
   for(const width of [1440,1024,390])await step('UX-R-OBS-01-retain-and-block-'+width,async()=>{
     await p.setViewportSize({width,height:width===390?844:900});await go(p,audit);const original=await rows(p),url=p.url();
     await p.locator('[name=start]').fill('1405/13/50');await p.waitForTimeout(700);
     await p.locator('main button[type=submit]').click();await p.waitForTimeout(200);
     const actual={value:await p.locator('[name=start]').inputValue(),validation:await p.locator('[name=start]').evaluate(x=>x.validationMessage),urlUnchanged:p.url()===url,resultsUnchanged:await rows(p)===original,...await metrics(p)};
     await capture(p,'audit-invalid-after-'+width);assert(actual.value==='1405/13/50','Lost input');assert(actual.validation.includes('تاریخ'),'Missing Persian error');assert(actual.urlUnchanged&&actual.resultsUnchanged,'Invalid filter changed results');return actual;
   });
   await step('AUDIT-partial-valid-conversion-clear-direct-invalid',async()=>{
     await p.setViewportSize({width:1440,height:900});await go(p,audit);let original=await rows(p),url=p.url();
     await p.locator('[name=start]').fill('1405/08');await p.locator('main button[type=submit]').click();await p.waitForTimeout(600);
     assert(p.url()===url&&await rows(p)===original,'Partial input changed results');assert(await p.locator('[name=start]').evaluate(x=>x.validationMessage.includes('تاریخ')),'Partial lacks Persian feedback');
     await p.locator('[name=start]').fill('1405/08/17');await p.locator('[name=end]').fill('1405/08/20');
     await submit(p,p.locator('main button[type=submit]'));
     const params=new URL(p.url()).searchParams;assert(params.get('start')==='2026-11-08'&&params.get('end')==='2026-11-11','Canonical conversion changed');
     assert(await p.locator('[name=start]').inputValue()==='1405/08/17','Valid display wrong');await capture(p,'audit-valid-range-1440');
     await submit(p,p.locator('main a').filter({hasText:'پاک‌کردن'}));assert(!new URL(p.url()).search,'Clear failed');
     await go(p,audit+'?start=1405%2F13%2F50');assert(await p.locator('[name=start]').inputValue()==='1405/13/50','Direct invalid value lost');
     const errors=await p.locator('.erp-form-field--invalid').innerText();assert(errors.includes('تاریخ'),'Server error not Persian');await capture(p,'audit-direct-invalid-1440');
     return {partialBlocked:true,canonicalStart:params.get('start'),canonicalEnd:params.get('end'),clear:true,directInvalidRetained:true,serverError:errors};
   });
 }
 if(phase==='companies'){
   for(const width of [1440,1024,390])await step('PA-03-final-css-'+width,async()=>{
     await p.setViewportSize({width,height:width===390?844:900});assert(await go(p,companies)===200,'Page not 200');const m=await metrics(p);assert(m.dir==='rtl','No RTL');assert(m.scroll<=m.client+1,'Horizontal document overflow');assert(m.rows>0,'No table');
     const links=await p.locator('.erp-list-row-action a').evaluateAll(xs=>xs.map(x=>({label:x.textContent.trim(),href:x.getAttribute('href')})));assert(links.every(x=>/\/companies\/[a-f0-9-]+\/$/.test(x.href)&&x.label.includes('فعالیت')),'Misleading row action');
     await capture(p,'companies-final-'+width);
     const first=p.locator('.erp-list-row-action a').first(),target=await first.getAttribute('href');await submit(p,first);assert(new URL(p.url()).pathname===target,'Row destination mismatch');
     await go(p,companies);const search=p.locator('main input[name=q]');await search.fill('ux-page-03');await submit(p,p.locator('main form button[type=submit]').first());assert((await rows(p)).includes('ux-page-03'),'Search failed');assert(await p.locator('main tbody tr').count()===1,'Search not narrowed');await capture(p,'companies-filtered-'+width);
     await go(p,companies+'?q=no-such-company-closeout');assert(await p.locator('main').innerText().then(x=>x.includes('یافت نشد')||x.includes('نتیجه')),'No empty feedback');
     await go(p,companies);const status=p.locator('main select[name=status]');if(await status.count()){await status.selectOption('suspended');await submit(p,p.locator('main form button[type=submit]').first());assert(new URL(p.url()).searchParams.get('status')==='suspended','Status not submitted');const labels=await p.locator('td.erp-list-status').allTextContents();assert(labels.every(x=>!x.includes('فعال')||x.includes('غیرفعال')),'Status mismatch');}
     await go(p,companies+'?sort=name&direction=asc');const sort=p.locator('main th a').first();if(await sort.count()){await submit(p,sort);assert(new URL(p.url()).searchParams.has('sort'),'Sort navigation failed');}
     await go(p,companies+'?page=2');assert(await p.locator('main tbody tr').count()>0,'Page 2 empty');
     await go(p,companies);const create=p.locator('main a[href="/organizations/create/"]');if(await create.count()){await submit(p,create);assert(new URL(p.url()).pathname==='/organizations/create/','Create destination wrong');}
     return {...m,rowDestinations:links,search:true,empty:true,status:true,sort:true,page2:true,detail:true};
   });
 }
 if(phase==='auth'){
   await context.close();
   const auth=await browser.newContext({viewport:{width:1440,height:900},locale:'fa-IR',timezoneId:'Asia/Tehran'});
   await auth.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());
   const ap=await auth.newPage();const paths={login:'/accounts/login/',reset:'/accounts/password/reset/',done:'/accounts/password/reset/done/',confirm:fixture.reset_path,complete:'/accounts/password/reset/complete/'};
   for(const [id,url] of Object.entries(paths))for(const width of [1440,390])await step('AUTH-review-'+id+'-'+width,async()=>{
     await ap.setViewportSize({width,height:width===390?844:900});assert(await go(ap,url)===200,'Not 200');if(id==='confirm')assert(await ap.locator('[name=new_password1]').count()===1,'Valid confirm form missing');
     await capture(ap,'auth-'+id+'-'+width);return {route:id==='confirm'?'/accounts/password/reset/<uid>/<token>/':url,...await metrics(ap)};
   });await auth.close();
 }
 await browser.close();write();console.log(JSON.stringify({phase,passed:out.checks.filter(x=>x.status==='PASS').length,failed:out.checks.filter(x=>x.status==='FAIL'),errors:out.errors}));
})().catch(async err=>{out.errors.push(err.message.split('\n')[0]);write();await browser?.close();process.exit(1)});
