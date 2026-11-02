// Installed Chrome; isolated Django test data. No browser automation dependency.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { createServer } from 'node:net';

const [base, output] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.F2_SCENARIOS);
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-f2-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-component-update',
  '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true });
let socket;
const results = [];
const offlineProof = [];
let requests = [], failures = [], errors = [], consoleErrors = [], external = [], posts = [];
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
  await send('Network.enable'); await send('Page.enable'); await send('Runtime.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Network.setBypassServiceWorker', { bypass: true });
  await send('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] });
  const version = await send('Browser.getVersion');
  const blocked = await evaluate(`fetch('https://offline-proof.invalid/f2').then(()=>false,()=>true)`);
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
  for (const scenario of scenarios) {
    requests = []; failures = []; errors = []; consoleErrors = []; external = []; posts = [];
    await send('Network.clearBrowserCookies');
    await send('Network.setCookie', {name: 'sessionid', value: process.env.F2_SESSION, url: base});
    await send('Emulation.setDeviceMetricsOverride', {width:scenario.width,height:900,deviceScaleFactor:1,mobile:scenario.width===390});
    await send('Page.navigate', {url:base + scenario.path});
    await waitFor(`location.pathname===${JSON.stringify(scenario.path)} && document.readyState==='complete'`);
    await evaluate('document.fonts.ready.then(()=>true)');
    const state = await evaluate(`(() => ({
      lang:document.documentElement.lang, dir:document.documentElement.dir,
      width:document.documentElement.clientWidth, scroll:document.documentElement.scrollWidth,
      selectors:[...document.querySelectorAll('select[data-business-choice]')].map(s=>({name:s.name,enhanced:!!s.tomselect})),
      native:[...document.querySelectorAll('select:not([data-business-choice])')].map(s=>({name:s.name,enhanced:!!s.tomselect})),
      fontLoaded:document.fonts.check('14px Vazirmatn'),
    }))()`);
    assert(state.lang==='fa' && state.dir==='rtl' && state.scroll<=state.width+1 && state.fontLoaded, scenario.name+': RTL/responsive/font');
    assert(state.selectors.length && state.selectors.every(s=>s.enhanced), 'Existing business choices enhanced');
    assert(state.native.every(s=>!s.enhanced), 'Short/native selects preserved');
    const source = `document.querySelector('select[name="${scenario.choice}"]')`;
    await evaluate(`${source}.addEventListener('change',()=>window.f2changes=(window.f2changes||0)+1)`);
    await click(`select[name="${scenario.choice}"] + .ts-wrapper .ts-control`);
    await send('Input.insertText', {text:scenario.query});
    await new Promise(done=>setTimeout(done,600));
    await waitFor(`(() => {const t=${source}.tomselect;return t.isOpen && t.loading===0 && !!t.dropdown.querySelector('[data-value]')})()`);
    await shot(scenario.name+'-selector');
    await click(`select[name="${scenario.choice}"] + .ts-wrapper .ts-dropdown [data-value]`);
    assert(await evaluate(`(() => {const s=${source}; return !!s.value && new FormData(s.form).get(s.name)===s.value && window.f2changes>0})()`), 'Choice value/form submission/change event');
    assert(await evaluate(`(() => {const s=${source}, t=s.tomselect;
      document.dispatchEvent(new CustomEvent('htmx:afterSwap'));
      document.dispatchEvent(new CustomEvent('htmx:afterSwap'));
      return t===s.tomselect && s.parentElement.querySelectorAll('.ts-wrapper').length===1;
    })()`), 'Duplicate initialization prevention');
    const actions=['real remote search and native selection/change/FormData', 'repeat HTMX mount does not duplicate', 'native short selects retained'];
    // Exercise the shared widget's multiple/disabled and cleanup contracts in
    // a small disposable DOM fixture on the representative worker page only.
    if (scenario.choice==='work_team') {
      assert(await evaluate(`(() => {
        const source=${source}; const host=document.createElement('form');
        host.innerHTML='<div data-field-search><select name="f2_multi" multiple data-business-choice="team"><option value="a">الف</option><option value="b">ب</option></select><span data-choice-status></span></div><div data-field-search><select name="f2_disabled" disabled data-business-choice="team"><option value="a">الف</option></select><span data-choice-status></span></div>';
        document.querySelector('main').append(host);
        for(const s of host.querySelectorAll('select')) s.dataset.optionsUrl=source.dataset.optionsUrl;
        host.elements.f2_disabled.dataset.dependsOn='f2_multi';
        document.dispatchEvent(new CustomEvent('htmx:afterSwap'));
        const m=host.elements.f2_multi,d=host.elements.f2_disabled;
        m.tomselect.setValue(['a','b']);
        const values=new FormData(host).getAll('f2_multi');
        const multi=m.multiple && m.tomselect.items.length===2 && values.join(',')==='a,b';
        const disabled=d.disabled && d.tomselect.isDisabled && !new FormData(host).has('f2_disabled');
        const old=m.tomselect;
        document.dispatchEvent(new CustomEvent('htmx:beforeCleanupElement',{detail:{elt:m}}));
        const cleaned=!m.tomselect;
        document.dispatchEvent(new CustomEvent('htmx:afterSwap'));
        const remounted=m.tomselect && m.tomselect!==old && m.parentElement.querySelectorAll('.ts-wrapper').length===1;
        document.dispatchEvent(new CustomEvent('htmx:beforeCleanupElement',{detail:{elt:host}}));
        host.remove(); return multi && disabled && cleaned && remounted;
      })()`), 'Multiple/disabled/dependency/HTMX cleanup preservation');
      actions.push('multiple values, disabled omission, dependency reset, direct/container cleanup and remount');
    }
    if (scenario.action) {
      await waitFor('!!window.Swal && !!window.BoniraInteractions');
      // Filled reason remains inline and unchanged after canceling its dialog.
      await click('#cancel-request summary');
      await evaluate(`document.querySelector('[name="cancel-reason"]').value='دلیل آزمایشی حفظ شود'`);
      await click('#cancel-request button[type="submit"]');
      await waitFor('Swal.isVisible() && !!document.querySelector(".swal2-cancel")');
      assert(posts.length===0, 'No request before confirmation');
      assert(await evaluate('getComputedStyle(Swal.getPopup()).direction==="rtl" && Swal.getPopup().getBoundingClientRect().width<=innerWidth'), 'Responsive RTL dialog');
      await shot(scenario.name+'-confirmation');
      await click('.swal2-cancel');
      await waitFor('!Swal.isVisible()');
      assert(posts.length===0 && await evaluate(`document.querySelector('[name="cancel-reason"]').value==='دلیل آزمایشی حفظ شود'`), 'Cancel sends no POST and preserves reason');
      await evaluate(`document.querySelector('#cancel-request').open=false`);
      const submit='form[action$="/submit/"] button';
      await click(submit);
      await waitFor('Swal.isVisible()');
      assert(await evaluate('document.activeElement===Swal.getCancelButton()'), 'Safe default keyboard focus');
      await send('Input.dispatchKeyEvent', {type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
      await waitFor('!Swal.isVisible()');
      assert(posts.length===0, 'Escape sends no POST');
      await click(submit);
      await waitFor('Swal.isVisible()');
      assert(posts.length===0, 'Submit is still held until confirmation');
      await click('.swal2-confirm');
      await waitFor(`document.readyState==='complete' && !!document.querySelector('.erp-message--success') && !document.querySelector('form[action$="/submit/"]')`);
      await waitFor('Swal.isVisible() && Swal.getPopup().classList.contains("swal2-toast")');
      assert(posts.length===1 && posts[0].url.endsWith('/submit/'), 'Exactly one confirmed POST to existing endpoint');
      await shot(scenario.name+'-success');
      actions.push('cancel and Escape: zero POST, reason retained, cancel focused', 'confirm: exactly one existing POST, success toast and retained inline feedback');
      await evaluate('Swal.close()');
      await waitFor('!Swal.isVisible()');
      for (const action of ['approve','reject']) {
        const form=`form[action$="/${action}/"]`;
        assert(await evaluate(`!!document.querySelector('${form}')`), 'Existing governed decision available');
        await click(`details:has(${form}) > summary`);
        await click(`${form} button[type="submit"]`);
        await waitFor('Swal.isVisible()');
        await click('.swal2-cancel');
        await waitFor('!Swal.isVisible()');
        assert(posts.length===1, action+' dismissal sends no POST');
      }
      actions.push('existing approve/reject confirmations dismiss without POST');
      // Native requestSubmit must preserve named submitter and existing handlers.
      await evaluate(`(() => {
        const f=document.createElement('form'); f.id='f2-native-contract';f.dataset.confirmTitle='آزمون تأیید';
        f.innerHTML='<input name="reason" required><button type="submit" name="decision" value="keep" formaction="/f2-unused/">ادامه</button>';
        f.addEventListener('submit',e=>{e.preventDefault();window.f2native={count:(window.f2native?.count||0)+1,value:new FormData(f,e.submitter).get('decision'),action:e.submitter.getAttribute('formaction')};});
        document.querySelector('main').append(f);f.requestSubmit(f.querySelector('button'));
      })()`);
      assert(await evaluate('!Swal.isVisible() && !window.f2native'), 'Native required validation occurs before dialog');
      await evaluate(`(() => {const f=document.querySelector('#f2-native-contract');f.elements.reason.value='دلیل';f.requestSubmit(f.querySelector('button'));f.requestSubmit(f.querySelector('button'));})()`);
      await waitFor('Swal.isVisible()');
      assert(await evaluate('!window.f2native && document.querySelectorAll(".swal2-popup").length===1'), 'Existing submit handlers held; repeated submit has one dialog');
      await click('.swal2-confirm');
      await waitFor('window.f2native?.count===1');
      assert(await evaluate('window.f2native.value==="keep" && window.f2native.action==="/f2-unused/"'), 'Named submitter/overridden action preserved');
      await evaluate(`document.querySelector('#f2-native-contract').remove()`);
      actions.push('required validation, submitter/formaction and existing handler retained, no duplicate submission');
    }
    assert(!errors.length && !consoleErrors.length && !external.length, scenario.name+': errors/external requests '+JSON.stringify({errors,consoleErrors,external}));
    const bad=requests.filter(r=>r.status>=400 && !r.url.endsWith('/favicon.ico'));
    const canceled=failures.filter(f=>f.canceled && f.type==='Fetch' && requests.some(r=>r.type==='Fetch' && r.status===200 && new URL(r.url).pathname===new URL(f.url).pathname));
    assert(!bad.length && !failures.some(f=>!canceled.includes(f)), 'Local asset/lookup failures '+JSON.stringify({bad,failures}));
    assert(requests.some(r=>r.type==='Document' && r.status===200), 'Real document loaded');
    await evaluate('window.scrollTo(0,0)'); await shot(scenario.name);
    results.push({name:scenario.name,path:scenario.path,width:scenario.width,state,actions,posts,requests,failures,errors,consoleErrors,external});
  }
  await writeFile(join(output,'results.json'),JSON.stringify({version,offlineProof,results},null,2));
  process.stdout.write(JSON.stringify({pages:results.length,chrome:version.product}));
} catch(error) {
  await mkdir(output,{recursive:true});
  await writeFile(join(output,'failure.json'),JSON.stringify({error:error.stack,completed:results.length,results,requests,failures,errors,consoleErrors,external,posts},null,2));
  throw error;
} finally {
  socket?.close(); chrome.kill();
  await new Promise(done=>chrome.once('exit',done));
  if (!resolve(profile).startsWith(resolve(tmpdir())+sep) || !profile.includes('bonira-f2-')) throw new Error('Unsafe temporary profile path');
  await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
