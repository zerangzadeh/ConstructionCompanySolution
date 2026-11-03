// Real installed Chrome: click downloads, verify completion and retain UI captures.
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve, relative} from 'node:path';
import {createServer} from 'node:net';

const [base, output] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.MVP07_SCENARIOS);
const server = createServer();
await new Promise(done => server.listen(0,'127.0.0.1',done));
const port = server.address().port;
await new Promise(done=>server.close(done));
const profile = await mkdtemp(join(tmpdir(),'bonira-xlsx-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',[
  '--headless=new','--no-first-run','--no-default-browser-check',
  `--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,'about:blank',
],{stdio:'ignore',windowsHide:true});
let socket;
const pause=ms=>new Promise(done=>setTimeout(done,ms));
try {
  let page;
  for(let i=0;i<100;i++) {
    try { page=(await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p=>p.type==='page'); } catch {}
    if(page) break;
    await pause(100);
  }
  if(!page) throw Error('Installed Chrome did not start');
  socket=new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((done,fail)=>{socket.addEventListener('open',done,{once:true});socket.addEventListener('error',fail,{once:true});});
  let id=0, errors=[], statuses=[], downloads=[];
  const pending=new Map();
  socket.addEventListener('message',event=>{
    const msg=JSON.parse(event.data);
    if(msg.method==='Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.text);
    if(msg.method==='Network.responseReceived' && msg.params.type==='Document') statuses.push(msg.params.response.status);
    if(msg.method==='Browser.downloadWillBegin') downloads.push({...msg.params,state:'starting'});
    if(msg.method==='Browser.downloadProgress') {
      const entry=downloads.find(d=>d.guid===msg.params.guid);
      if(entry) Object.assign(entry,msg.params);
    }
    if(!pending.has(msg.id)) return;
    const {done,fail}=pending.get(msg.id);pending.delete(msg.id);
    msg.error?fail(Error(msg.error.message)):done(msg.result);
  });
  const send=(method,params={})=>new Promise((done,fail)=>{const next=++id;pending.set(next,{done,fail});socket.send(JSON.stringify({id:next,method,params}));});
  const evaluate=async expression=>{
    const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  await send('Network.enable');await send('Page.enable');await send('Runtime.enable');
  await send('Network.setCookie',{name:'sessionid',value:process.env.MVP07_SESSION,url:base});
  await mkdir(output,{recursive:true});
  const results=[];
  for(const scenario of scenarios) {
    errors=[];statuses=[];downloads=[];
    const directory=await mkdtemp(join(resolve(output),scenario.name+'-'));
    await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:directory,eventsEnabled:true});
    await send('Network.setBlockedURLs',{urls:['https://*','http://cdn.*']});
    await send('Emulation.setDeviceMetricsOverride',{width:scenario.width||1440,height:900,deviceScaleFactor:1,mobile:scenario.width===390});
    await send('Page.navigate',{url:new URL(scenario.path,base).href});
    let ready=false;
    for(let i=0;i<200;i++) {
      await pause(100);
      ready=await evaluate(`document.readyState==='complete' && location.pathname===${JSON.stringify(scenario.path.split('?')[0])}`);
      if(ready && statuses.length) break;
    }
    if(!ready||statuses.at(-1)!==(scenario.status||200)) throw Error(scenario.name+': status '+statuses);
    const state=await evaluate(`({dir:document.documentElement.dir,width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,button:!!document.querySelector('[data-xlsx-export]'),href:document.querySelector('[data-xlsx-export]')?.href,bodyText:document.body.innerText,drawer:!!document.querySelector('[data-module-selector]'),assets:[...document.scripts].map(s=>s.src).filter(Boolean)})`);
    const actionCount=await evaluate('document.querySelectorAll("[data-xlsx-export]").length');
    if(!scenario.observeOnly && actionCount!==(scenario.status===403?0:1)) throw Error(scenario.name+': expected one export action, found '+actionCount);
    if(scenario.status!==403 && !scenario.observeOnly) {
      if(state.dir!=='rtl'||state.scroll>state.width+2) throw Error(scenario.name+': RTL/overflow');
      const before=await evaluate('location.href');
      const rect=await evaluate(`(()=>{const a=document.querySelector('[data-xlsx-export]');a.scrollIntoView({block:'center'});const r=a.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...rect});
      await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...rect});
      for(let i=0;i<300 && !downloads.some(d=>d.state==='completed');i++) await pause(100);
      if(downloads.length!==1||downloads[0].state!=='completed'||!downloads[0].suggestedFilename.endsWith('.xlsx')) throw Error(scenario.name+': download '+JSON.stringify(downloads));
      if(await evaluate('location.href')!==before) throw Error('Download replaced current page');
      if(!await evaluate("!!document.querySelector('[data-xlsx-export]') && !!document.querySelector('main')")) throw Error('Page unusable');
    }
    const visibleText=await evaluate('document.body.innerText');
    await writeFile(join(directory,'visible.txt'),visibleText,'utf8');
    const beforeShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(join(directory,'page.png'),Buffer.from(beforeShot.data,'base64'));
    if(scenario.clearFilters) await writeFile(join(directory,'filtered-empty.png'),Buffer.from(beforeShot.data,'base64'));
    const normalizedText=visibleText.replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
    if(scenario.contains && !normalizedText.includes(scenario.contains)) throw Error(scenario.name+': expected visible '+scenario.contains);
    if(scenario.excludes && visibleText.includes(scenario.excludes)) throw Error(scenario.name+': obsolete visible '+scenario.excludes);
    if(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-/.test(visibleText)) throw Error(scenario.name+': UUID leakage');
    if(scenario.status!==403 && (state.dir!=='rtl'||state.scroll>state.width+2)) throw Error(scenario.name+': RTL/overflow');
    if(errors.length) throw Error(scenario.name+': JavaScript '+JSON.stringify(errors));
    if(scenario.headerCheck) {
      state.headers=await evaluate('[...document.querySelectorAll("main table thead tr:first-child th")].map(e=>e.textContent.trim())');
      if(scenario.headerCheck==='before' && state.headers.at(-1)!=='') throw Error('Expected current unlabeled action column');
      if(scenario.headerCheck==='after' && !state.headers.at(-1)?.includes('اقدام')) throw Error('Missing action column label');
      await evaluate('document.querySelector("main table thead tr:first-child th:last-child").scrollIntoView({block:"nearest",inline:"nearest"})');
      const actionShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await writeFile(join(directory,'action-column.png'),Buffer.from(actionShot.data,'base64'));
    }
    if(scenario.clearFilters) {
      const point=await evaluate(`(()=>{const a=document.querySelector('[data-empty-clear-filters]');if(!a)throw Error('Missing clear filters');a.scrollIntoView({block:'center'});const r=a.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
      await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
      let restored=false;
      for(let i=0;i<100;i++) {await pause(100);restored=await evaluate("document.readyState==='complete' && !location.search && document.body.innerText.includes('جرثقیل نمونه') && !document.querySelector('[data-empty-clear-filters]')");if(restored)break;}
      if(!restored)throw Error('Clear filters failed to restore authorized existing record');
      state.clearFiltersRestored=true;
      const restoredShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await writeFile(join(directory,'filters-cleared.png'),Buffer.from(restoredShot.data,'base64'));
    }
    const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(join(directory,'page.png'),Buffer.from(shot.data,'base64'));
    const safeDownloads=downloads.map(({suggestedFilename,state,totalBytes})=>({filename:join(directory,suggestedFilename),state,totalBytes}));
    results.push({name:scenario.name,width:scenario.width||1440,status:statuses.at(-1),state,downloads:safeDownloads,jsErrors:errors});
  }
  await writeFile(join(output,'results.json'),JSON.stringify(results,null,2));
  process.stdout.write(JSON.stringify(results));
} finally {
  if(socket) socket.close();chrome.kill();await pause(350);
  const relativeProfile=relative(resolve(tmpdir()),resolve(profile));
  if(relativeProfile && !relativeProfile.startsWith('..') && !relativeProfile.includes(':')) {
    await rm(resolve(profile),{recursive:true,force:true}).catch(()=>{});
  }
}
