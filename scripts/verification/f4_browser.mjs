// Installed Chrome; isolated Django test data. No browser automation dependency.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { createServer } from 'node:net';

const [base, output] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.F4_SCENARIOS);
const sessions=JSON.parse(process.env.F4_SESSIONS);
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-f4-'));
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
  for(const scenario of scenarios){
    requests=[];failures=[];errors=[];consoleErrors=[];external=[];posts=[];logErrors=[];
    await send('Network.clearBrowserCookies');
    await send('Network.setCookie',{name:'sessionid',value:sessions[scenario.actor],url:base});
    await send('Emulation.setDeviceMetricsOverride',{width:scenario.width,height:900,deviceScaleFactor:1,mobile:scenario.width===390});
    await send('Page.navigate',{url:base+scenario.path});
    await waitFor(`location.pathname===${JSON.stringify(scenario.path)} && document.readyState==='complete'`);
    await evaluate('document.fonts.ready.then(()=>true)');
    const state=await evaluate(`(() => ({
      lang:document.documentElement.lang,dir:document.documentElement.dir,
      width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
      fontLoaded:document.fonts.check('14px Vazirmatn'),
      foundation:[...document.querySelectorAll('link[href$="/static/css/tailwind.css"]')].map(e=>({href:e.href,media:e.media,onload:e.getAttribute('onload'),rules:e.sheet?.cssRules.length})),
      foundationLast:document.head.querySelector('link[href$="/static/css/tailwind.css"]')===[...document.head.querySelectorAll('style,link[rel=stylesheet]')].at(-1),
      scripts:[...document.scripts].map(e=>e.src).filter(Boolean),
      classes:[...new Set([...document.body.querySelectorAll('*')].flatMap(e=>[...e.classList]))],
      selectors:[...document.querySelectorAll('select[data-business-choice]')].map(e=>({name:e.name,enhanced:!!e.tomselect,url:e.dataset.optionsUrl})),
      native:[...document.querySelectorAll('select:not([data-business-choice])')].map(e=>({name:e.name,enhanced:!!e.tomselect})),
      utilityProbe:(()=>{const e=document.createElement('div');e.className='hidden';document.body.append(e);const hidden=getComputedStyle(e).display==='none';e.className='flex';const flex=getComputedStyle(e).display==='flex';e.remove();return {hidden,flex};})(),
    }))()`);
    assert(state.lang==='fa' && state.dir==='rtl' && state.scroll<=state.width+1 && state.fontLoaded,'RTL/responsive/local font');
    assert(state.foundation.length===1 && state.foundation[0].rules>0 && !state.foundation[0].onload && !state.foundation[0].media && state.foundationLast && state.utilityProbe.hidden && state.utilityProbe.flex,'Local synchronous Tailwind with working utilities/cascade');
    assert(!state.scripts.some(url=>url.includes('tailwindcss.com')),'No Tailwind browser compiler');
    assert(state.selectors.every(x=>x.enhanced) && state.native.every(x=>!x.enhanced),'Business/native selectors preserved');
    const actions=['local Tailwind computed utility/cascade checks'];
    const initial=await evaluate(`(() => ({
      lang:document.documentElement.lang,dir:document.documentElement.dir,
      width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
      triggers:document.querySelectorAll('[data-module-trigger]').length,
      closed:!document.querySelector('#erp-module-selector').open,
      contexts:[...document.querySelectorAll('[data-context-project],[data-context-site]')].map(s=>({name:s.name,value:s.value,disabled:s.disabled})),
      sidebar:[...document.querySelectorAll('aside .erp-nav a')].map(a=>a.getAttribute('href')),
      mobile:[...document.querySelectorAll('.erp-mobile-nav .erp-nav a')].map(a=>a.getAttribute('href')),
    }))()`);
    assert(initial.lang==='fa' && initial.dir==='rtl' && initial.scroll<=initial.width+1 && initial.triggers===1 && initial.closed,scenario.name+': shell/RTL/overflow/single trigger');
    assert(JSON.stringify(initial.sidebar)===JSON.stringify(initial.mobile),'Existing desktop/mobile navigation agree');
    await evaluate(`(() => {const spacer=document.createElement('div');spacer.id='f3-scroll-probe';spacer.style.height='1800px';document.querySelector('main').append(spacer);window.scrollTo(0,100)})()`);
    await open();
    const drawerState=await evaluate(`(() => {
      const d=document.querySelector('#erp-module-selector'),r=d.querySelector('nav'),box=d.getBoundingClientRect();
      return {dir:getComputedStyle(d).direction,top:box.top,width:box.width,
        modal:d.matches(':modal'),focusInside:d.contains(document.activeElement),
        locked:getComputedStyle(document.documentElement).overflowY==='hidden' && getComputedStyle(document.body).overflowY==='hidden',
        expanded:document.querySelector('[data-module-trigger]').getAttribute('aria-expanded'),
        links:[...r.querySelectorAll('a')].map(a=>({label:a.firstChild.textContent.trim(),url:a.getAttribute('href')})),
        active:[...r.querySelectorAll('a[aria-current]')].map(a=>a.getAttribute('href')),
        tops:[...r.querySelectorAll('a')].map(a=>a.getBoundingClientRect().top),
        rowWidth:r.clientWidth,scrollWidth:r.scrollWidth,scrollLeft:r.scrollLeft,
      };
    })()`);
    assert(JSON.stringify(drawerState.links)===JSON.stringify(scenario.expected),'Exact server-authorized labels/routes, no extra or hidden destinations');
    assert(JSON.stringify(drawerState.active)===JSON.stringify([scenario.active]),'Exactly one correct active module');
    assert(drawerState.dir==='rtl' && Math.abs(drawerState.top)<1 && drawerState.width<=scenario.width && drawerState.modal && drawerState.focusInside && drawerState.locked && drawerState.expanded==='true','Top modal/RTL/focus/scroll lock');
    assert(Math.max(...drawerState.tops)-Math.min(...drawerState.tops)<1,'All modules remain in one row');
    await shot(scenario.name+'-open');
    const beforeY=await evaluate('scrollY');
    await send('Input.dispatchMouseEvent',{type:'mouseWheel',x:scenario.width/2,y:800,deltaX:0,deltaY:350});
    await new Promise(done=>setTimeout(done,150));
    assert(await evaluate(`scrollY===${beforeY}`),'Background wheel scroll is locked');
    if (scenario.width===390) {
      assert(drawerState.scrollWidth>drawerState.rowWidth,'Mobile row overflows inside drawer');
      const point=await evaluate(`(() => {const r=document.querySelector('.erp-module-selector__row').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      const start=await evaluate('document.querySelector(".erp-module-selector__row").scrollLeft');
      await send('Input.dispatchMouseEvent',{type:'mouseWheel',...point,deltaX:-280,deltaY:0});
      await new Promise(done=>setTimeout(done,150));
      let moved=await evaluate(`document.querySelector('.erp-module-selector__row').scrollLeft!==${start}`);
      if(!moved){
        await send('Input.dispatchMouseEvent',{type:'mouseWheel',...point,deltaX:280,deltaY:0});
        await new Promise(done=>setTimeout(done,150));
        moved=await evaluate(`document.querySelector('.erp-module-selector__row').scrollLeft!==${start}`);
      }
      assert(moved,'Real horizontal wheel scroll works on mobile RTL row');
    }
    await evaluate(`document.querySelector('.erp-module-selector__row a:last-child').focus()`);
    await key('Tab');
    assert(await evaluate('document.querySelector("#erp-module-selector").contains(document.activeElement)'),'Native modal traps keyboard focus');
    await key('Tab',8);
    assert(await evaluate('document.activeElement===document.querySelector(".erp-module-selector__row a:last-child")'),'Shift+Tab wraps back to last destination');
    await click('[data-module-close]');await closed();
    assert(await evaluate(`scrollY===${beforeY}`),'Close preserves background position');
    await open();
    const backdropY=await evaluate('Math.min(850,document.querySelector("#erp-module-selector").getBoundingClientRect().bottom+80)');
    await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,x:scenario.width/2,y:backdropY});
    await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,x:scenario.width/2,y:backdropY});
    await closed();
    await open();await key('Escape');await closed();
    await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
    await open();
    assert(await evaluate('getComputedStyle(document.querySelector("#erp-module-selector")).animationName==="none"'),'Reduced-motion disables opening animation');
    await key('Escape');await closed();
    await send('Emulation.setEmulatedMedia',{features:[]});
    const after=await evaluate(`(() => ({
      contexts:[...document.querySelectorAll('[data-context-project],[data-context-site]')].map(s=>({name:s.name,value:s.value,disabled:s.disabled})),
      sidebar:[...document.querySelectorAll('aside .erp-nav a')].map(a=>a.getAttribute('href')),
      mobile:[...document.querySelectorAll('.erp-mobile-nav .erp-nav a')].map(a=>a.getAttribute('href')),
    }))()`);
    assert(JSON.stringify(initial.contexts)===JSON.stringify(after.contexts) && JSON.stringify(initial.sidebar)===JSON.stringify(after.sidebar) && JSON.stringify(initial.mobile)===JSON.stringify(after.mobile),'Context and existing navigations unchanged by drawer');
    await evaluate('document.querySelector("#f3-scroll-probe").remove();window.scrollTo(0,0)');

    actions.push('filtered active drawer, horizontal scroll, close/backdrop/Escape, focus/Tab, scroll lock, reduced motion, unchanged context');
    if(scenario.choice){
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
      actions.push('real local Tom Select search, native value/FormData/change, no duplicate mount');
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
    }
    assert(posts.length===(scenario.action?1:0),'Only the explicitly confirmed existing submit may POST');
    const bad=requests.filter(r=>r.status>=400 && !r.url.endsWith('/favicon.ico'));
    const lookupPaths=state.selectors.map(x=>new URL(x.url,base).pathname);
    const canceled=failures.filter(f=>f.canceled && f.type==='Fetch' && lookupPaths.includes(new URL(f.url).pathname) && requests.some(r=>r.type==='Fetch' && r.status===200 && new URL(r.url).pathname===new URL(f.url).pathname));
    const baselineLogs=logErrors.filter(e=>e.source==='network' && e.url && new URL(e.url).pathname==='/favicon.ico' && requests.some(r=>r.url===e.url && r.status===404));
    assert(!bad.length && !failures.some(f=>!canceled.includes(f)), 'No failed required local asset or current lookup '+JSON.stringify({bad,failures}));
    assert(!errors.length && !consoleErrors.length && !external.length && logErrors.every(e=>baselineLogs.includes(e)), 'No application JS/console/external errors '+JSON.stringify({errors,consoleErrors,external,logErrors}));
    assert(requests.filter(r=>r.type==='Document').length && requests.filter(r=>r.type==='Document').every(r=>r.status===200),'Real routes load successfully');
    await evaluate('window.scrollTo(0,0)');await shot(scenario.name+'-final');
    const finalClasses=await evaluate('[...new Set([...document.body.querySelectorAll("*")].flatMap(e=>[...e.classList]))]');
    state.classes=[...new Set([...state.classes,...finalClasses])];
    results.push({name:scenario.name,path:scenario.path,width:scenario.width,actor:scenario.actor,state,drawerState,initial,after,actions,posts,requests,failures,canceled,logErrors,baselineLogs,errors,consoleErrors,external});
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
  if(!resolve(profile).startsWith(resolve(tmpdir())+sep) || !profile.includes('bonira-f4-'))throw new Error('Unsafe temporary profile path');
  await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
