// Trusted execution helper. Browser control exclusively through supplied cua tabs.
import * as fs from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
const root='E:/Construction_Company_Solution/docs/governance/cep/evidence/CEP-078_REENTRY_03/';
export const plan=JSON.parse(await fs.readFile(root+'BROWSER_PLAN.json','utf8')).rows;
const auth=JSON.parse(await fs.readFile(root+'AUTHENTICATION.json','utf8'));
export const ctx={surfaces:JSON.parse(await fs.readFile(root+'SURFACE_RESULTS.json','utf8')),auth,active:Object.fromEntries(auth.map(r=>[r.family,r.alias]))};
export const save=async(name,value)=>fs.writeFile(root+name,JSON.stringify(value,null,2));
export async function probe(tab){return tab.playwright.evaluate(()=>{
 const d=document,vis=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const all=Array.from(d.querySelectorAll('[id]'));
 return {url:d.URL,title:d.title,width:window.innerWidth,height:window.innerHeight,clientWidth:d.documentElement.clientWidth,scrollWidth:d.documentElement.scrollWidth,
 main:d.querySelectorAll('main,[role=main]').length,h1:Array.from(d.querySelectorAll('h1')).map(e=>e.textContent.trim()),lang:d.documentElement.lang,dir:d.documentElement.dir,
 unlabelled:Array.from(d.querySelectorAll('input:not([type=hidden]),select,textarea')).filter(vis).filter(e=>!(e.labels?.length)&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')&&!['submit','button'].includes(e.type)).map(e=>({tag:e.tagName,id:e.id,name:e.name,type:e.type})),
 unlabelledButtons:Array.from(d.querySelectorAll('button')).filter(vis).filter(e=>!e.textContent.trim()&&!e.getAttribute('aria-label')&&!e.getAttribute('title')).length,
 duplicateIds:all.map(e=>e.id).filter((v,i,a)=>a.indexOf(v)!==i),
 tables:Array.from(d.querySelectorAll('table')).map(e=>({headers:e.querySelectorAll('th').length,caption:!!e.caption,overflowContainer:e.parentElement?getComputedStyle(e.parentElement).overflowX:null})),
 focus:{id:d.activeElement?.id,tag:d.activeElement?.tagName,outline:getComputedStyle(d.activeElement).outline,shadow:getComputedStyle(d.activeElement).boxShadow}};
});}
export async function signIn(family,tab,alias){
 if(ctx.active[family]===alias)return;
 const state=await tab.playwright.evaluate(()=>({login:!!document.querySelector('#id_username'),menu:!!document.querySelector('summary[aria-label="باز کردن فهرست"]')?.getClientRects().length,desktopLogout:!!document.querySelector('aside form[action*="logout"] button')?.getClientRects().length}));
 if(!state.login){
  if(state.desktopLogout)await tab.playwright.locator('aside form[action*="logout"] button').click();
  else if(state.menu){await tab.playwright.locator('summary[aria-label="باز کردن فهرست"]').click();await tab.getAXState({emit:false});await tab.playwright.locator('.erp-mobile-nav__panel form[action*="logout"] button').click();}
  else throw Error('No governed visible logout in current context');
  await tab.playwright.waitForURL('http://127.0.0.1:8000/accounts/login/',{timeoutMs:15000});await tab.getAXState({emit:false});
 }
 let secret=execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',"$a=[Console]::In.ReadToEnd(); $p=Join-Path $env:LOCALAPPDATA ('BONIRA/UIUXRuntimeAudit/credentials/'+$a+'.clixml'); (Import-Clixml -LiteralPath $p).GetNetworkCredential().Password"],{input:alias,encoding:'utf8'}).trim();
 await tab.playwright.locator('#id_username').fill(alias);await tab.playwright.locator('#id_password').fill(secret);secret=null;
 await tab.playwright.getByRole('button',{name:'ورود به سامانه',exact:true}).click();
 await tab.playwright.waitForURL('http://127.0.0.1:8000/',{timeoutMs:15000});await tab.getAXState({emit:false});
 ctx.active[family]=alias;ctx.auth.push({at:new Date().toISOString(),family,alias,method:'Normal existing credential login from local protected store; no resets/grants/session injection'});await save('AUTHENTICATION.json',ctx.auth);
}
export async function run(family,tab,vp,start,end){
 const summary=[];
 for(const row of plan.slice(start,end)){
  await signIn(family,tab,row.actor);await tab.goto('http://127.0.0.1:8000'+row.path);
  await fs.writeFile(root+row.id+'_'+family+'.ax.txt',await tab.getAXState({emit:false}));
  for(const [w,h]of row.viewports){
   await vp.set({width:w,height:h});const p=await probe(tab);
   const checks={exactViewport:p.width===w&&p.height===h,singleMain:p.main===1,oneH1:p.h1.length===1,noPageOverflow:p.scrollWidth<=p.clientWidth,labelledVisibleFields:p.unlabelled.length===0,namedVisibleButtons:p.unlabelledButtons===0,uniqueIds:p.duplicateIds.length===0,persianRtl:p.lang==='fa'&&p.dir==='rtl',notLoginRedirect:!p.url.includes('/accounts/login/')};
   const result=Object.values(checks).every(Boolean)?'PASS':'FAIL';let capture=null;
   if(w===390||result==='FAIL'){capture=row.id+'_'+family+'_'+w+'.jpg';await fs.writeFile(root+capture,await tab.getScreenshot({emit:false}));}
   const record={at:new Date().toISOString(),...row,family,viewport:[w,h],measurement:p,checks,result,capture,limitations:'Current prepared browser state only; no domain transaction/lifecycle or WCAG certification'};
   ctx.surfaces.push(record);await save('SURFACE_RESULTS.json',ctx.surfaces);summary.push({id:row.id,w,result,failed:Object.keys(checks).filter(k=>!checks[k])});
  }
 }
 return {cases:summary.length,failed:summary.filter(r=>r.result==='FAIL')};
}
