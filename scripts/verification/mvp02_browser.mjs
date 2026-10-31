// Real Chrome/CDP probe against a Django isolated test database and live server.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createServer } from 'node:net';

const [base, outputDirectory, actor] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.MVP02_SCENARIOS);
const cookie = process.env.MVP02_SESSION;
if (!base || !outputDirectory || !cookie) throw new Error('Missing probe input');
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-mvp02-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true });
let socket;
try {
  let page;
  for (let i = 0; i < 80; i++) {
    try {
      page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p => p.type === 'page');
      if (page) break;
    } catch { /* starting */ }
    await new Promise(done => setTimeout(done, 100));
  }
  if (!page) throw new Error('Chrome unavailable');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true });
    socket.addEventListener('error', fail, { once: true });
  });
  let id = 0;
  let documentStatus;
  const documentStatuses = new Map();
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Network.responseReceived' && message.params.type === 'Document') {
      documentStatus = message.params.response.status;
      documentStatuses.set(message.params.response.url.split('#')[0], documentStatus);
    }
    if (!pending.has(message.id)) return;
    const { done, fail } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) fail(new Error(message.error.message)); else done(message.result);
  });
  const send = (method, params = {}) => new Promise((done, fail) => {
    const next = ++id;
    pending.set(next, { done, fail });
    socket.send(JSON.stringify({ id: next, method, params }));
  });
  const evaluate = async expression => (await send('Runtime.evaluate', { expression, returnByValue: true })).result.value;
  await send('Network.enable');
  await send('Page.enable');
  await send('Network.setCookie', { name: 'sessionid', value: cookie, url: base });
  await mkdir(outputDirectory, { recursive: true });
  const click = async selector => {
    await evaluate(`(() => {const el=document.querySelector(${JSON.stringify(selector)});if(el){const r=el.getBoundingClientRect();if(r.top<0 || r.bottom>innerHeight) el.scrollIntoView({block:'center',behavior:'instant'});}})()`);
    await new Promise(done=>setTimeout(done,50));
    const rect = await evaluate(`(() => {const el=document.querySelector(${JSON.stringify(selector)}); if(!el) return null;const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    if (!rect) {
      const diagnostic = await evaluate(`({path:location.pathname,title:document.title,heading:document.querySelector('main h1')?.textContent,buttons:[...document.querySelectorAll('main button')].map(b=>b.textContent.trim())})`);
      await writeFile(join(outputDirectory,actor+'-missing-control-diagnostic.json'),JSON.stringify({selector,...diagnostic},null,2));
      throw new Error('Missing clickable control '+selector);
    }
    await send('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...rect});
    await send('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...rect});
  };
  const results = [];
  for (const scenario of scenarios) {
    const width = scenario.mobile ? 390 : 1440;
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: !!scenario.mobile });
    await send('Network.setBlockedURLs', {urls: []});
    await send('Emulation.setScriptExecutionDisabled', {value: !!scenario.noJS});
    documentStatus = undefined;
    await send('Page.navigate', { url: new URL(scenario.path, base).href });
    let state;
    for (let i = 0; i < 300; i++) {
      await new Promise(done => setTimeout(done, 100));
      state = await evaluate(`(() => ({
        ready:document.readyState, path:location.pathname,
        lang:document.documentElement.lang, dir:document.documentElement.dir,
        width:document.documentElement.clientWidth, scroll:document.documentElement.scrollWidth,
        links:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')),
        groups:[...document.querySelectorAll('aside [data-surface-group]')].map(g=>g.dataset.surfaceGroup),
        mobileGroups:[...document.querySelectorAll('.erp-mobile-nav [data-surface-group]')].map(g=>g.dataset.surfaceGroup),
        homeGroups:[...document.querySelectorAll('[data-home-group]')].map(g=>g.dataset.homeGroup),
        exception:!!document.querySelector('#traceback'),
      }))()`);
      if (state?.ready === 'complete' && state.path === scenario.path.split('?')[0] && documentStatus) break;
    }
    for (const step of scenario.steps || []) {
      if (step.fill) {
        await evaluate(`(() => {for(const [name,value] of Object.entries(${JSON.stringify(step.fill)})) {
          const scope=document.querySelector(${JSON.stringify(step.formSelector || 'body')});
          const field=scope?.querySelector('[name="'+name+'"]');
          if(!field) throw new Error('Missing form field '+name);
          if(field.tomselect) field.tomselect.setValue(value); else if(field.type==='checkbox') field.checked=!!value; else field.value=value;
          field.dispatchEvent(new Event('input',{bubbles:true}));
          field.dispatchEvent(new Event('change',{bubbles:true}));
        }})()`);
      }
      if(step.clearChoice) {
        documentStatus = undefined;
        await click('select[name="'+step.clearChoice+'"] + .ts-wrapper .ts-control');
        await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Backspace',code:'Backspace',windowsVirtualKeyCode:8});
        await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Backspace',code:'Backspace',windowsVirtualKeyCode:8});
        for(let i=0;i<100;i++) {
          await new Promise(done=>setTimeout(done,100));
          if(documentStatus && await evaluate(`document.readyState==='complete' && !['project','site','employee'].some(name=>new URL(location.href).searchParams.has(name))`)) break;
          if(i===99) {
            const probe=await evaluate(`({url:location.href,ready:document.readyState,fields:[...document.querySelectorAll('main select')].map(s=>({name:s.name,value:s.value,disabled:s.disabled,bound:s.form?.dataset.tableFilterBound,input:s.tomselect?.control_input.value}))})`);
            await writeFile(join(outputDirectory,actor+'-clear-diagnostic.json'),JSON.stringify({documentStatus,probe},null,2));
            throw new Error('Clearing project retained stale URL context '+JSON.stringify(probe));
          }
        }
        continue;
      }
      if(step.emptyLookup) {
        await click('select[name="'+step.emptyLookup+'"] + .ts-wrapper .ts-control');
        await send('Input.insertText',{text:'گزینه‌ای که وجود ندارد'});
        for(let i=0;i<100;i++) {
          await new Promise(done=>setTimeout(done,100));
          if(await evaluate(`(() => {const t=document.querySelector('select[name="'+${JSON.stringify(step.emptyLookup)}+'"]').tomselect;return t.loading===0 && !t.boniraFailed && t.dropdown.textContent.includes('گزینه‌ای یافت نشد.');})()`)) break;
          if(i===99) throw new Error('Empty authorized result not distinguished from a failed lookup');
        }
        continue;
      }
      if(step.searchChoice) {
        const {name,query,value}=step.searchChoice;
        const selector = 'select[name="'+name+'"]';
        await click(selector+' + .ts-wrapper .ts-control');
        await send('Input.dispatchKeyEvent', {type:'keyDown',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});
        await send('Input.dispatchKeyEvent', {type:'keyUp',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});
        await send('Input.insertText', {text:query});
        for(let i=0;i<100;i++) {
          await new Promise(done=>setTimeout(done,100));
          const found=await evaluate(`(() => {const t=document.querySelector(${JSON.stringify(selector)}).tomselect;return t?.isOpen && t.loading===0 && t.control_input.value===${JSON.stringify(query)} && !!t.dropdown.querySelector('[data-value="'+${JSON.stringify(value)}+'"]');})()`);
          // Native fallback matches can appear before the debounced fetch updates
          // the popup. Wait beyond its throttle before measuring a click target.
          if(found && i>=5) break;
          if(i===99) {
            const diagnostic=await evaluate(`(() => {const s=document.querySelector(${JSON.stringify(selector)}),t=s.tomselect;return {name:s.name,value:s.value,search:t.control_input.value,disabled:t.isDisabled,open:t.isOpen,loading:t.loading,active:document.activeElement?.outerHTML,fields:[...s.form.querySelectorAll('select')].map(f=>({name:f.name,value:f.value,disabled:f.disabled,search:f.tomselect?.control_input.value})),scrollY,control:t.control.getBoundingClientRect().toJSON(),dropdown:t.dropdown.getBoundingClientRect().toJSON(),options:[...t.dropdown.querySelectorAll('[data-value]')].map(o=>({value:o.dataset.value,text:o.textContent,rect:o.getBoundingClientRect().toJSON()}))};})()`);
            await writeFile(join(outputDirectory,actor+'-search-diagnostic.json'),JSON.stringify(diagnostic,null,2));
            const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
            await writeFile(join(outputDirectory,actor+'-search-diagnostic.png'),Buffer.from(shot.data,'base64'));
            throw new Error(scenario.name+': integrated search did not resolve '+name);
          }
        }
        if(step.typeOnly) {
          await new Promise(done=>setTimeout(done,900));
          const retained=await evaluate(`document.querySelector(${JSON.stringify(selector)}).tomselect.control_input.value===${JSON.stringify(query)}`);
          if(!retained) throw new Error('Typing inside selector submitted the outer filter form');
          continue;
        }
        if(step.keyboard) {
          await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
          await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        } else await click(selector+' + .ts-wrapper .ts-dropdown [data-value="'+value+'"]');
        if(step.filterChange) {
          for(let i=0;i<100;i++) {
            await new Promise(done=>setTimeout(done,100));
            if(await evaluate(`document.readyState==='complete' && new URL(location.href).searchParams.get('project')===${JSON.stringify(value)} && !new URL(location.href).searchParams.get('site') && !!document.querySelector('main select[name=site]')?.tomselect`)) break;
            if(i===99) throw new Error('Filter context change did not settle');
          }
          continue;
        }
        let selected;
        for(let i=0;i<20;i++) {
          selected = await evaluate(`document.querySelector(${JSON.stringify(selector)}).value`);
          if(selected===value) break;
          await new Promise(done=>setTimeout(done,50));
        }
        if(selected!==value) {
          const diagnostic=await evaluate(`(() => {const s=document.querySelector(${JSON.stringify(selector)}),t=s.tomselect;return {name:s.name,value:s.value,search:t.control_input.value,open:t.isOpen,loading:t.loading,scrollY,viewport:visualViewport?.toJSON?.(),control:t.control.getBoundingClientRect().toJSON(),dropdown:t.dropdown.getBoundingClientRect().toJSON(),options:[...t.dropdown.querySelectorAll('[data-value]')].map(o=>({value:o.dataset.value,rect:o.getBoundingClientRect().toJSON()}))};})()`);
          await writeFile(join(outputDirectory,actor+'-selection-diagnostic.json'),JSON.stringify(diagnostic,null,2));
          const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
          await writeFile(join(outputDirectory,actor+'-selection-diagnostic.png'),Buffer.from(shot.data,'base64'));
          throw new Error(scenario.name+': incorrect chosen '+name+' value '+selected);
        }
        if(step.expectCleared) {
          const cleared = await evaluate(`(${JSON.stringify(step.expectCleared)}).every(name=>!document.querySelector('[name="'+name+'"]').value)`);
          if(!cleared) throw new Error(scenario.name+': stale dependent selection remains');
        }
        if(!step.clickHref && !step.submit) continue;
      }
      if(step.failedLookup) {
        const {name,query}=step.failedLookup;
        await send('Network.setBlockedURLs',{urls:['*workforce/field/choices/*']});
        await click('select[name="'+name+'"] + .ts-wrapper .ts-control');
        await send('Input.insertText',{text:query});
        for(let i=0;i<100;i++) {
          await new Promise(done=>setTimeout(done,100));
          if(await evaluate(`!!document.querySelector('select[name="'+${JSON.stringify(name)}+'"]').tomselect.dropdown.querySelector('[data-choice-retry]')`)) break;
          if(i===99) throw new Error('Failed lookup has no retry state '+JSON.stringify(await evaluate(`(() => {const t=document.querySelector('select[name="'+${JSON.stringify(name)}+'"]').tomselect;return {failed:t.boniraFailed,query:t.lastValue,loading:t.loading,open:t.isOpen,html:t.dropdown.innerHTML};})()`)));
        }
        if(step.recover) {
          await send('Network.setBlockedURLs',{urls:[]});
          await click('select[name="'+name+'"] + .ts-wrapper [data-choice-retry]');
          for(let i=0;i<100;i++) {
            await new Promise(done=>setTimeout(done,100));
            if(await evaluate(`(() => {const t=document.querySelector('select[name="'+${JSON.stringify(name)}+'"]').tomselect;return !t.boniraFailed && t.loading===0 && t.dropdown.querySelectorAll('[data-value]').length>0;})()`)) break;
            if(i===99) throw new Error('Lookup retry did not recover');
          }
        }
        continue;
      }
      if(step.scrollChoices) {
        const name=step.scrollChoices;
        await click('select[name="'+name+'"] + .ts-wrapper .ts-control');
        for(let i=0;i<100;i++) {
          await new Promise(done=>setTimeout(done,100));
          await evaluate(`(() => {const d=document.querySelector('select[name="'+${JSON.stringify(name)}+'"]').tomselect.dropdown_content;d.scrollTop=d.scrollHeight;d.dispatchEvent(new Event('scroll'));})()`);
          if(await evaluate(`Object.keys(document.querySelector('select[name="'+${JSON.stringify(name)}+'"]').tomselect.options).length>=46`)) break;
          if(i===99) throw new Error('Scrolling did not load remaining canonical options');
        }
        continue;
      }
      if(step.openChoice) {
        await click('select[name="'+step.openChoice+'"] + .ts-wrapper .ts-control');
        await new Promise(done=>setTimeout(done,600));
        continue;
      }
      if (step.toggleSelector) {
        await click(step.toggleSelector);
        await new Promise(done=>setTimeout(done,100));
        if (!step.inspect) continue;
      }
      if(step.inspect) {
        if(step.waitMs) await new Promise(done=>setTimeout(done,step.waitMs));
        const passed=await evaluate(step.inspect);
        if(!passed) throw new Error(scenario.name+': '+step.description);
        continue;
      }
      documentStatus = undefined;
      if (step.history) {
        const history = await send('Page.getNavigationHistory');
        const entry = history.entries[history.currentIndex + (step.history === 'back' ? -1 : 1)];
        if (!entry) throw new Error('Missing browser history destination');
        await send('Page.navigateToHistoryEntry', {entryId: entry.id});
        for (let i=0;i<200;i++) {
          await new Promise(done=>setTimeout(done,100));
          if (await evaluate(`document.readyState==='complete' && location.href===${JSON.stringify(entry.url)}`)) break;
          if (i===199) throw new Error('Browser history did not restore the requested URL');
        }
        // BFCache may restore a page without another HTTP response. Retain only
        // its previously observed document status, never invent a success code.
        documentStatus ??= documentStatuses.get(entry.url.split('#')[0]);
        if (!documentStatus) throw new Error('History destination has no observed document response');
        continue;
      } else if (step.reload) {
        await send('Page.reload');
      } else if (step.clickSelector) {
        await click(step.clickSelector);
      } else if (step.clickHref) {
        const clicked = await evaluate(`(() => {const a=[...document.querySelectorAll('a[href]')].find(a=>a.getAttribute('href')===${JSON.stringify(step.clickHref)}); if(!a) return false; a.click(); return true;})()`);
        if(!clicked) throw new Error(scenario.name+': missing journey link '+step.clickHref);
      } else if (step.submit) {
        await evaluate(`document.querySelector(${JSON.stringify(step.formSelector || 'main form[method="post"]')}).requestSubmit()`);
      }
      for(let i=0;i<200;i++) {
        await new Promise(done=>setTimeout(done,100));
        const settled=await evaluate(`({ready:document.readyState,path:location.pathname,text:document.body.innerText})`);
        if(documentStatus && settled?.ready==='complete' && (!step.afterPath || settled.path===step.afterPath) && (!step.afterPrefix || settled.path.startsWith(step.afterPrefix)) && (!step.mustText || settled.text.includes(step.mustText))) break;
        if(i===199) throw new Error(scenario.name+': interaction did not settle '+JSON.stringify(settled));
      }
    }
    state = await evaluate(`(() => ({
      ready:document.readyState,path:location.pathname,lang:document.documentElement.lang,dir:document.documentElement.dir,
      width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
      links:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')),
      groups:[...document.querySelectorAll('aside [data-surface-group]')].map(g=>g.dataset.surfaceGroup),
      mobileGroups:[...document.querySelectorAll('.erp-mobile-nav [data-surface-group]')].map(g=>g.dataset.surfaceGroup),
      exception:!!document.querySelector('#traceback'),
      technicalLabels:[...document.querySelectorAll('select option')].map(o=>o.textContent).filter(t=>/object \\(|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(t)),
    }))()`);
    const visibleText = await evaluate('document.body.innerText');
    if(!scenario.noJS && scenario.status===200) {
      const contract = await evaluate(`(() => {
        const selects=[...document.querySelectorAll('select[data-business-choice]')];
        return {count:selects.length, enhanced:selects.every(s=>s.tomselect && s.closest('[data-field-search]').querySelectorAll('[role="combobox"]').length===1),rejected:!!document.querySelector('[data-choice-search],[data-choice-submit]'), technical:/حداکثر [۴4][۰0] گزینه/.test(document.body.innerText)};
      })()`);
      if(contract.rejected || contract.technical || !contract.enhanced) throw new Error(scenario.name+': selector contract '+JSON.stringify(contract));
      state.selectorContract=contract;
    }
    for(const text of scenario.mustText || []) if(!visibleText.includes(text)) throw new Error(scenario.name+': missing business text '+text);
    for(const text of scenario.absentText || []) if(visibleText.includes(text)) throw new Error(scenario.name+': technical leakage '+text);
    if(state.technicalLabels.length) throw new Error(scenario.name+': technical selector labels');
    if(state.scroll>state.width+1) {
      const overflow = await evaluate(`({width:innerWidth,wide:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width && (r.left < -1 || r.right > innerWidth+1);}).map(e=>({tag:e.tagName,id:e.id,classes:e.className,rect:e.getBoundingClientRect().toJSON()})).slice(0,30)})`);
      await writeFile(join(outputDirectory,actor+'-overflow-diagnostic.json'),JSON.stringify(overflow,null,2));
      const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
      await writeFile(join(outputDirectory,actor+'-overflow-diagnostic.png'),Buffer.from(shot.data,'base64'));
      throw new Error(scenario.name+': horizontal overflow');
    }
    if (documentStatus !== scenario.status) throw new Error(`${scenario.name}: expected ${scenario.status}, got ${documentStatus}`);
    if (state.exception || state.lang !== 'fa' || state.dir !== 'rtl') throw new Error(`${scenario.name}: unsafe or non-RTL page`);
    for (const link of scenario.mustLinks || []) {
      if (!state.links.includes(link)) throw new Error(`${scenario.name}: missing ${link}`);
    }
    for (const link of scenario.absentLinks || []) {
      if (state.links.includes(link)) throw new Error(`${scenario.name}: exposed ${link}`);
    }
    if (scenario.groups && JSON.stringify(state.groups) !== JSON.stringify(scenario.groups)) throw new Error(`${scenario.name}: incorrect groups`);
    if (JSON.stringify(state.groups) !== JSON.stringify(state.mobileGroups)) throw new Error(`${scenario.name}: desktop/mobile differ`);
    if (scenario.path === '/' && state.scroll > state.width + 1) throw new Error(`${scenario.name}: Home overflows`);
    if (scenario.mobile) {
      const opened = await evaluate(`(() => {const n=document.querySelector('.erp-mobile-nav'); n.querySelector('summary').click(); return n.open && n.getBoundingClientRect().width>0;})()`);
      if (!opened) throw new Error(`${scenario.name}: mobile navigation did not open`);
      await evaluate(`document.querySelector('.erp-mobile-nav summary').click()`);
    }
    if (scenario.screenshot) {
      await evaluate('window.scrollTo(0,0)');
      await new Promise(done=>setTimeout(done,120));
      if(scenario.name==='UX-worker-create-desktop') {
        const viewport = await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        await writeFile(join(outputDirectory, `${actor}-${scenario.name}-viewport.png`),Buffer.from(viewport.data,'base64'));
        state.viewportGeometry = await evaluate(`({scrollX,scrollY,innerWidth,sidebar:document.querySelector('aside').getBoundingClientRect().toJSON()})`);
      }
      const layout = await send('Page.getLayoutMetrics');
      const size=layout.cssContentSize;
      const shot = await send('Page.captureScreenshot', scenario.mobile ? {format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:size.width,height:size.height,scale:1}} : {format:'png',captureBeyondViewport:false});
      await writeFile(join(outputDirectory, `${actor}-${scenario.name}.png`), Buffer.from(shot.data, 'base64'));
    }
    results.push({ name: scenario.name, status: documentStatus, ...state });
  }
  await writeFile(join(outputDirectory, `${actor}-results.json`), JSON.stringify(results, null, 2));
  process.stdout.write(JSON.stringify(results));
} finally {
  socket?.close();
  chrome.kill();
  // Guard the exact helper-created directory before recursive cleanup.
  if (resolve(profile).startsWith(resolve(tmpdir()) + '\\bonira-mvp02-')) {
    await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  }
}
