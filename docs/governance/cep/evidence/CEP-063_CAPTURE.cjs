const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');
(async()=>{
 const base=path.resolve('docs/governance/cep/evidence/CEP-063_UI'); const profileRoot=path.resolve('.pytest_cache/bonira-cep063-browser'); await fs.mkdir(profileRoot,{recursive:true}); const profile=await fs.mkdtemp(path.join(profileRoot,'chrome-cdp-'));
 const proc=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-sandbox','--remote-debugging-port=0','--user-data-dir='+profile,'--allow-file-access-from-files',pathToFileURL(path.join(base,'ready-render.html')).href],{windowsHide:true,stdio:'ignore'});
 let ws;
 try {
  let port;
  for(let i=0;i<100;i++){try{port=(await fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}catch{await new Promise(r=>setTimeout(r,100));}}
  const pages=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  let next=0; const pending=new Map();
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const {resolve,reject}=pending.get(m.id);pending.delete(m.id);m.error?reject(m.error):resolve(m.result);}};
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  await send('Page.enable');
  const records=[];
  for (const name of ['ready','timesheet','form','empty','error','unauthorized']) {
   for (const [label,width,height] of [['desktop',1366,1000],['mobile',390,900]]) {
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<500});
    await send('Page.navigate',{url:pathToFileURL(path.join(base,name+'-render.html')).href});
    for(let i=0;i<80;i++){const r=await send('Runtime.evaluate',{expression:'document.readyState === "complete" && Boolean(document.querySelector("main"))',returnByValue:true});if(r.result.value)break;await new Promise(r=>setTimeout(r,100));}
    await new Promise(r=>setTimeout(r,700));
    const metrics=await send('Runtime.evaluate',{expression:'JSON.stringify({width:innerWidth,document:document.documentElement.scrollWidth,main:document.querySelector("main")?.getBoundingClientRect().width,rtl:document.documentElement.dir,fonts:document.fonts.status})',returnByValue:true});
    const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await fs.writeFile(path.resolve('docs/governance/cep/evidence/CEP-063_'+name+'_'+label+'.png'),Buffer.from(screenshot.data,'base64'));
    records.push({name,label,...JSON.parse(metrics.result.value)});
   }
  }
  await fs.writeFile(path.resolve('docs/governance/cep/evidence/CEP-063_BROWSER.json'),JSON.stringify(records,null,2));
  console.log(JSON.stringify(records));
  await send('Browser.close');
 }finally{if(ws && ws.readyState===1){ws.send(JSON.stringify({id:9999,method:"Browser.close"}));ws.close();} if(proc.exitCode===null)proc.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
