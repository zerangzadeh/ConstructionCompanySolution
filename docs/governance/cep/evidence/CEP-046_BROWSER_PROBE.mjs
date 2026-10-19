// Reuse the repository's isolated Chrome/CDP test-probe pattern; no user profile.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { createServer } from 'node:net';

const [origin, casesJson, outputDir] = process.argv.slice(2);
const cookie = process.env.CEP046_TEST_SESSION;
if (!origin || !casesJson || !outputDir || !cookie) throw new Error('Missing synthetic probe input');
if (!['localhost', '127.0.0.1'].includes(new URL(origin).hostname)) throw new Error('Loopback test server required');
const cases = JSON.parse(casesJson);
const listener = createServer();
await new Promise(resolvePort => listener.listen(0, '127.0.0.1', resolvePort));
const port = listener.address().port;
await new Promise(resolvePort => listener.close(resolvePort));
const profile = await mkdtemp(join(tmpdir(), 'bonira-cep046-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true });
let socket;
try {
  let page;
  for (let attempt = 0; attempt < 60; attempt++) {
    try { page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(item => item.type === 'page'); } catch { /* starting */ }
    if (page) break;
    await new Promise(r => setTimeout(r, 100));
  }
  if (!page) throw new Error('Isolated Chrome unavailable');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((ready, reject) => { socket.addEventListener('open', ready, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  const pending = new Map(); let id = 0; let status = null;
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Network.responseReceived' && message.params.type === 'Document') status = message.params.response.status;
    if (!pending.has(message.id)) return;
    const request = pending.get(message.id); pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
  });
  const send = (method, params = {}) => new Promise((ok, reject) => {
    const requestId = ++id; pending.set(requestId, { resolve: ok, reject });
    socket.send(JSON.stringify({ id: requestId, method, params }));
  });
  await send('Network.enable'); await send('Page.enable');
  await send('Network.setCookie', { name: 'sessionid', value: cookie, url: origin });
  await mkdir(outputDir, { recursive: true });
  const results = [];
  for (const item of cases) {
    const width = item.mobile ? 390 : 1440;
    await send('Emulation.setDeviceMetricsOverride', { width, height: item.mobile ? 844 : 1000, deviceScaleFactor: 1, mobile: !!item.mobile });
    status = null;
    await send('Page.navigate', { url: origin + item.path });
    let observed;
    for (let attempt = 0; attempt < 150; attempt++) {
      await new Promise(r => setTimeout(r, 100));
      const result = await send('Runtime.evaluate', { expression: `(() => ({ready:document.readyState, path:location.pathname, lang:document.documentElement.lang, dir:document.documentElement.dir, viewport:document.documentElement.clientWidth, scroll:document.documentElement.scrollWidth, workspace:${JSON.stringify(item.workspace || '')} ? !!document.querySelector('main [data-workspace-id="${item.workspace || ''}"]') : true, confidentialNameVisible:document.body.innerText.includes('گردش‌کار آزمایشی محرمانه'), financialAuthorities:!!document.querySelector('[data-financial-authorities]')}))()`, returnByValue: true });
      observed = result.result.value;
      if (observed?.ready === 'complete' && observed.path === item.path && status !== null) break;
    }
    if (status !== item.status || observed?.lang !== 'fa' || observed.dir !== 'rtl' || !observed.workspace || observed.scroll > observed.viewport + 1) throw new Error(`${item.name} failed: ${JSON.stringify({status, observed})}`);
    if (item.status !== 200 && observed.confidentialNameVisible) throw new Error('Confidential object name leaked');
    if (item.authorities && !observed.financialAuthorities) throw new Error('Financial source/authority context missing');
    if (item.home) {
      const link = await send('Runtime.evaluate', { expression: `!!document.querySelector('[data-home-state] a[href="/financials/"]')`, returnByValue: true });
      if (link.result.value) throw new Error('Legacy Financials remains a canonical Home link');
    }
    const screenshot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(join(outputDir, `${item.name}.png`), Buffer.from(screenshot.data, 'base64'));
    results.push({ name: item.name, status, ...observed });
  }
  process.stdout.write(JSON.stringify(results));
  await Promise.race([send('Browser.close').catch(() => {}), new Promise(r => setTimeout(r, 1000))]);
} finally {
  socket?.close(); chrome.kill();
  const target = resolve(profile);
  if (dirname(target) !== resolve(tmpdir()) || !basename(target).startsWith('bonira-cep046-')) throw new Error('Unexpected temporary profile path');
  await rm(target, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
