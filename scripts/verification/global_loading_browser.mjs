// Real shared Django layout + installed Chrome; isolated local HTTP fixture, no DB.
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile, writeFile, mkdtemp, rm} from 'node:fs/promises';
import {join, resolve, sep} from 'node:path';
import {tmpdir} from 'node:os';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2]);
const root = process.cwd();
const fixture = `<section class="erp-surface p-6"><h1 class="text-xl font-bold">پروژه‌های ساختمانی</h1><p>نمای آزمایشی پوسته مشترک بنیرا</p><a id="slow" href="/slow">پروژه‌ها</a> <a id="fast" href="/fast">خانه</a> <a id="failure" href="/failure">پاسخ ناموفق</a><a id="hash" href="#section">بخش صفحه</a><a id="download" href="/download" download>دریافت</a><form id="form" action="/slow"><button id="submit">ثبت</button><span id="local" hidden>در حال ثبت</span></form><div id="section"></div></section>`;
const shell = (await readFile(join(output, 'shell.html'), 'utf8')).replace('</main>', fixture + '</main>');
const server = createServer(async (req, res) => {
    const path = new URL(req.url, 'http://localhost').pathname;
    if (path === '/favicon.ico') {res.writeHead(204).end(); return;}
    if (path === '/download') {res.writeHead(200, {'Content-Disposition':'attachment; filename=test.txt'}).end('test'); return;}
    if (path.startsWith('/static/')) {
        try {
            const name = path.slice(8);
            if (name.includes('..')) throw Error('Invalid fixture asset');
            const bytes = await readFile(join(root, 'apps/accounts/static', name));
            res.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'font/woff2');
            res.end(bytes);
        } catch {res.writeHead(404).end();}
        return;
    }
    if (['/slow', '/xhr'].includes(path)) await new Promise(done => setTimeout(done, 900));
    res.writeHead(path === '/failure' ? 500 : 200, {'Content-Type':'text/html; charset=utf-8'}).end(shell);
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}`;
const profile = await mkdtemp(join(tmpdir(), 'bonira-loading-'));
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
    const hidden=()=>evaluate('document.querySelector("[data-global-loading-bar]").hidden');
    const record=name=>results.push(name);
    const navigate=async path=>{
        await send('Page.navigate',{url:base+path});
        await wait('document.readyState==="complete" && !!window.BoniraLoading');
    };
    await send('Page.enable'); await send('Runtime.enable');
    await navigate('/');
    await evaluate(`window.bar=document.querySelector('[data-global-loading-bar]');window.api=BoniraLoading`);
    assert.equal(await hidden(),true);
    await evaluate('window.fast=api.start();fast.finish()'); await sleep(300);
    assert.equal(await hidden(),true); record('fast async operation: no flash');
    await evaluate('window.a=api.start();window.b=api.start()'); await sleep(290);
    assert.equal(await hidden(),false);
    await evaluate('a.finish()');assert.equal(await hidden(),false);
    await evaluate('b.finish()');assert.equal(await evaluate('bar.dataset.state'),'complete');await sleep(220);
    assert.equal(await hidden(),true);record('overlap: visible until last completion, success finish');
    await evaluate('window.a=api.start();a.progress(37)');await sleep(280);
    assert.equal(await evaluate('bar.getAttribute("aria-valuenow")'),'37');
    await evaluate('window.b=api.start()');assert.equal(await evaluate('bar.hasAttribute("aria-valuenow")'),false);
    await evaluate('b.cancel();a.cancel()');assert.equal(await hidden(),true);record('reliable determinate progress; mixed/concurrent indeterminate');
    await evaluate('window.controller=new AbortController();window.a=api.start({signal:controller.signal})');await sleep(280);
    await evaluate('controller.abort()');assert.equal(await hidden(),true);record('AbortSignal cancellation');
    await evaluate('window.a=api.start({timeoutMs:1000})');await sleep(1100);
    assert.equal(await hidden(),true);record('stale task watchdog');
    // HTMX hooks with real XHR: no HTMX library currently shipped in this shell.
    for(const [path,abort,local] of [['/xhr',false,false],['/failure',false,false],['/xhr',true,false],['/xhr',false,true]]){
        await evaluate(`window.xhr=new XMLHttpRequest();xhr.open('GET',${JSON.stringify(path)});document.dispatchEvent(new CustomEvent('htmx:beforeSend',{detail:{xhr,target:document.querySelector(${JSON.stringify(local?'#section':'#main-content')}),elt:document.querySelector('#slow')}}));xhr.send()`);
        await sleep(300);
        assert.equal(await hidden(),!(path==='/xhr'&&!local));
        if(abort)await evaluate('xhr.abort()');else await wait('xhr.readyState===4');
        await sleep(230);assert.equal(await hidden(),true);
    }
    record('primary HTMX: slow, failed, aborted, local target excluded');
    // Layout + reduced-motion checks and review captures in real Chrome.
    for(const width of [1440,390]){
        await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width===390});
        const before=await evaluate('JSON.stringify(document.querySelector("main").getBoundingClientRect().toJSON())');
        await evaluate('window.a=api.start()');await sleep(650);
        const geometry=await evaluate(`(()=>{const r=bar.getBoundingClientRect(),h=document.querySelector('header').getBoundingClientRect();return {height:r.height,top:r.top,bottom:h.bottom,width:r.width,headerWidth:h.width,color:getComputedStyle(bar.firstElementChild).backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth}})()`);
        assert.equal(geometry.height,3);assert.equal(geometry.top,geometry.bottom);assert.equal(geometry.width,geometry.headerWidth);
        assert.equal(geometry.color,'rgb(21, 99, 214)');assert.equal(geometry.overflow,false);
        assert.equal(await evaluate('JSON.stringify(document.querySelector("main").getBoundingClientRect().toJSON())'),before);
        const shot=await send('Page.captureScreenshot',{format:'png'});
        await writeFile(join(output,`rtl-${width}.png`),Buffer.from(shot.data,'base64'));
        await evaluate('a.cancel()');
    }
    record('RTL desktop/mobile: 3px, primary blue, under header, no shift/overflow');
    await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
    await evaluate('window.a=api.start()');await sleep(280);
    assert.equal(await evaluate('getComputedStyle(bar.firstElementChild).animationName'),'none');
    await evaluate('a.finish()');assert.equal(await hidden(),true);record('reduced motion');
    await send('Emulation.setEmulatedMedia',{features:[]});
    for(const fallback of [false,true]){
        let script;
        if(fallback)script=await send('Page.addScriptToEvaluateOnNewDocument',{source:'Object.defineProperty(window,"navigation",{value:undefined})'});
        await navigate('/');
        await evaluate(`sessionStorage.removeItem('loading-observed');new MutationObserver(()=>{if(!document.querySelector('[data-global-loading-bar]').hidden)sessionStorage.setItem('loading-observed','true')}).observe(document.querySelector('[data-global-loading-bar]'),{attributes:true,attributeFilter:['hidden']});setTimeout(()=>document.querySelector("#slow").click(),0)`);
        await wait('location.pathname==="/slow" && document.readyState==="complete"');assert.equal(await hidden(),true);
        assert.equal(await evaluate('sessionStorage.getItem("loading-observed")'),'true',`slow navigation (${fallback?'fallback':'native'})`);
        await evaluate(`sessionStorage.removeItem('fast-flash');new MutationObserver(()=>{if(!document.querySelector('[data-global-loading-bar]').hidden)sessionStorage.setItem('fast-flash','true')}).observe(document.querySelector('[data-global-loading-bar]'),{attributes:true,attributeFilter:['hidden']});setTimeout(()=>document.querySelector("#fast").click(),0)`);
        await wait('location.pathname==="/fast" && document.readyState==="complete"');assert.equal(await hidden(),true);
        assert.equal(await evaluate('sessionStorage.getItem("fast-flash")'),null,'fast navigation must not flash');
        await evaluate('history.back()');await wait('location.pathname==="/slow" && document.readyState==="complete"');assert.equal(await hidden(),true);
        await evaluate('history.forward()');await wait('location.pathname==="/fast" && document.readyState==="complete"');assert.equal(await hidden(),true);
        await evaluate('document.querySelector("#hash").click()');await sleep(300);assert.equal(await hidden(),true);
        await evaluate('document.querySelector("#download").click()');await sleep(300);assert.equal(await hidden(),true);
        await evaluate(`document.querySelector('#form').addEventListener('submit',e=>e.preventDefault(),{once:true});document.querySelector('#submit').click()`);
        await sleep(300);assert.equal(await hidden(),true);
        await evaluate(`document.querySelector('#form').addEventListener('submit',()=>{document.querySelector('#local').hidden=false;document.querySelector('#submit').disabled=true;sessionStorage.setItem('local-feedback',String(document.querySelector('#submit').disabled&&!document.querySelector('#local').hidden))});setTimeout(()=>document.querySelector('#submit').click(),0)`);
        // Chrome may resolve new Runtime.evaluate commands in the incoming document.
        await wait('location.pathname==="/slow" && document.readyState==="complete"');assert.equal(await hidden(),true);
        assert.equal(await evaluate('sessionStorage.getItem("local-feedback")'),'true');
        await evaluate('document.querySelector("#failure").click()');await wait('location.pathname==="/failure" && document.readyState==="complete"');assert.equal(await hidden(),true);
        record(`${fallback?'fallback':'Navigation API'}: slow/fast links, back/forward, hash/download exclusion, cancelled submit, local submit feedback, failed response`);
        if(!fallback){
            await evaluate(`setTimeout(()=>document.querySelector('#slow').click(),0);setTimeout(()=>window.stop(),400)`);
            await sleep(700);assert.equal(await hidden(),true);
            record('Navigation API: stopped in-flight navigation cleans up');
        }
        if(script)await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:script.identifier});
    }
    assert.deepEqual(errors,[]);
    await writeFile(join(output,'results.json'),JSON.stringify({chrome:await send('Browser.getVersion'),results,errors},null,2));
    console.log(JSON.stringify({checks:results.length,results}));
} finally {
    socket?.close();chrome.kill();
    await new Promise(done=>chrome.once('exit',done));
    server.closeAllConnections();await new Promise(done=>server.close(done));
    if(!resolve(profile).startsWith(resolve(tmpdir())+sep)||!profile.includes('bonira-loading-'))throw Error('Unsafe profile path');
    await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
