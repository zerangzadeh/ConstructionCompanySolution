// Installed Chrome; isolated Django test data. No browser automation dependency.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { createServer } from 'node:net';

const [base, output] = process.argv.slice(2);
const baseline = process.env.F1_PHASE === 'before';
const scenarios = JSON.parse(process.env.F1_SCENARIOS);
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-f1-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-component-update',
  ...(!baseline ? ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost'] : []),
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true });
let socket;
const results = [];
const offlineProof = [];
let requests = [], failures = [], errors = [], consoleErrors = [], external = [];
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
      if (!local) external.push({ url: p.request.url, type: p.resourceType, blocked: !baseline });
      // Baseline permits only the existing Tailwind CDN; final permits loopback only.
      const permitted = local || (baseline && url.hostname === 'cdn.tailwindcss.com');
      send(permitted ? 'Fetch.continueRequest' : 'Fetch.failRequest', permitted
        ? { requestId: p.requestId } : { requestId: p.requestId, errorReason: 'BlockedByClient' }).catch(() => {});
    }
    if (m.method === 'Network.responseReceived') requests.push({ url: p.response.url, type: p.type, status: p.response.status, cached: !!p.response.fromDiskCache });
    if (m.method === 'Network.requestWillBeSent') requestURLs.set(p.requestId,p.request.url);
    if (m.method === 'Network.loadingFailed') failures.push({ url:requestURLs.get(p.requestId),type:p.type,error:p.errorText,blocked:p.blockedReason,canceled:!!p.canceled });
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
    const point = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing '+${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    await send('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...point});
    await send('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...point});
  };
  await mkdir(output, { recursive: true });
  await send('Network.enable'); await send('Page.enable'); await send('Runtime.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Network.setBypassServiceWorker', { bypass: true });
  await send('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] });
  const version = await send('Browser.getVersion');
  if (!baseline) {
    const blocked = await evaluate(`fetch('https://offline-proof.invalid/f1').then(()=>false,()=>true)`);
    offlineProof.push({ blocked, requests: external, failures });
    if (!blocked || !external.some(r => r.blocked)) throw new Error('External blocking negative control failed');
  }
  for (const scenario of scenarios) {
    requests = []; failures = []; errors = []; consoleErrors = []; external = [];
    await send('Network.clearBrowserCookies');
    if (!scenario.anonymous) await send('Network.setCookie', { name: 'sessionid', value: process.env.F1_SESSION, url: base });
    await send('Emulation.setDeviceMetricsOverride', { width: scenario.width, height: 900, deviceScaleFactor: 1, mobile: scenario.width === 390 });
    await send('Page.navigate', { url: base + scenario.path });
    await waitFor(`location.pathname===${JSON.stringify(scenario.path.split('?')[0])} && document.readyState==='complete'`);
    await evaluate('document.fonts.ready.then(()=>true)');
    await new Promise(done => setTimeout(done, 200));
    // Sample all body elements: geometry and computed visual styling are compared
    // before/after without depending on generated UUIDs or CSRF token values.
    const state = await evaluate(`(() => {
      const props=['display','position','direction','fontFamily','fontSize','fontWeight','lineHeight','color','backgroundColor','borderTopWidth','borderTopColor','borderRadius','paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','gap','gridTemplateColumns','boxShadow','overflowX'];
      const nodes=[...document.body.querySelectorAll('*')].filter(e=>!['SCRIPT','STYLE','NOSCRIPT'].includes(e.tagName));
      return { lang:document.documentElement.lang,dir:document.documentElement.dir,width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
        font:getComputedStyle(document.body).fontFamily,fontLoaded:document.fonts.check('14px Vazirmatn'),
        sheets:[...document.querySelectorAll('link[rel=stylesheet]')].map(e=>({href:e.href,media:e.media,onload:e.getAttribute('onload')})),
        foundationIsLast:document.head.querySelector('link[href$="/static/css/tailwind.css"]')===[...document.head.querySelectorAll('style,link[rel=stylesheet]')].at(-1),
        scripts:[...document.scripts].map(e=>e.src).filter(Boolean),
        classes:[...new Set(nodes.flatMap(e=>[...e.classList]))].sort(),
        badges:[...document.querySelectorAll('.erp-badge')].map(e=>({class:e.className,color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor})),
        tables:document.querySelectorAll('table').length,
        selectors:[...document.querySelectorAll('select[data-business-choice]')].map(e=>({name:e.name,enhanced:!!e.tomselect})),
        visual:nodes.map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {tag:e.tagName,class:e.getAttribute('class'),rect:[r.x,r.y,r.width,r.height].map(n=>Math.round(n*100)/100),style:props.map(p=>s[p])}})
      };
    })()`);
    if (state.lang !== 'fa' || state.dir !== 'rtl' || state.scroll > state.width + 1) throw new Error(scenario.name + ': RTL/overflow');
    if (!state.fontLoaded || !state.font.includes('Vazirmatn')) throw new Error(scenario.name + ': local typography');
    if (state.selectors.some(s => !s.enhanced)) throw new Error(scenario.name + ': Tom Select not enhanced');
    if (!baseline && (!state.foundationIsLast || !state.sheets.some(s => s.href.endsWith('/static/css/tailwind.css') && !s.onload && !s.media) || state.scripts.some(s => s.includes('tailwindcss')))) throw new Error(scenario.name + ': local synchronous stylesheet/cascade');
    const actions = [];
    if (!scenario.anonymous) {
      if (scenario.width === 390) {
        await click('.erp-mobile-nav summary');
        if (!await evaluate('document.querySelector(".erp-mobile-nav").open')) throw new Error('Mobile menu failed');
        await click('.erp-mobile-nav summary'); actions.push('mobile navigation open/close');
      } else if (!await evaluate('!!document.querySelector("aside") && getComputedStyle(document.querySelector("aside")).display!=="none"')) throw new Error('Desktop navigation missing');
    }
    if (scenario.lookup) {
      await click('select[name="work_team"] + .ts-wrapper .ts-control');
      await send('Input.insertText', { text: 'آرماتور' });
      await new Promise(done=>setTimeout(done,500));
      await waitFor(`(() => {const t=document.querySelector('select[name="work_team"]').tomselect;return t.isOpen && t.loading===0 && !!t.dropdown.querySelector('[data-value]')})()`);
      await click('select[name="work_team"] + .ts-wrapper .ts-dropdown [data-value]');
      if (!await evaluate(`!!document.querySelector('select[name="work_team"]').value`)) throw new Error('Offline choice selection failed');
      actions.push('Tom Select remote lookup and selection over loopback');
    }
    if (scenario.datepicker) {
      await click('.erp-jalali-trigger');
      if (!await evaluate(`!![...document.querySelectorAll('.erp-jalali-popover')].find(e=>!e.hidden && e.getBoundingClientRect().width>0)`)) throw new Error('Jalali picker failed');
      await send('Input.dispatchKeyEvent', { type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27 });
      actions.push('Jalali picker open');
    }
    if (scenario.filter) {
      await click('main [data-filter-apply]');
      await waitFor(`document.readyState==='complete' && !!document.querySelector('main')`);
      actions.push('existing list filter submit');
    }
    if (errors.length || consoleErrors.length) throw new Error(scenario.name + ': JS errors ' + JSON.stringify({errors,consoleErrors}));
    const bad = requests.filter(r => r.status >= 400 && !r.url.endsWith('/favicon.ico'));
    // Existing autocomplete aborts superseded preload/search fetches. Retain and
    // classify those only when the same local endpoint has a successful result;
    // missing assets, failed current lookups and other failures remain fatal.
    const canceledLookups=failures.filter(f=>f.canceled && f.type==='Fetch' && f.url?.startsWith(base+'/workforce/field/choices/') && requests.some(r=>r.type==='Fetch' && r.status===200 && new URL(r.url).pathname===new URL(f.url).pathname));
    const unexpectedFailures=failures.filter(f=>!canceledLookups.includes(f));
    if (bad.length || unexpectedFailures.length || (!baseline && external.length)) throw new Error(scenario.name + ': asset/network failures ' + JSON.stringify({bad,unexpectedFailures,external}));
    const documents = requests.filter(r => r.type === 'Document');
    if (!documents.length || documents.some(r => r.status !== 200)) throw new Error(scenario.name + ': route status');
    await evaluate('window.scrollTo(0,0)');
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(join(output, scenario.name + '.png'), Buffer.from(shot.data, 'base64'));
    results.push({ name:scenario.name,path:scenario.path,width:scenario.width,state,actions,requests,failures,canceledLookups,external,errors,consoleErrors });
  }
  await writeFile(join(output, 'results.json'), JSON.stringify({ phase:baseline?'before':'offline',version,offlineProof,results }, null, 2));
  process.stdout.write(JSON.stringify({ phase:baseline?'before':'offline',pages:results.length,chrome:version.product }));
} catch (error) {
  await mkdir(output, { recursive:true });
  if (results.length) await writeFile(join(output,'partial-results.json'), JSON.stringify(results,null,2));
  await writeFile(join(output,'failure.json'), JSON.stringify({error:error.stack,completed:results.length,requests,failures,external,errors,consoleErrors},null,2));
  throw error;
} finally {
  socket?.close(); chrome.kill();
  await new Promise(done => chrome.once('exit',done));
  if (!resolve(profile).startsWith(resolve(tmpdir()) + sep) || !profile.includes('bonira-f1-')) throw new Error('Unsafe temporary profile path');
  await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
