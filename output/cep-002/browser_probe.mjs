// Test-only Chrome DevTools probe for the authenticated CEP-002 Home.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'node:net';

const [url, stateName, outputDir] = process.argv.slice(2);
const cookie = process.env.CEP002_TEST_SESSION;
if (!url || !stateName || !outputDir || !cookie) throw new Error('Missing browser probe input');

const server = createServer();
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
await new Promise((resolve) => server.close(resolve));
const profile = await mkdtemp(join(tmpdir(), 'cep002-chrome-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true });

let socket;
try {
  let page;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      page = pages.find((entry) => entry.type === 'page');
      if (page) break;
    } catch { /* browser starting */ }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (!page) throw new Error('Chrome debugging page unavailable');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  function send(method, params = {}) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  await send('Network.enable');
  await send('Page.enable');
  await send('Network.setCookie', { name: 'sessionid', value: cookie, url });
  await mkdir(outputDir, { recursive: true });
  const results = [];
  for (const [index, [label, width, height, mobile]] of [
    ['desktop', 1440, 900, false], ['mobile', 390, 844, true],
  ].entries()) {
    await send('Emulation.setDeviceMetricsOverride', {
      width, height, deviceScaleFactor: 1, mobile,
    });
    if (index === 0) await send('Page.navigate', { url });
    let result;
    for (let attempt = 0; attempt < 200; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      const evaluated = await send('Runtime.evaluate', {
        expression: `(() => ({ready:document.readyState, state:document.querySelector('[data-home-state]')?.dataset.homeState, lang:document.documentElement.lang, dir:document.documentElement.dir, viewport:document.documentElement.clientWidth, scroll:document.documentElement.scrollWidth, homeLinks:document.querySelectorAll('a[href="/"]').length, profile:!!document.querySelector('a[href="/accounts/settings/"]'), mobileNav:!!document.querySelector('.erp-mobile-nav'), financialLink:!!document.querySelector('a[href="/financials/"]'), testOrgVisible:document.body.innerText.includes('Browser Test Company')}))()`,
        returnByValue: true,
      });
      result = evaluated.result.value;
      if (result?.ready === 'complete' && result?.state === stateName) break;
    }
    if (result?.state !== stateName) throw new Error(`Home did not render ${stateName} at ${label}: ${JSON.stringify(result)}`);
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(join(outputDir, `${stateName}-${label}.png`), Buffer.from(shot.data, 'base64'));
    if (mobile) {
      const nav = await send('Runtime.evaluate', {
        expression: `(() => { const details = document.querySelector('.erp-mobile-nav'); details.querySelector('summary').click(); return {open: details.open, home: !!details.querySelector('a[href="/"]')}; })()`,
        returnByValue: true,
      });
      result.mobileNavOpens = nav.result.value.open && nav.result.value.home;
    }
    results.push({ label, ...result });
  }
  if (stateName === 'normal') {
    await send('Page.navigate', { url: `${new URL(url).origin}/financials/` });
    let separate = false;
    for (let attempt = 0; attempt < 50; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      const evaluated = await send('Runtime.evaluate', {
        expression: `location.pathname === '/financials/' && !document.querySelector('[data-home-state]')`,
        returnByValue: true,
      });
      if (evaluated.result.value) { separate = true; break; }
    }
    if (!separate) throw new Error('Financial workspace did not remain a separate page');
  }
  process.stdout.write(JSON.stringify(results));
} finally {
  socket?.close();
  chrome.kill();
  if (profile.startsWith(join(tmpdir(), 'cep002-chrome-')))
    await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
