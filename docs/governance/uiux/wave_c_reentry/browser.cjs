// Actual Edge rendering and keyboard checks against the fresh Development server.
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const {chromium} = require('C:/Users/azera/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=__dirname, base='http://127.0.0.1:8015';
const doc=JSON.parse(fs.readFileSync(path.join(out,'DOCUMENT_SCAN.json'),'utf8'));
const fixtures=JSON.parse(fs.readFileSync(path.join(out,'DOMAIN_FIXTURES.json'),'utf8'));
const old=JSON.parse(fs.readFileSync(path.join(out,'../wave_c_evidence/FIXTURES.json'),'utf8'));
const oldInput=JSON.parse(fs.readFileSync(path.join(out,'../wave_c_evidence/BROWSER_INPUT.json'),'utf8'));
const delta=process.argv[2]==='delta';
const linked=JSON.parse(fs.readFileSync(path.join(out,'EMPLOYMENT_IDENTITY.json'),'utf8'));
const targets=delta ? [
 ['RV-015','uiux.wavec.hr',`/workforce/employees/${linked.employee}/`],
 ['RV-029','uiux.wavec.time','/workforce/ess/employment/'],
] : [
 ['RV-007','uiux.wavec.buyer',`/procurement/rfqs/${old.rfqs.A.id}/buyer/`],
 ['RV-015','uiux.wavec.hr','/workforce/departments/'],
 ['RV-015','uiux.wavec.hr','/workforce/foundation/'],
 ['RV-015','uiux.wavec.hr','/workforce/employees/create/'],
 ['RV-017','uiux.wavec.time','/timekeeping/'],
 ['RV-017','uiux.wavec.time','/timekeeping/calendars/new/'],
 ['RV-018','uiux.wavec.payroll','/payroll/'],
 ['RV-018','uiux.wavec.payroll',`/payroll/runs/${fixtures.payroll.run}/`],
 ['RV-018','uiux.wavec.payroll','/payroll/statutory/'],
 ['RV-018','uiux.wavec.payroll','/payroll/financial-handoffs/'],
 ['RV-018','uiux.wavec.payroll','/payroll/configuration/employment/new/'],
 ['RV-028','uiux.wavec.documents',`/documents/${doc.document}/`],
 ['RV-029','uiux.wavec.hr','/workforce/employment/'],
 ['RV-030','uiux.wavec.commercial','/commercial/create/'],
 ['RV-031','uiux.wavec.controls',`/projects/${oldInput.project_a}/controls/comparison/`],
 ['RV-031','uiux.wavec.controls',`/projects/${oldInput.project_a}/controls/exceptions/`],
 ['RV-031','uiux.wavec.controls',`/projects/${oldInput.project_a}/controls/cost-reconciliation/`],
];
function credential(alias){return execFileSync('C:/Users/azera/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe',['-NoProfile','-Command',`$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/${alias}.clixml'); $c.GetNetworkCredential().Password`],{encoding:'utf8'}).trim()}
(async()=>{
 for(let attempt=0;attempt<10;attempt++){
  try { const response=await fetch(base+'/accounts/login/'); if(response.ok) break; }
  catch(error){if(attempt===9) throw error;}
  await new Promise(resolve=>setTimeout(resolve,1000));
 }
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const contexts=new Map(), records=[];
 try {
  for(const [scenario,alias,url] of targets){
   let page=contexts.get(alias);
   if(!page){
    const ctx=await browser.newContext({locale:'fa-IR',viewport:{width:1440,height:900}});
    page=await ctx.newPage(); contexts.set(alias,page);
    await page.goto(base+'/accounts/login/');
    await page.locator('[name=username]').fill(alias);
    await page.locator('[name=password]').fill(credential(alias));
    await Promise.all([page.waitForURL(u=>!u.pathname.includes('/accounts/login/')),page.locator('button[type=submit]').click()]);
   }
   await page.setViewportSize({width:1440,height:900});
   const response=await page.goto(base+url); await page.waitForLoadState('networkidle');
   const id=(delta?'delta_browser_':'browser_')+String(records.length+1).padStart(2,'0');
   const metrics=await page.evaluate(()=>({mains:document.querySelectorAll('main,[role=main]').length,headings:[...document.querySelectorAll('#main-content h1,#main-content h2')].map(e=>e.textContent.trim()),overflow:document.documentElement.scrollWidth>innerWidth,details:[...document.querySelectorAll('#main-content details')].map(e=>({summary:e.querySelector('summary')?.textContent,open:e.open})),duplicateIds:[...document.querySelectorAll('[id]')].map(e=>e.id).filter((v,i,a)=>a.indexOf(v)!==i)}));
   await page.screenshot({path:path.join(out,id+'_desktop.png'),fullPage:true});
   const focus=[]; for(let n=0;n<4;n++){await page.keyboard.press('Tab');focus.push(await page.evaluate(()=>({tag:document.activeElement.tagName,text:(document.activeElement.innerText||document.activeElement.getAttribute('aria-label')||'').slice(0,55),outline:getComputedStyle(document.activeElement).outlineStyle})));}
   await page.setViewportSize({width:390,height:844});
   await page.screenshot({path:path.join(out,id+'_mobile.png'),fullPage:true});
   const mobile=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth}));
   const interaction={};
   if(url==='/timekeeping/'){
    await page.getByText('راه‌اندازی و تنظیمات تقویم و شیفت',{exact:true}).click();
    interaction.setupExpanded=await page.getByRole('link',{name:'تقویم جدید',exact:true}).isVisible();
    await page.screenshot({path:path.join(out,id+'_mobile_setup.png'),fullPage:true});
   }
   if(url==='/workforce/employees/create/'){
    await page.locator('#main-content button[type=submit]').first().click();
    interaction.invalidRedisplay=await page.locator('[role=alert]').count();
    interaction.nativeInvalidInputs=await page.locator(':invalid').count();
    await page.screenshot({path:path.join(out,id+'_mobile_invalid.png'),fullPage:true});
   }
   records.push({scenario,actor:alias,path:url,status:response.status(),browser:browser.version(),metrics,mobile,focus,interaction,screenshots:[id+'_desktop.png',id+'_mobile.png']});
   fs.writeFileSync(path.join(out,delta?'BROWSER_DELTA.json':'BROWSER.json'),JSON.stringify(records,null,2));
  }
 } finally {await browser.close();}
 console.log('Actual Edge:',records.length,'desktop/mobile observations');
})().catch(e=>{console.error(e.message);process.exitCode=1});
