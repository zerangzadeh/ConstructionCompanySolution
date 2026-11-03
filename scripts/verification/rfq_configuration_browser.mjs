// Installed Chrome; isolated Django test data. No browser automation dependency.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { createServer } from 'node:net';

const [base, output] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.RFQ_UX_SCENARIOS);
const sessions=JSON.parse(process.env.RFQ_UX_SESSIONS);
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-rfq-ux-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-component-update',
  '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true });
let socket, inspectFailure;
const results = [];
const offlineProof = [];
let requests = [], failures = [], errors = [], consoleErrors = [], external = [], posts = [], logErrors = [];
try {
  let page;
  for (let i = 0; i < 100; i++) {
    try { page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p => p.type === 'page'); } catch {}
    if (page) break;
    await new Promise(done => setTimeout(done, 100));
  }
  if (!page) throw new Error('Installed Chrome unavailable');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((done, fail) => { socket.addEventListener('open', done); socket.addEventListener('error', fail); });
  let id = 0;
  const pending = new Map();
  const requestURLs = new Map();
  const send = (method, params = {}) => new Promise((done, fail) => {
    const next = ++id;
    const timer = setTimeout(() => { pending.delete(next); fail(new Error('CDP timeout: ' + method)); }, 30000);
    pending.set(next, { done, fail, timer });
    socket.send(JSON.stringify({ id: next, method, params }));
  });
  socket.addEventListener('message', event => {
    const m = JSON.parse(event.data), p = m.params;
    if (m.method === 'Fetch.requestPaused') {
      const url = new URL(p.request.url);
      const local = url.origin === new URL(base).origin;
      if (!local) external.push({ url: p.request.url, type: p.resourceType, blocked: true });
      const permitted = local;
      send(permitted ? 'Fetch.continueRequest' : 'Fetch.failRequest', permitted
        ? { requestId: p.requestId } : { requestId: p.requestId, errorReason: 'BlockedByClient' }).catch(() => {});
    }
    if (m.method === 'Network.responseReceived') requests.push({ url: p.response.url, type: p.type, status: p.response.status, cached: !!p.response.fromDiskCache });
    if (m.method === 'Network.requestWillBeSent') {requestURLs.set(p.requestId,p.request.url); if (p.request.method === 'POST') posts.push({url:p.request.url, method:p.request.method});}
    if (m.method === 'Network.loadingFailed') failures.push({ url:requestURLs.get(p.requestId),type:p.type,error:p.errorText,blocked:p.blockedReason,canceled:!!p.canceled });
    if (m.method === 'Log.entryAdded' && p.entry.level==='error') logErrors.push({source:p.entry.source,url:p.entry.url,text:p.entry.text});
    if (m.method === 'Runtime.exceptionThrown') errors.push(p.exceptionDetails.exception?.description || p.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && p.type === 'error') consoleErrors.push(p.args.map(a => a.value || a.description).join(' '));
    if (!pending.has(m.id)) return;
    const task = pending.get(m.id); pending.delete(m.id); clearTimeout(task.timer);
    if (m.error) task.fail(new Error(m.error.message)); else task.done(m.result);
  });
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
  };
  const waitFor = async expression => {
    for (let i = 0; i < 200; i++) {
      if (await evaluate(expression)) return;
      await new Promise(done => setTimeout(done, 100));
    }
    throw new Error('Page did not settle: ' + expression);
  };
  const click = async selector => {
    if (selector.startsWith('.swal2-')) {
      await waitFor('window.Swal?.isVisible() && Number(getComputedStyle(Swal.getPopup()).opacity)===1 && Swal.getPopup().getAnimations().every(a=>a.playState!=="running")');
      await evaluate('new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(()=>done(true))))');
    }
    const point = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing '+${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    await send('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...point});
    await send('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...point});
  };
  await mkdir(output, { recursive: true });
  let loads=0; socket.addEventListener('message',e=>{if(JSON.parse(e.data).method==='Page.loadEventFired')loads++;});
  await send('Network.enable'); await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Network.setBypassServiceWorker', { bypass: true });
  await send('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] });
  const version = await send('Browser.getVersion');
  const blocked = await evaluate(`fetch('https://offline-proof.invalid/f4').then(()=>false,()=>true)`);
  offlineProof.push({ blocked, requests: external, failures });
  if (!blocked || !external.some(r => r.blocked)) throw new Error('External blocking negative control failed');
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const shot = async name => {
    // Capture the settled dialog, rather than its opening opacity animation.
    await evaluate('Promise.all((window.Swal?.getPopup()?.getAnimations() || []).map(a=>a.finished.catch(()=>{}))).then(()=>true)');
    await waitFor('!window.Swal?.isVisible() || (Number(getComputedStyle(Swal.getPopup()).opacity)===1 && Swal.getPopup().getAnimations().every(a=>a.playState!=="running"))');
    const result = await send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
    await writeFile(join(output, name + '.png'), Buffer.from(result.data, 'base64'));
  };
  const settled = async () => {
    await waitFor("document.readyState==='complete'");
    await evaluate('document.fonts.ready.then(()=>true)');
    if (await evaluate('!!window.Swal?.isVisible()')) {
      await evaluate('Swal.close()'); await waitFor('!Swal.isVisible()');
    }
  };
  const navigate = async path => {
    const before=loads; await send('Page.navigate',{url:base+path});
    for(let i=0;loads<=before && i<200;i++)await new Promise(r=>setTimeout(r,100));
    assert(loads>before,'Navigation load');await settled();
  };
  const submit = async selector => {
    const before=loads;await click(selector);
    for(let i=0;loads<=before && i<200;i++)await new Promise(r=>setTimeout(r,100));
    assert(loads>before,'Form navigation');await settled();
  };
  const fill = async values => evaluate(`(() => {for(const [name,value] of Object.entries(${JSON.stringify(values)})){const e=document.querySelector('main [name="'+name+'"]');if(!e)throw Error('Missing '+name);if(e.type==='checkbox')e.checked=value;else e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));}return true;})()`);
  const layout = async () => {
    const state=await evaluate(`(() => {const main=document.querySelector('main');return {viewport:innerWidth,width:document.documentElement.scrollWidth,rtl:document.documentElement.dir,text:main.innerText,external:[...document.querySelectorAll('script[src],link[rel=stylesheet]')].map(e=>e.src||e.href).filter(u=>new URL(u).origin!==location.origin),inputs:[...main.querySelectorAll('input[type=number]')].map(e=>({name:e.name,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height})),classes:[...new Set([...main.querySelectorAll('[class]')].flatMap(e=>[...e.classList]))]};})()`);
    assert(state.width<=state.viewport,'No page overflow '+JSON.stringify({width:state.width,viewport:state.viewport}));
    assert(state.rtl==='rtl','RTL');assert(!state.external.length,'Local runtime assets only');
    assert(!/Commercial Scope|Scope Code|Scope Type|تعریف صریح دامنه خرید|مقدار حاکم بسته|دامنه ثبت‌شده|source_fingerprint|RFQCommercialScope|[a-f0-9]{8}-[a-f0-9]{4}-/i.test(state.text),'No technical leakage');
    assert(state.inputs.every(e=>e.width>=75 && e.height>=38),'Usable numeric controls '+JSON.stringify(state.inputs));
    state.text=state.text.slice(0,300);return state;
  };
  const capture = async name => {
    await evaluate('window.scrollTo(0,0)');await shot(name+'-top');
    await evaluate("document.querySelector('#supplier-selection,.rfq-config__group-form')?.scrollIntoView({block:'start'})");
    await shot(name+'-configuration');
  };
  inspectFailure=async()=>{await shot('failure');return evaluate("({path:location.pathname,text:document.querySelector('main')?.innerText})");};
  for (const scenario of scenarios) {
    requests=[]; failures=[]; errors=[]; consoleErrors=[]; external=[]; posts=[];logErrors=[];
    await send('Network.clearBrowserCookies');
    await send('Network.setCookie',{name:'sessionid',value:sessions[scenario.actor],url:base,httpOnly:true,sameSite:'Lax'});
    await send('Emulation.setDeviceMetricsOverride',{width:scenario.width,height:1000,deviceScaleFactor:1,mobile:false});
    await navigate(scenario.path);
    let state;
    if(scenario.kind==='denied') {
      assert(requests.some(r=>r.type==='Document' && r.status===404),'Project/tenant denial');
      assert(!await evaluate("!!document.querySelector('[data-item-configuration]')"),'No unauthorized form');
      await shot(scenario.name);results.push({name:scenario.name,requests,errors});continue;
    }
    state=await layout();await capture(scenario.name+'-before');
    if(scenario.kind==='readonly') {
      assert(!await evaluate("!!document.querySelector('[data-item-configuration]') || !!document.querySelector('[data-scope-define]')"),'Read-only viewer');
    } else if(scenario.kind==='missing') {
      await fill({supplier_ids:true});
      await submit('form[action$="/issue/"] button');
      assert(await evaluate("document.querySelector('main').innerText.includes('تأیید و ذخیره کنید')"),'Explicit issue prerequisite');
      assert(requests.some(r=>r.type==='Document' && r.status===400),'Issue fails without definition');
      await capture(scenario.name+'-blocked');
    } else if(scenario.kind==='group') {
      await click('[data-scope-define]');await waitFor("document.readyState==='complete' && !!document.querySelector('[name=selection_ui]')");await settled();
      assert(await evaluate("[...document.querySelectorAll('[name^=member_]')].map(e=>Number(e.value)).join(',')==='120,8500,500'"),'Group member quantities prefilled');
      await fill({scope_code:'گروه خرید فونداسیون',required_quantity:'1',unit_of_measure:scenario.unit,
        select_0:true,select_1:true,select_2:true,independently_awardable:'no',allows_split_award:'yes',allows_alternates:'yes'});
      await layout();await capture(scenario.name+'-group');
      await submit('button[name=operation][value=append]');
      await navigate(scenario.path);
      assert(await evaluate("!document.querySelector('[data-item-configuration]') && document.querySelector('main').innerText.includes('گروه خرید فونداسیون')"),'Group-only config without inferred independent lines');
      await capture(scenario.name+'-saved');
    } else {
      assert(await evaluate(`document.querySelectorAll('[data-item-configuration] tbody tr').length===${scenario.count}`),'Existing RFQ rows');
      assert(!await evaluate("!!document.querySelector('[data-item-configuration] [name=scope_code], [data-item-configuration] [name=unit_of_measure]')"),'No duplicate identity/unit fields');
      if(scenario.kind==='validation') {
        await fill({quantity_0:'121',independently_awardable_0:'no',allows_split_award_0:'yes'});
        await submit('[data-item-configuration] button[name=operation]');
        assert(await evaluate("!!document.querySelector('#id_quantity_0-errors') && !!document.querySelector('#id_allows_split_award_0-errors') && document.querySelector('[name=quantity_0]').value==='121'"),'Field errors and retained input');
        await capture('validation-errors');await fill({quantity_0:'3.25',independently_awardable_0:'yes',allows_split_award_0:'no'});
      }
      if(['partial','saved'].includes(scenario.kind))await fill({quantity_0:'3.25'});
      if(['split','alternate'].includes(scenario.kind)) {
        await click('.rfq-config__advanced summary');
        await fill({[scenario.kind==='split'?'allows_split_award_0':'allows_alternates_0']:'yes'});
      }
      await submit('[data-item-configuration] button[name=operation]');
      assert(await evaluate("document.querySelector('main').innerText.includes('تنظیمات نسخه جاری ثبت شده است')"),'Explicit confirmation saved');
      if(scenario.kind==='saved') {
        await click('.rfq-config__history summary');
        assert(await evaluate("/[5۵] متر مکعب/.test(document.querySelector('.rfq-config__history').innerText)"),'Previous quantity available');
      }
      await layout();await capture(scenario.name+'-saved');
      if(scenario.kind==='issue') {
        await submit('form[action$="/submit/"] button');await fill({supplier_ids:true});
        await submit('form[action$="/issue/"] button');
        assert(await evaluate("!document.querySelector('[data-item-configuration]') && document.querySelector('main').innerText.includes('تنظیمات نسخه جاری')"),'Issued configuration read-only');
        await capture('issued');
      }
      await navigate(scenario.path); // GET/reload must never persist another revision.
    }
    const final=await layout();
    const expected400=['validation','missing'].includes(scenario.kind);
    const bad=requests.filter(r=>r.status>=400 && !(r.url.endsWith('/favicon.ico') && r.status===404) && !(expected400 && r.type==='Document' && r.status===400));
    const badLogs=logErrors.filter(e=>!(e.source==='network' && e.url && (e.url.endsWith('/favicon.ico') || (expected400 && requests.some(r=>r.url===e.url && r.status===400)))));
    assert(!bad.length && !failures.length,'No unexpected HTTP or asset failure '+JSON.stringify({bad,failures}));
    assert(!errors.length && !consoleErrors.length && !external.length && !badLogs.length,'No JS/console/external errors '+JSON.stringify({errors,consoleErrors,external,badLogs}));
    results.push({name:scenario.name,width:scenario.width,state,final,requests,posts,errors,consoleErrors,external,logErrors});
  }
  await writeFile(join(output,'results.json'),JSON.stringify({version,offlineProof,results},null,2));
  process.stdout.write(JSON.stringify({pages:results.length,chrome:version.product}));
}catch(error){
  await mkdir(output,{recursive:true});let dom;
  try{dom=await inspectFailure?.();}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({error:error.stack,completed:results.length,results,requests,failures,logErrors,errors,consoleErrors,external,posts,dom},null,2));
  throw error;
}finally{
  socket?.close();chrome.kill();await new Promise(done=>chrome.once('exit',done));
  if(!resolve(profile).startsWith(resolve(tmpdir())+sep) || !profile.includes('bonira-rfq-ux-'))throw new Error('Unsafe temporary profile path');
  await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
