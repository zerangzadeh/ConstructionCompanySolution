// Genuine browser login; secrets remain in DPAPI and process memory only.
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const {chromium} = require('C:/Users/azera/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=__dirname;
const fixtures=JSON.parse(fs.readFileSync(path.join(out,'FIXTURES.json'),'utf8'));
const input=JSON.parse(fs.readFileSync(path.join(out,'BROWSER_INPUT.json'),'utf8'));
const phase=process.argv[2] || 'before';
const base='http://127.0.0.1:8015';
function credential(alias){
  return execFileSync('C:/Users/azera/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe',['-NoProfile','-Command',`$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/${alias}.clixml'); $c.GetNetworkCredential().Password`],{encoding:'utf8'}).trim();
}
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const records=[];
 for(const [alias,targets] of [
 ['uiux.persona.inventory',[
 ['RV-009','/inventory/'],['RV-009','/inventory/custody/'],['RV-009','/inventory/valuation/']]],
 ['uiux.audit.project',[
 ['RV-007',`/procurement/rfqs/${fixtures.rfqs.A.id}/buyer/`],
 ['RV-009','/inventory/custody/'],['RV-009','/inventory/valuation/'],
 ['RV-013','/subledgers/'],['RV-015','/workforce/teams/'],
 ['RV-015','/workforce/foundation/'],['RV-017','/timekeeping/'],
 ['RV-028','/documents/'],['RV-028',`/documents/${input.docs.A}/`],
 ['RV-030','/contracts/'],['RV-030','/contracts/1c869bb0-cb4b-4a47-8210-87167b90ee6f/commercial-review/'],
 ['RV-030','/commercial/'],['RV-031',`/projects/${input.project_a}/controls/`],
 ['RV-032','/procurement/portal/accept/']]],
 ['account.demo-construction-01.accountant',[
 ['RV-013','/subledgers/'],
 ['RV-011','/accounting/statements/?kind=trial_balance&ends_on=1405%2F07%2F30'],
 ['RV-011',`/accounting/statements/${fixtures.statements.A}/`]]]
 ]){
  const ctx=await browser.newContext({viewport:{width:1440,height:900},locale:'fa-IR'});
  const page=await ctx.newPage();
  await page.goto(base+'/accounts/login/');
  await page.locator('[name=username]').fill(alias);
  await page.locator('[name=password]').fill(credential(alias));
  await Promise.all([page.waitForURL(u=>!u.pathname.includes('/accounts/login/')),page.locator('button[type=submit]').click()]);
  for(const [scenario,url] of targets){
   await page.setViewportSize({width:1440,height:900});
   const response=await page.goto(base+url);
   await page.waitForLoadState('networkidle');
   const id=`${phase}_browser_${String(records.length+1).padStart(2,'0')}`;
   const metrics=await page.evaluate(()=>({
    mains:document.querySelectorAll('main,[role=main]').length,
    headings:Array.from(document.querySelectorAll('#main-content h1,#main-content h2')).map(x=>x.textContent.trim()),
    styled:getComputedStyle(document.querySelector('body')).fontFamily,
    overflow:document.documentElement.scrollWidth>innerWidth,
    technicalText:Array.from(document.querySelectorAll('#main-content')).some(x=>/immutable|context|پیش‌نمایش trial_balance/.test(x.textContent)),
    details:Array.from(document.querySelectorAll('#main-content details')).map(x=>({summary:x.querySelector('summary')?.textContent,open:x.open})),
   }));
   await page.screenshot({path:path.join(out,id+'_desktop.png'),fullPage:true});
   const focus=[];
   for(let n=0;n<6;n++){
    await page.keyboard.press('Tab');
    focus.push(await page.evaluate(()=>({tag:document.activeElement.tagName,text:(document.activeElement.innerText||document.activeElement.getAttribute('aria-label')||'').slice(0,65),outline:getComputedStyle(document.activeElement).outlineStyle})));
   }
   await page.setViewportSize({width:390,height:844});
   await page.screenshot({path:path.join(out,id+'_mobile.png'),fullPage:true});
   const mobile=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth}));
   records.push({scenario,actor:alias,path:url,status:response.status(),browser:browser.version(),viewports:[[1440,900],[390,844]],metrics,mobile,focus,screenshots:[id+'_desktop.png',id+'_mobile.png']});
   fs.writeFileSync(path.join(out,phase+'_BROWSER.json'),JSON.stringify(records,null,2));
  }
  await ctx.close();
 }
 await browser.close();
 console.log(phase+' browser observations: '+records.length+'; screenshots '+records.length*2);
})().catch(e=>{console.error(e.message);process.exitCode=1});
