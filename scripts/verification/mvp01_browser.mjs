// Real Chrome/CDP probe against a Django isolated test database and live server.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createServer } from 'node:net';

const [base, outputDirectory, actor] = process.argv.slice(2);
const scenarios = JSON.parse(process.env.MVP01_SCENARIOS);
const cookie = process.env.MVP01_SESSION;
if (!base || !outputDirectory || !cookie) throw new Error('Missing probe input');
const listener = createServer();
await new Promise(done => listener.listen(0, '127.0.0.1', done));
const port = listener.address().port;
await new Promise(done => listener.close(done));
const profile = await mkdtemp(join(tmpdir(), 'bonira-mvp01-'));
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
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Network.responseReceived' && message.params.type === 'Document') {
      documentStatus = message.params.response.status;
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
  const results = [];
  for (const scenario of scenarios) {
    const width = scenario.mobile ? 390 : 1440;
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: !!scenario.mobile });
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
    }
    if (scenario.screenshot) {
      const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
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
  if (resolve(profile).startsWith(resolve(tmpdir()) + '\\bonira-mvp01-')) {
    await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  }
}
