// Installed Google Chrome, isolated synthetic fixtures, real print-media PDFs.
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {basename, dirname, join, resolve} from 'node:path';
import {createServer} from 'node:net';

const [base, output] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.MVP06_SCENARIOS);
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-print-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], {stdio: 'ignore', windowsHide: true});
const pause = ms => new Promise(done => setTimeout(done, ms));
let socket;
try {
  let page;
  for (let i=0; i<100; i++) {
    try { page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p=>p.type==='page'); } catch {}
    if (page) break;
    await pause(100);
  }
  if (!page) throw Error('Installed Chrome did not start');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((done,fail)=>{socket.addEventListener('open',done,{once:true});socket.addEventListener('error',fail,{once:true});});
  let id=0, errors=[], statuses=[], external=[], failed=[];
  const pending = new Map();
  const send = (method,params={})=>new Promise((done,fail)=>{
    const next=++id;pending.set(next,{done,fail});socket.send(JSON.stringify({id:next,method,params}));
  });
  socket.addEventListener('message',event=>{
    const msg=JSON.parse(event.data);
    if (msg.method==='Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.text);
    if (msg.method==='Network.responseReceived' && msg.params.type==='Document') statuses.push(msg.params.response.status);
    if (msg.method==='Network.loadingFailed') failed.push(msg.params.errorText);
    if (msg.method==='Fetch.requestPaused') {
      const url=msg.params.request.url;
      if (url.startsWith(base+'/') || url.startsWith('data:')) {
        send('Fetch.continueRequest',{requestId:msg.params.requestId}).catch(()=>{});
      } else {
        external.push(url);
        send('Fetch.failRequest',{requestId:msg.params.requestId,errorReason:'BlockedByClient'}).catch(()=>{});
      }
    }
    if (!pending.has(msg.id)) return;
    const {done,fail}=pending.get(msg.id);pending.delete(msg.id);
    msg.error?fail(Error(msg.error.message)):done(msg.result);
  });
  const evaluate = async expression=>{
    const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  await send('Network.enable');await send('Page.enable');await send('Runtime.enable');
  await send('Fetch.enable',{patterns:[{urlPattern:'*'}]});
  await send('Network.setCookie',{name:'sessionid',value:process.env.MVP06_SESSION,url:base});
  const version=await send('Browser.getVersion');
  await mkdir(output,{recursive:true});
  const results=[];
  for (const scenario of scenarios) {
    errors=[];statuses=[];external=[];failed=[];
    await send('Emulation.setEmulatedMedia',{media:'screen'});
    await send('Emulation.setDeviceMetricsOverride',{width:scenario.mobile?390:1440,height:1000,deviceScaleFactor:1,mobile:!!scenario.mobile});
    await send('Page.navigate',{url:new URL(scenario.path,base).href});
    for (let i=0;i<200;i++) {
      await pause(75);
      if (await evaluate(`document.readyState==='complete' && location.pathname===${JSON.stringify(scenario.path.split('?')[0])}`) && statuses.length) break;
    }
    if (statuses.at(-1)!==200) throw Error(scenario.name+': source status '+statuses);
    const entry=await evaluate(`!!document.querySelector('[data-print-preview]')`);
    if (!entry) throw Error(scenario.name+': missing source print action');
    await evaluate(`document.querySelector('[data-print-preview]').click()`);
    for (let i=0;i<200;i++) {
      await pause(75);
      if (await evaluate(`document.readyState==='complete' && !!document.querySelector('.print-document')`)) break;
    }
    await evaluate('document.fonts.ready');
    if (!await evaluate(`document.fonts.check('12px Vazirmatn')`)) throw Error('Persian font not loaded');
    const screen=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,back:document.querySelector('.print-toolbar a').getAttribute('href'),href:location.href})`);
    if (screen.scroll>screen.width+2) throw Error(scenario.name+': screen overflow '+JSON.stringify(screen));
    // Verify the real toolbar handler without opening a headless native dialog.
    await evaluate(`window.print=()=>{window.__printRequested=true};document.querySelector('[data-print-document]').click()`);
    await pause(50);
    if (!await evaluate('window.__printRequested===true')) throw Error(scenario.name+': print action failed');
    const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
    await writeFile(join(output,scenario.name+'-screen.png'),Buffer.from(screenshot.data,'base64'));
    await send('Emulation.setDeviceMetricsOverride',{width:794,height:1123,deviceScaleFactor:1,mobile:false});
    await send('Emulation.setEmulatedMedia',{media:'print'});
    const state=await evaluate(`({rtl:document.documentElement.dir,toolbar:getComputedStyle(document.querySelector('.print-toolbar')).display,footer:getComputedStyle(document.querySelector('.print-footer')).display,nav:document.querySelectorAll('nav,[data-module-selector],aside').length,overflow:[...document.querySelectorAll('table,td,th,p,dd,bdi')].filter(e=>e.scrollWidth>e.clientWidth+2&&e.clientWidth>0).map(e=>e.tagName),font:document.fonts.check('12px Vazirmatn'),tables:document.querySelectorAll('table').length,rows:document.querySelectorAll('tbody tr').length,text:document.querySelector('h1').innerText})`);
    if (state.rtl!=='rtl'||state.toolbar!=='none'||state.footer!=='none'||state.nav||state.overflow.length||!state.font) throw Error(scenario.name+': print state '+JSON.stringify(state));
    const pdf=await send('Page.printToPDF',{printBackground:false,preferCSSPageSize:true,displayHeaderFooter:false});
    const bytes=Buffer.from(pdf.data,'base64');
    if (!bytes.subarray(0,5).equals(Buffer.from('%PDF-'))) throw Error('Invalid PDF');
    await writeFile(join(output,scenario.name+'.pdf'),bytes);
    if (errors.length||external.length||failed.length) throw Error(scenario.name+': '+JSON.stringify({errors,external,failed}));
    results.push({name:scenario.name,screen,state,pdfBytes:bytes.length,external,errors,failed});
  }
  await writeFile(join(output,'results.json'),JSON.stringify({chrome:version.product,results},null,2));
  process.stdout.write(JSON.stringify(results));
} finally {
  socket?.close();chrome.kill();await pause(400);
  const resolvedProfile=resolve(profile);
  if(dirname(resolvedProfile)!==resolve(tmpdir()) || !basename(resolvedProfile).startsWith('bonira-print-')) throw Error('Refusing profile cleanup outside the owned temporary directory');
  await rm(resolvedProfile,{recursive:true,force:true}).catch(()=>{});
}
