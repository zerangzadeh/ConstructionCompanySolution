// Installed Chrome; isolated Django test data. No browser automation dependency.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { createServer } from 'node:net';

const [base, output] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.PR_UIUX_SCENARIOS);
const sessions=JSON.parse(process.env.PR_UIUX_SESSIONS);
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-pr-uiux-'));
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
  const key = async (name, modifiers=0) => {
    const codes={Tab:9,Escape:27};
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:name,code:name,windowsVirtualKeyCode:codes[name],modifiers});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:name,code:name,windowsVirtualKeyCode:codes[name],modifiers});
  };
  const open = async () => {
    await click('[data-module-trigger]');
    await waitFor('document.querySelector("#erp-module-selector").open && document.querySelector("#erp-module-selector").getAnimations().every(a=>a.playState!=="running") && Math.abs(document.querySelector("#erp-module-selector").getBoundingClientRect().top)<1');
    await evaluate('new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(()=>done(true))))');
  };
  const closed = async () => {
    await waitFor('!document.querySelector("#erp-module-selector").open && document.activeElement===document.querySelector("[data-module-trigger]") && document.querySelector("[data-module-trigger]").getAttribute("aria-expanded")==="false" && !document.documentElement.classList.contains("erp-module-selector-open")');
  };
  inspectFailure=async()=>{
    const dom=await evaluate(`({path:location.pathname,ready:document.readyState,drawer:document.querySelector('#erp-module-selector')?.open,swal:!!window.Swal?.isVisible(),focus:document.activeElement?.outerHTML.slice(0,250)})`);
    await shot('failure');return dom;
  };
  const settled = async () => {
    await waitFor("document.readyState==='complete'");
    await evaluate('document.fonts.ready.then(()=>true)');
    if(await evaluate('!!window.Swal?.isVisible()')) {
      await evaluate('Swal.close()');
      await waitFor('!Swal.isVisible()');
    }
  };
  const capture = async name => {
    await evaluate('window.scrollTo(0,0)'); await shot(name);
    const {cssContentSize:size}=await send('Page.getLayoutMetrics');
    const result=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:size.width,height:size.height,scale:1}});
    await writeFile(join(output,name+'-full.png'),Buffer.from(result.data,'base64'));
  };
  const inspectLayout = async () => {
    const state=await evaluate(`(() => ({
      width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
      dir:document.documentElement.dir,font:document.fonts.check('14px Vazirmatn'),
      classes:[...new Set([...document.body.querySelectorAll('*')].flatMap(e=>[...e.classList]))],
      texts:document.querySelector('main').innerText,
      metrics:document.querySelectorAll('.pr-detail__metric').length,
      tokenPrimary:getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
      iconBackground:getComputedStyle(document.querySelector('.pr-detail__icon')).backgroundColor,
      guidanceBorder:getComputedStyle(document.querySelector('.pr-detail__guidance')).borderInlineStartWidth,
      relatedBadgeWidth:document.querySelector('.pr-detail__related .erp-badge')?.getBoundingClientRect().width,
      grid:getComputedStyle(document.querySelector('.pr-detail__summary')).gridTemplateColumns,
      itemGrid:getComputedStyle(document.querySelector('.pr-detail__items-layout')).gridTemplateColumns,
      table:document.querySelector('.pr-detail__table')?.getBoundingClientRect().width,
      tableWrap:document.querySelector('.pr-detail__table-inset .erp-table-wrap')?.clientWidth,
      nativeNames:[...document.querySelectorAll('main select')].map(e=>({name:e.name,enhanced:!!e.tomselect})),
      foundation:[...document.querySelectorAll('link[href$="/static/css/tailwind.css"]')].map(e=>({rules:e.sheet?.cssRules.length,media:e.media,onload:e.getAttribute('onload')})),
      foundationLast:document.head.querySelector('link[href$="/static/css/tailwind.css"]')===[...document.head.querySelectorAll('style,link[rel=stylesheet]')].at(-1),
    }))()`);
    assert(state.width+1>=state.scroll && state.dir==='rtl' && state.font,'RTL/font/no page overflow');
    assert(state.metrics===4,'Four compact summary metrics');
    assert(state.tokenPrimary && state.iconBackground!=='rgba(0, 0, 0, 0)' && state.guidanceBorder==='3px','Existing canonical token styles actually resolve');
    assert(!state.relatedBadgeWidth || state.relatedBadgeWidth<150,'Related RFQ keeps compact shared status badge');
    assert(!/UUID|object \(|purchase_requests\.|RFQCommercialScope|[a-f0-9]{8}-[a-f0-9]{4}-/i.test(state.texts),'No technical leakage');
    assert(state.foundation.length===1 && state.foundation[0].rules>0 && !state.foundation[0].media && !state.foundation[0].onload && state.foundationLast,'Preserved local Tailwind');
    return state;
  };
  const confirm = async (selector, expected, cancelFirst=false) => {
    const before=posts.length;
    await click(selector);await waitFor('Swal.isVisible()');
    assert(await evaluate('document.activeElement===Swal.getCancelButton() && getComputedStyle(Swal.getPopup()).direction==="rtl" && Swal.getPopup().getBoundingClientRect().width<=innerWidth'),'Safe focused RTL confirmation fits');
    assert(posts.length===before,'Confirmation has not posted');
    if(cancelFirst){
      await shot(expected+'-confirmation'); await click('.swal2-cancel');await waitFor('!Swal.isVisible()');
      assert(posts.length===before,'Dismissal sends no POST');
      await click(selector);await waitFor('Swal.isVisible()');
      await key('Escape');await waitFor('!Swal.isVisible()');
      assert(posts.length===before,'Escape sends no POST');
      await click(selector);await waitFor('Swal.isVisible()');
    }
    await click('.swal2-confirm');
    await waitFor(`document.readyState==='complete' && document.querySelector('[data-pr-state]')?.dataset.prState===${JSON.stringify(expected.split('-')[0])}`);
    await settled();assert(posts.length===before+1,'Exactly one existing action POST');
  };
  // Inspect read-only actors before the owner advances the same synthetic records.
  const orderedScenarios = [...scenarios.filter(s=>s.actor==='viewer'), ...scenarios.filter(s=>s.actor!=='viewer')];
  for(const scenario of orderedScenarios){
    requests=[];failures=[];errors=[];consoleErrors=[];external=[];posts=[];logErrors=[];
    await send('Network.clearBrowserCookies');
    await send('Network.setCookie',{name:'sessionid',value:sessions[scenario.actor],url:base});
    await send('Emulation.setDeviceMetricsOverride',{width:scenario.width,height:900,deviceScaleFactor:1,mobile:scenario.width===390});
    await send('Page.navigate',{url:base+scenario.path});
    await waitFor(`location.pathname===${JSON.stringify(scenario.path)} && document.readyState==='complete'`);
    await settled();
    if(scenario.denied){
      assert(!await evaluate("!!document.querySelector('[data-pr-state]')"),'No inaccessible record shown');
      assert(requests.some(r=>r.type==='Document' && r.status===404),'Scope denial is 404');
      await capture(scenario.name);
      assert(!errors.length && !consoleErrors.length && !external.length,'Denied route has no JS/external failures');
      results.push({name:scenario.name,state:{classes:[]},requests,errors,posts});continue;
    }
    const state=await inspectLayout();
    assert(await evaluate(`document.querySelector('[data-pr-state]').dataset.prState===${JSON.stringify(scenario.state)}`),'Requested lifecycle state is actually rendered');
    await capture(scenario.name);
    if(scenario.actor==='viewer'){
      assert(await evaluate("!document.querySelector('main form[action*=\"/requests/\"]') && !document.querySelector('[data-pr-rfq]')"),'Viewer has no mutation/handoff actions');
      assert(!errors.length && !consoleErrors.length && !external.length,'Read-only route has no JS/external failures');
      results.push({name:scenario.name,state,requests,errors,posts});continue;
    }
    if(scenario.width===390){
      const point=await evaluate(`(()=>{const e=document.querySelector('.pr-detail__table-inset .erp-table-wrap');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await send('Input.dispatchMouseEvent',{type:'mouseWheel',...point,deltaX:-260,deltaY:0});
      await waitFor("Math.abs(document.querySelector('.pr-detail__table-inset .erp-table-wrap').scrollLeft)>20");
      await shot(scenario.name+'-table-scroll');
      await evaluate("document.querySelector('.pr-detail__table-inset .erp-table-wrap').scrollLeft=0");
    }
    // Same drawer and server navigation authority, on the changed route only.
    const context=await evaluate(`JSON.stringify([...document.querySelectorAll('[data-context-project],[data-context-site]')].map(e=>({name:e.name,value:e.value,disabled:e.disabled})))`);
    await open();
    const links=await evaluate("[...document.querySelectorAll('#erp-module-selector nav a')].map(a=>({label:a.firstChild.textContent.trim(),url:a.getAttribute('href')}))");
    assert(JSON.stringify(links)===JSON.stringify(scenario.expectedNavigation),'Navigation matches server authority');
    assert(await evaluate(`document.querySelector('#erp-module-selector nav [aria-current]')?.getAttribute('href')==='/procurement/'`),'Procurement active');
    await key('Escape');await closed();
    assert(context===await evaluate(`JSON.stringify([...document.querySelectorAll('[data-context-project],[data-context-site]')].map(e=>({name:e.name,value:e.value,disabled:e.disabled})))`),'Context controls unchanged');
    if(scenario.state==='draft'){
      const source='document.querySelector("select[name=material]")';
      assert(await evaluate(`!!${source}.tomselect`),'Existing Tom Select mounted');
      await click('select[name=material] + .ts-wrapper .ts-control');
      await evaluate(`(()=>{const t=${source}.tomselect;t.clear();t.setTextboxValue('سیمان');t.onInput()})()`);
      await waitFor(`(()=>{const t=${source}.tomselect;return t.isOpen && t.loading===0 && !!t.dropdown.querySelector('[data-value="${scenario.material}"]')})()`);
      await shot(scenario.name+'-selector');
      await click(`select[name=material] + .ts-wrapper .ts-dropdown [data-value="${scenario.material}"]`);
      assert(await evaluate(`(()=>{const s=${source};document.dispatchEvent(new CustomEvent('htmx:afterSwap'));document.dispatchEvent(new CustomEvent('htmx:afterSwap'));return s.value==='${scenario.material}' && new FormData(s.form).get('material')===s.value && s.parentElement.querySelectorAll('.ts-wrapper').length===1})()`),'Tom Select value/FormData/idempotent mount');
      await evaluate(`document.querySelector('[name=quantity]').value='-1';document.querySelector('[name=description]').value='مصرف مرحله دوم'`);
      await click('form[aria-label="افزودن قلم"] button[type=submit]');
      await waitFor("document.readyState==='complete' && !!document.querySelector('.erp-form-field--invalid')");
      assert(await evaluate(`document.querySelector('[name=quantity]').value==='-1' && document.querySelector('[name=description]').value==='مصرف مرحله دوم' && document.querySelector('[name=material]').value==='${scenario.material}'`),'Validation retains bound inputs');
      await inspectLayout();await capture(scenario.name+'-validation');
      await evaluate("document.querySelector('[name=quantity]').value='8.5'");
      await click('form[aria-label="افزودن قلم"] button[type=submit]');
      await waitFor("document.readyState==='complete' && document.querySelectorAll('.pr-detail__table tbody tr').length===2");
      await settled();
      // Cancellation stays separate, preserves its reason, and never posts on dismissal.
      await click('#cancel-request summary');
      await evaluate("document.querySelector('[name=\"cancel-reason\"]').value='دلیل حفظ شود'");
      const before=posts.length;
      await click('#cancel-request button[type=submit]');await waitFor('Swal.isVisible()');
      await click('.swal2-cancel');await waitFor('!Swal.isVisible()');
      assert(posts.length===before && await evaluate("document.querySelector('[name=\"cancel-reason\"]').value==='دلیل حفظ شود'"),'Cancellation dismissal preserves input without POST');
      await evaluate("document.querySelector('#cancel-request').open=false");
      await confirm('form[action$="/submit/"] button','submitted-'+scenario.width,true);
      assert(await evaluate("!document.querySelector('form[aria-label=\"افزودن قلم\"]') && !document.querySelector('[data-pr-rfq]') && document.querySelectorAll('.pr-detail__history li').length===1"),'Submitted read-only/history');
      await inspectLayout();await capture('journey-submitted-'+scenario.width);
      await click('details:has(form[action$="/approve/"]) > summary');
      await evaluate("document.querySelector('[name=\"approve-reason\"]').value='نیاز پروژه بازبینی شد'");
      await confirm('form[action$="/approve/"] button','approved-'+scenario.width,true);
      assert(await evaluate("!!document.querySelector('[data-pr-rfq]') && !document.querySelector('main form[action*=\"/requests/\"]') && document.querySelectorAll('.pr-detail__history li').length===2"),'Approved lifecycle presentation');
      await capture('journey-approved-'+scenario.width);
    }else if(scenario.state==='submitted'){
      assert(await evaluate("!document.querySelector('form[aria-label=\"افزودن قلم\"]') && !document.querySelector('[data-pr-rfq]') && document.querySelectorAll('.pr-detail__history li').length===1"),'Submitted read-only and factual history');
      await click('details:has(form[action$="/reject/"]) > summary');
      await evaluate("document.querySelector('[name=\"reject-reason\"]').value='مقدار موردنیاز بازبینی شود'");
      await confirm('form[action$="/reject/"] button','rejected-'+scenario.width,true);
      await capture('journey-rejected-'+scenario.width);
    }else{
      assert(await evaluate("!!document.querySelector('[data-pr-rfq]') && !!document.querySelector('[data-pr-existing-rfq]') && !document.querySelector('main form[action*=\"/requests/\"]')"),'Approved RFQ lineage and read-only items');
      await click('[data-pr-rfq]');await waitFor("document.readyState==='complete' && !!document.querySelector('[name=purchase_request_id]')");
      assert(await evaluate("document.querySelector('[name=purchase_request_id]').type==='hidden'"),'Contextual RFQ source remains inherited');
      const history=await send('Page.getNavigationHistory');
      await send('Page.navigateToHistoryEntry',{entryId:history.entries[history.currentIndex-1].id});
      await waitFor(`document.readyState==='complete' && location.pathname===${JSON.stringify(scenario.path)} && !!document.querySelector('[data-pr-existing-rfq]')`);
      await click('[data-pr-existing-rfq]');await waitFor(`document.readyState==='complete' && location.pathname===${JSON.stringify(scenario.rfqPath)}`);
      await send('Page.navigate',{url:base+scenario.path});await waitFor("document.readyState==='complete' && !!document.querySelector('[data-pr-rfq]')");
    }
    await send('Page.reload');await waitFor("document.readyState==='complete' && !!document.querySelector('[data-pr-state]')");await settled();
    assert(posts.length===(scenario.state==='draft'?4:scenario.state==='submitted'?1:0),'Only the intended item/lifecycle POSTs; refresh/back do not repeat mutations');
    const final=await inspectLayout();state.classes=[...new Set([...state.classes,...final.classes])];
    const bad=requests.filter(r=>r.status>=400 && !(r.url.endsWith('/favicon.ico') && r.status===404) && !(scenario.state==='draft' && r.type==='Document' && r.status===400 && new URL(r.url).pathname.endsWith('/items/')));
    const canceled=failures.filter(f=>f.canceled && f.type==='Fetch' && f.url?.includes('/choices/material/') && requests.some(r=>r.type==='Fetch' && r.status===200 && r.url.includes('/choices/material/')));
    const baselineLogs=logErrors.filter(e=>e.source==='network' && e.url && (new URL(e.url).pathname==='/favicon.ico' || (scenario.state==='draft' && new URL(e.url).pathname.endsWith('/items/') && requests.some(r=>r.url===e.url && r.status===400))));
    assert(!bad.length && !failures.some(f=>!canceled.includes(f)),'No unexpected route/asset/lookup failure '+JSON.stringify({bad,failures}));
    assert(!errors.length && !consoleErrors.length && !external.length && logErrors.every(e=>baselineLogs.includes(e)),'No JS/console/external errors '+JSON.stringify({errors,consoleErrors,external,logErrors}));
    results.push({name:scenario.name,path:scenario.path,width:scenario.width,state,final,posts,requests,failures,canceled,logErrors,baselineLogs,errors,consoleErrors,external});
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
  if(!resolve(profile).startsWith(resolve(tmpdir())+sep) || !profile.includes('bonira-pr-uiux-'))throw new Error('Unsafe temporary profile path');
  await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
