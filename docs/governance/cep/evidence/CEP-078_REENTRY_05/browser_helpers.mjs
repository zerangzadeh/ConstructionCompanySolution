import * as fs from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
const root='E:/Construction_Company_Solution/docs/governance/cep/evidence/CEP-078_REENTRY_05/';
export const records=[];
export const active={Chrome:'cep078.synthetic.operations',Edge:'uiux.audit.reporting'};
export const save=async(n,v)=>fs.writeFile(root+n,JSON.stringify(v,null,2));
export async function sign(f,t,vp,alias){
 if(active[f]===alias)return;
 await vp.set({width:1440,height:900});
 if((await t.url()).includes('/admin/login/')){await t.goto('http://127.0.0.1:8000/');await t.getAXState({emit:false});}
 if(!await t.playwright.locator('#id_username').count()){
  await t.playwright.locator('aside form[action*="logout"] button').click();
  await t.playwright.waitForURL('http://127.0.0.1:8000/accounts/login/',{timeoutMs:15000});await t.getAXState({emit:false});
 }
 let secret=execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',"$a=[Console]::In.ReadToEnd(); $p=Join-Path $env:LOCALAPPDATA ('BONIRA/UIUXRuntimeAudit/credentials/'+$a+'.clixml'); (Import-Clixml -LiteralPath $p).GetNetworkCredential().Password"],{input:alias,encoding:'utf8'}).trim();
 await t.playwright.locator('#id_username').fill(alias);await t.playwright.locator('#id_password').fill(secret);secret=null;
 await t.playwright.getByRole('button',{name:'ورود به سامانه',exact:true}).click();
 await t.playwright.waitForURL('http://127.0.0.1:8000/',{timeoutMs:15000});await t.getAXState({emit:false});
 active[f]=alias;await save('AUTHENTICATION.json',{at:new Date().toISOString(),active,method:'Normal public existing-credential login; no reset, staff change or session injection'});
}
export async function record(id,f,t,checks,details={},capture=false){
 const viewport=await t.playwright.evaluate(()=>[innerWidth,innerHeight]);
 const r={id,family:f,at:new Date().toISOString(),actor:active[f],viewport,url:await t.url(),checks,details,result:Object.values(checks).every(Boolean)?'PASS':'FAIL'};
 if(capture){r.capture=id+'_'+f+'_'+viewport[0]+'.jpg';await fs.writeFile(root+r.capture,await t.getScreenshot({emit:false}));}
 records.push(r);await save('RUNTIME_RESULTS.json',records);return {id,family:f,viewport,result:r.result,failed:Object.keys(checks).filter(k=>!checks[k])};
}
export async function artifact(name,t){await fs.writeFile(root+name,await t.getAXState({emit:false}));}
