// Rendered Django shell/components + installed Chrome; isolated HTTP fixtures.
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile, writeFile, mkdtemp, rm, unlink} from 'node:fs/promises';
import {join, resolve, sep} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const output=resolve(process.argv[2]), root=process.cwd();
const shell=await readFile(join(output,'shell.html'),'utf8');
const fixtures=JSON.parse(await readFile(join(output,'fixtures.json'),'utf8'));
// Test-only HTMX, never added to the product or downloaded at browser runtime.
const htmxResponse=await fetch('https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.11.tgz');
assert.ok(htmxResponse.ok,'Test-only HTMX package is available');
const htmxArchive=join(output,'htmx-test-only.tgz');
await writeFile(htmxArchive,Buffer.from(await htmxResponse.arrayBuffer()));
const {execFileSync}=await import('node:child_process');
let htmx;
try { htmx=execFileSync('tar',['-xOzf',htmxArchive,'package/dist/htmx.min.js'],{windowsHide:true}); }
finally { await unlink(htmxArchive); }
assert.equal(createHash('sha384').update(htmx).digest('base64'),'2OatzQy1H+Zd/IIrjr1TcuDGqLXeHhbooAyJY1KdQMKnr4LZ22k31GBLdYKHmVjg');
const fixture=`<section class="erp-surface rounded-xl p-6"><h1 class="text-lg font-bold">پیام‌ها و وضعیت‌های سیستم</h1><form id="save" method="post" action="/save" data-confirm-title="ثبت اطلاعات نمونه" data-confirm-text="اطلاعات واردشده در این فرم ثبت می‌شود." data-confirm-label="ثبت اطلاعات"><label for="title">عنوان</label><input id="title" name="title" required><button class="erp-btn erp-btn--primary" name="decision" value="save" type="submit">ثبت اطلاعات</button></form><form id="failure" method="post" action="/fail"><button class="erp-btn erp-btn--secondary" type="submit">آزمون پاسخ ناموفق</button></form><form id="validation" method="post" action="/validation" novalidate><button class="erp-btn erp-btn--secondary" type="submit">اعتبارسنجی</button></form><div id="hx-target"></div><form id="hx" hx-post="/partial" hx-target="#hx-target" hx-confirm="ثبت درخواست نمونه"><button class="erp-btn erp-btn--primary" name="choice" value="keep" type="submit">ثبت درخواست</button></form></section>`;
const page=content=>shell.replace('</main>',content+'</main>').replace('</head>','<script src="/test-htmx.js" defer></script></head>');
let posts=[], external=[];
const server=createServer(async(req,res)=>{
 const path=new URL(req.url,'http://localhost').pathname;
 if(path==='/favicon.ico'){res.writeHead(204).end();return;}
 if(path==='/test-htmx.js'){res.setHeader('Content-Type','text/javascript');res.end(htmx);return;}
 if(path.startsWith('/static/')){
  try {const name=path.slice(8);if(name.includes('..'))throw Error('Invalid asset');const data=await readFile(join(root,'apps/accounts/static',name));res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/woff2');res.end(data);}catch{res.writeHead(404).end();}return;
 }
 if(req.method==='POST'){let body='';for await(const chunk of req)body+=chunk;posts.push({path,body});await new Promise(done=>setTimeout(done,400));}
 res.setHeader('Content-Type','text/html; charset=utf-8');
 if(path==='/partial'){res.end(`<p>پاسخ دریافت شد</p><template><div hx-swap-oob="beforeend:#bonira-feedback">${fixtures.messages.success}</div></template>`);return;}
 if(path==='/partial-fail'){res.writeHead(409).end('PRIVATE SQL technical failure');return;}
 if(path==='/silent'){res.end('<p>پاسخ بدون اعلان موفقیت</p>');return;}
 if(path==='/validation'){res.end(page(fixtures.validation+fixture));return;}
 if(path==='/save'){res.end(page(fixtures.messages.success+fixture));return;}
 if(path==='/fail'){res.writeHead(409).end(page(fixtures.messages.error+fixture));return;}
 if(fixtures.states[path.slice(1)]){res.writeHead(Number(path.slice(1))||200).end(Number(path.slice(1))?fixtures.states[path.slice(1)]:page(fixtures.states[path.slice(1)]+fixture));return;}
 res.end(page(fixture));
});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
const base=`http://127.0.0.1:${server.address().port}`;
const profile = await mkdtemp(join(tmpdir(), 'bonira-stage6-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
    '--headless=new', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, 'about:blank',
], {stdio:'ignore', windowsHide:true});
let socket;
const results = [], errors = [];
try {
    let port;
    for (let i=0;i<100;i++) {
        try {port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break;} catch {}
        await new Promise(done => setTimeout(done, 100));
    }
    assert.ok(port, 'Chrome started');
    const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p=>p.type==='page');
    socket = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise(done=>socket.addEventListener('open',done));
    let id=0;
    const pending=new Map();
    const send=(method,params={})=>new Promise((done,fail)=>{
        const next=++id, timer=setTimeout(()=>{pending.delete(next);fail(Error(method+' timed out'));},15000);
        pending.set(next,{done,fail,timer}); socket.send(JSON.stringify({id:next,method,params}));
    });
    socket.addEventListener('message',event=>{
        const m=JSON.parse(event.data);
        if(m.method==='Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text);
        const task=pending.get(m.id); if(!task)return;
        pending.delete(m.id);clearTimeout(task.timer);
        if(m.error)task.fail(Error(m.error.message));else task.done(m.result);
    });
    const evaluate=async expression=>{
        const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
        if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);
        return r.result.value;
    };
    const sleep=ms=>new Promise(done=>setTimeout(done,ms));
    const wait=async expression=>{
        for(let i=0;i<100;i++){if(await evaluate(expression))return;await sleep(50);}
        throw Error('Did not settle: '+expression);
    };

    await send('Network.enable');await send('Page.enable');await send('Runtime.enable');
    await send('Emulation.setFocusEmulationEnabled',{enabled:true});
    await send('Network.setCacheDisabled',{cacheDisabled:true});
    await send('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
    socket.addEventListener('message',event=>{
      const m=JSON.parse(event.data);if(m.method!=='Fetch.requestPaused')return;
      const p=m.params, local=new URL(p.request.url).origin===base;
      if(!local)external.push(p.request.url);
      send(local?'Fetch.continueRequest':'Fetch.failRequest',local?{requestId:p.requestId}:{requestId:p.requestId,errorReason:'BlockedByClient'}).catch(()=>{});
    });
    const navigate=async path=>{await send('Page.navigate',{url:base+path});await wait(`location.pathname===${JSON.stringify(path)} && document.readyState==='complete' && !!window.BoniraFeedback`);await evaluate('document.fonts.ready.then(()=>true)');};
    const click=async selector=>{
      const p=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});
    };
    const shot=async name=>{await sleep(180);const s=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(output,name+'.png'),Buffer.from(s.data,'base64'));};
    const close=async()=>{await evaluate('Swal.close()');await wait('!Swal.isVisible()');await sleep(80);};
    for(const width of [1440,1024,390]){
      await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width===390});
      await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
      await navigate('/');posts=[];
      assert.equal(await evaluate(`document.documentElement.dir==='rtl' && document.fonts.check('14px Vazirmatn') && document.documentElement.scrollWidth<=innerWidth+1`),true);
      // Native required validation precedes confirmation and does not notify success.
      await click('#save button');await sleep(120);assert.equal(posts.length,0);assert.equal(await evaluate('Swal.isVisible()'),false);
      await evaluate(`document.querySelector('#title').value='اطلاعات آزمایشی';document.querySelector('#save button').focus()`);
      await click('#save button');await wait('Swal.isVisible()');
      assert.equal(await evaluate('document.activeElement===Swal.getCancelButton()'),true);
      await shot(`confirmation-${width}`);
      await click('.swal2-cancel');await wait('!Swal.isVisible()');assert.equal(posts.length,0);
      await wait(`document.activeElement===document.querySelector('#save button') && document.querySelector('#title').value==='اطلاعات آزمایشی'`);
      await click('#save button');await wait('Swal.isVisible()');
      await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await wait('!Swal.isVisible()');assert.equal(posts.length,0);
      await click('#save button');await wait('Swal.isVisible()');
      await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
      assert.equal(await evaluate('Swal.getPopup().contains(document.activeElement)'),true);
      await click('.swal2-confirm');await wait(`location.pathname==='/save' && document.readyState==='complete' && Swal.isVisible() && Swal.getPopup().classList.contains('swal2-toast')`);
      assert.equal(posts.length,1);assert.match(posts[0].body,/decision=save/);
      await shot(`success-${width}`);
      assert.equal(await evaluate(`document.querySelector('[data-feedback-level]').hidden && getComputedStyle(Swal.getPopup()).direction==='rtl' && Swal.getTitle().textContent==='اطلاعات با موفقیت ثبت شد.'`),true);
      await evaluate(`document.dispatchEvent(new CustomEvent('htmx:afterSwap'));document.dispatchEvent(new CustomEvent('htmx:oobAfterSwap'))`);
      await close();await evaluate(`document.dispatchEvent(new CustomEvent('htmx:afterSwap'))`);await sleep(150);assert.equal(await evaluate('Swal.isVisible()'),false);
      await click('#failure button');await wait(`location.pathname==='/fail' && document.readyState==='complete' && Swal.isVisible()`);await shot(`error-${width}`);await close();
      for(const level of ['warning','info']){
        await evaluate(`BoniraFeedback.${level}(${JSON.stringify(level==='warning'?'پیش از ادامه اطلاعات را بررسی کنید.':'اطلاعات به‌روزرسانی شد.')})`);await wait('Swal.isVisible()');await shot(`${level}-${width}`);await close();
      }
      await click('#validation button');await wait(`location.pathname==='/validation' && document.readyState==='complete'`);
      assert.equal(await evaluate(`document.activeElement.matches('[data-form-errors]') && document.querySelector('[aria-invalid="true"]')!==null && !Swal.isVisible()`),true);await shot(`validation-${width}`);
      await navigate('/');posts=[];
      await click('#hx button');await wait('Swal.isVisible()');await click('.swal2-cancel');await wait('!Swal.isVisible()');assert.equal(posts.length,0);
      await click('#hx button');await wait('Swal.isVisible()');await click('.swal2-confirm');
      await wait(`!!document.querySelector('#hx-target p') && Swal.isVisible() && Swal.getPopup().classList.contains('swal2-toast')`);
      assert.equal(posts.length,1);assert.match(posts[0].body,/choice=keep/);await shot(`htmx-success-${width}`);await close();
      await evaluate(`document.querySelector('#hx').setAttribute('hx-post','/partial-fail');document.querySelector('#hx').removeAttribute('hx-confirm');htmx.process(document.querySelector('#hx'));`);
      await click('#hx button');await wait('Swal.isVisible()');
      assert.equal(await evaluate(`!document.body.textContent.includes('PRIVATE SQL') && !document.querySelector('#hx').hasAttribute('aria-busy') && Swal.getTitle().textContent.includes('وضعیت اطلاعات تغییر')`),true);await shot(`htmx-conflict-${width}`);await close();
      await evaluate(`document.querySelector('#hx').setAttribute('hx-post','/silent');htmx.process(document.querySelector('#hx'));`);await click('#hx button');await wait(`document.querySelector('#hx-target').textContent.includes('بدون اعلان')`);assert.equal(await evaluate('Swal.isVisible()'),false);
      for(const state of ['empty','badge','403','404','500']){await navigate('/'+state);assert.equal(await evaluate('Swal.isVisible()'),false);await shot(`${state}-${width}`);}
      results.push({width,checks:['RTL/font/no overflow','native validation','cancel/Escape zero POST','focus default/trap/restore','confirmed named POST once','Django success/error','warning/info','no duplicate replay','inline validation focus','real HTMX confirmation/cancel/OOB/success/conflict/unlock','HTTP 2xx without success stays silent','empty/badge/403/404/500 inline']});
    }
    await navigate('/');
    await evaluate(`document.querySelector('#title').focus();BoniraFeedback.info('آزمون تمرکز')`);await wait(`Swal.isVisible() && Swal.getPopup().dataset.feedbackLevel==='info'`);
    assert.equal(await evaluate(`document.activeElement===document.querySelector('#title')`),true);
    const focused = await evaluate(`(()=>{const button=Swal.getCloseButton();button.focus();return {active:document.activeElement===button, running:Swal.isTimerRunning(), element:document.activeElement.outerHTML.slice(0,300), button:button.outerHTML};})()`);
    assert.ok(focused.active && !focused.running, JSON.stringify(focused));
    const paused=await evaluate('Swal.getTimerLeft()');await sleep(250);assert.ok(Math.abs(paused-await evaluate('Swal.getTimerLeft()'))<40);await close();
    await evaluate(`BoniraFeedback.alert('warning','اطلاعات را بازبینی کنید.','نیاز به بررسی')`);await wait('Swal.isVisible()');
    assert.equal(await evaluate(`Swal.getPopup().getAttribute('role')==='dialog' && !Swal.getPopup().classList.contains('swal2-toast')`),true);
    await shot('interactive-alert-390');await click('.swal2-confirm');await wait('!Swal.isVisible()');
    // Text safety, notification queue ordering and singleton event handlers.
    await evaluate(`BoniraFeedback.info('<img src=x onerror=alert(1)>');BoniraFeedback.warning('پیام دوم');`);await wait('Swal.isVisible()');assert.equal(await evaluate(`Swal.getTitle().textContent==='<img src=x onerror=alert(1)>' && !Swal.getTitle().querySelector('img')`),true);await evaluate('Swal.close()');await wait(`Swal.isVisible() && Swal.getTitle().textContent==='پیام دوم'`);await close();
    await evaluate(`(()=>{const s=document.createElement('script');s.src='/static/js/erp_interactions.js';document.head.append(s)})()`);await sleep(150);
    // Slow native submission: repeat synchronous submits and clicks must send one POST.
    await evaluate(`document.querySelector('#save').removeAttribute('data-confirm-title');document.querySelector('#title').value='آزمون';const f=document.querySelector('#save'),b=f.querySelector('button');f.requestSubmit(b);f.requestSubmit(b);b.click();`);
    await wait(`location.pathname==='/save' && document.readyState==='complete' && Swal.isVisible()`);assert.equal(posts.filter(p=>p.path==='/save').length,1);await close();
    // Missing vendor: readable Django fallback and confirmed operation fails closed.
    await send('Network.setBlockedURLs',{urls:['*sweetalert2.min.js*']});await navigate('/save');
    assert.equal(await evaluate(`!window.Swal && !document.querySelector('[data-feedback-level]').hidden`),true);
    const before=posts.length;await evaluate(`document.querySelector('#title').value='آزمون'`);await click('#save button');await sleep(180);assert.equal(posts.length,before);assert.equal(await evaluate(`!!document.querySelector('.erp-feedback-fallback')`),true);await shot('vendor-failure-390');
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    await writeFile(join(output,'results.json'),JSON.stringify({chrome:await send('Browser.getVersion'),results,errors,external,posts,htmxTestOnly:'2.0.11; official SHA384 verified'},null,2));
    console.log(JSON.stringify({widths:results.length,checks:results,errors,external}));
} finally {
    socket?.close();chrome.kill();await new Promise(done=>chrome.once('exit',done));
    server.closeAllConnections();await new Promise(done=>server.close(done));
    if(!resolve(profile).startsWith(resolve(tmpdir())+sep)||!profile.includes('bonira-stage6-'))throw Error('Unsafe profile path');
    await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
