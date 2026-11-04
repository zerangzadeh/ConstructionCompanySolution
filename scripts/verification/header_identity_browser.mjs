// Real Django-rendered shared header; synthetic local fixtures, no database writes.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdtemp, rm} from 'node:fs/promises';
import {createServer} from 'node:http';
import {tmpdir} from 'node:os';
import {basename, dirname, join, resolve} from 'node:path';

const output = resolve(process.argv[2]);
const root = process.cwd();
const routes = JSON.parse(await readFile(join(output, 'routes.json'), 'utf8'));
const shells = {
    '/': await readFile(join(output, 'shell.html'), 'utf8'),
    '/fallback': await readFile(join(output, 'fallback.html'), 'utf8'),
    '/contracts': await readFile(join(output, 'contracts.html'), 'utf8'),
};
// Small synthetic image fixture; the actual protected profile-image URL is retained.
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS1kAAAAASUVORK5CYII=', 'base64');
const server = createServer(async (req, res) => {
    const path = new URL(req.url, 'http://localhost').pathname;
    if (path === '/favicon.ico') { res.writeHead(204).end(); return; }
    if (path === routes.avatar) { res.writeHead(200, {'Content-Type': 'image/png'}).end(png); return; }
    if (path.startsWith('/static/')) {
        const name = path.slice(8);
        if (name.includes('..')) { res.writeHead(400).end(); return; }
        try {
            const bytes = await readFile(join(root, 'apps/accounts/static', name));
            res.setHeader('Content-Type', name.endsWith('.css') ? 'text/css' : name.endsWith('.js') ? 'text/javascript' : 'font/woff2');
            res.end(bytes);
        } catch { res.writeHead(404).end(); }
        return;
    }
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'}).end(shells[path] || shells['/']);
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}`;
const profile = await mkdtemp(join(tmpdir(), 'bonira-header-identity-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
    '--headless=new', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, 'about:blank',
], {stdio: 'ignore', windowsHide: true});
let socket;
const results = [], errors = [];
try {
    let port;
    for (let i = 0; i < 100; i++) {
        try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; } catch {}
        await new Promise(done => setTimeout(done, 100));
    }
    assert.ok(port, 'Headless Chrome started');
    const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p => p.type === 'page');
    socket = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise(done => socket.addEventListener('open', done));
    let id = 0;
    const pending = new Map();
    const send = (method, params = {}) => new Promise((done, fail) => {
        const next = ++id;
        const timer = setTimeout(() => { pending.delete(next); fail(Error(method + ' timed out')); }, 15000);
        pending.set(next, {done, fail, timer});
        socket.send(JSON.stringify({id: next, method, params}));
    });
    socket.addEventListener('message', event => {
        const message = JSON.parse(event.data);
        if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
        const task = pending.get(message.id);
        if (!task) return;
        pending.delete(message.id);
        clearTimeout(task.timer);
        if (message.error) task.fail(Error(message.error.message)); else task.done(message.result);
    });
    const evaluate = async expression => {
        const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
        if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        return result.result.value;
    };
    const wait = async expression => {
        for (let i = 0; i < 100; i++) {
            if (await evaluate(expression)) return;
            await new Promise(done => setTimeout(done, 50));
        }
        throw Error('Did not settle: ' + expression);
    };
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Page.bringToFront');
    await send('Page.navigate', {url: base + '/'});
    await wait('document.readyState === "complete" && !!document.querySelector("[data-header-profile]")');
    await evaluate('document.fonts.ready');
    for (const width of [1440, 1024, 768, 640, 390, 320]) {
        await send('Emulation.setDeviceMetricsOverride', {width, height: 900, deviceScaleFactor: 1, mobile: false});
        await evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))');
        const geometry = await evaluate(`(() => {
            const header = document.querySelector('header.sticky');
            const desktop = document.querySelector('[data-header-profile-desktop]');
            const mobile = document.querySelector('[data-header-profile-mobile]');
            const visible = innerWidth >= 768 ? desktop : mobile;
            const avatar = visible.querySelector('img, summary > span');
            const h = header.getBoundingClientRect(), p = visible.getBoundingClientRect();
            return {overflow: document.documentElement.scrollWidth > innerWidth, height: h.height,
                fits: p.top >= h.top && p.bottom <= h.bottom && p.left >= 0 && p.right <= innerWidth,
                avatarWidth: avatar.getBoundingClientRect().width,
                imageLoaded: !avatar.matches('img') || avatar.complete && avatar.naturalWidth > 0,
                settings: desktop.getAttribute('href')};
        })()`);
        assert.equal(geometry.overflow, false, `${width}px: horizontal overflow`);
        assert.equal(geometry.fits, true, `${width}px: profile fits header`);
        assert.equal(geometry.avatarWidth, width >= 768 ? 56 : 40, `${width}px: avatar size`);
        assert.equal(geometry.imageLoaded, true, `${width}px: protected image source loaded`);
        assert.equal(geometry.settings, routes.settings);
        if (width < 768) {
            await evaluate(`document.querySelector('[data-header-profile-mobile] summary').focus()`);
            await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', text: '\r', windowsVirtualKeyCode: 13});
            await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13});
            await wait(`document.querySelector('[data-header-profile-mobile]').open`);
            const disclosure = await evaluate(`(() => {
                const menu = document.querySelector('[data-header-profile-mobile] > div');
                const r = menu.getBoundingClientRect();
                return {fits: r.left >= 0 && r.right <= innerWidth,
                    text: menu.innerText, href: menu.querySelector('a').getAttribute('href')};
            })()`);
            assert.equal(disclosure.fits, true, `${width}px: disclosure fits viewport`);
            for (const label of ['علی رضایی', 'مدیر شرکت', 'سرپرست اجرا', 'تنظیمات شخصی']) assert.ok(disclosure.text.includes(label));
            assert.equal(disclosure.href, routes.settings);
        }
        const shot = await send('Page.captureScreenshot', {format: 'png'});
        await writeFile(join(output, `header-${width}.png`), Buffer.from(shot.data, 'base64'));
        await evaluate(`document.querySelector('[data-header-profile-mobile]').open = false`);
        results.push({width, ...geometry});
    }
    // Long multi-role and position labels must not grow the page or be clipped in the mobile disclosure.
    await evaluate(`document.querySelectorAll('[data-header-profile] [title]').forEach(e => { e.textContent = e.title = 'عنوان طولانی آزمایشی برای نقش و سمت سازمانی در شرکت ساختمانی، مسئول کنترل پروژه و امور اجرایی'; })`);
    await send('Emulation.setDeviceMetricsOverride', {width: 390, height: 900, deviceScaleFactor: 1, mobile: false});
    await evaluate(`document.querySelector('[data-header-profile-mobile]').open = true`);
    assert.equal(await evaluate(`document.documentElement.scrollWidth <= innerWidth && Array.from(document.querySelectorAll('[data-header-profile-mobile] [title]')).every(e => e.scrollWidth <= e.clientWidth)`), true, 'Long labels wrap in mobile disclosure');
    await writeFile(join(output, 'header-long-labels.png'), Buffer.from((await send('Page.captureScreenshot', {format: 'png'})).data, 'base64'));
    await send('Page.navigate', {url: base + '/contracts'});
    await wait('document.readyState === "complete" && !!document.querySelector(".erp-list-context--header")');
    for (const width of [1440, 1024, 768, 640, 390, 320]) {
        await send('Emulation.setDeviceMetricsOverride', {width, height: 900, deviceScaleFactor: 1, mobile: false});
        await evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))');
        const variant = await evaluate(`(() => {
            const profile = document.querySelector('[data-header-profile]');
            const context = document.querySelector('.erp-list-context--header');
            const p = profile.getBoundingClientRect(), c = context.getBoundingClientRect();
            return {overflow: document.documentElement.scrollWidth > innerWidth,
                fits: p.left >= 0 && p.right <= innerWidth,
                overlaps: p.right > c.left && p.left < c.right};
        })()`);
        assert.equal(variant.overflow, false, `${width}px: list header has no horizontal overflow`);
        assert.equal(variant.fits, true, `${width}px: list profile fits viewport`);
        assert.equal(variant.overlaps, false, `${width}px: profile and working-context control do not overlap`);
        if (width < 768) {
            await evaluate(`document.querySelector('.erp-list-context--header').open = true`);
            assert.equal(await evaluate(`document.querySelector('.erp-list-context__panel').getBoundingClientRect().top >= document.querySelector('header.sticky').getBoundingClientRect().bottom`), true, 'Context panel remains below compact header');
            await evaluate(`document.querySelector('.erp-list-context--header').open = false`);
        }
    }
    await send('Page.navigate', {url: base + '/fallback'});
    await wait('document.readyState === "complete" && !document.querySelector("[data-header-profile] img")');
    assert.equal(await evaluate(`document.querySelector('[data-header-profile-mobile] summary > span').innerText`), 'H');
    assert.deepEqual(errors, [], 'No JavaScript exceptions');
    await writeFile(join(output, 'browser-results.json'), JSON.stringify({results, keyboardDisclosure: 'PASS', longLabels: 'PASS', fallbackAvatar: 'PASS', listHeader: 'PASS', javascriptErrors: errors}, null, 2));
    console.log(`${results.length} viewports, protected image/fallback, keyboard disclosure, settings URLs, long labels: PASS`);
} finally {
    socket?.close();
    chrome.kill();
    await new Promise(done => server.close(done));
    const cleanupTarget = resolve(profile);
    assert.equal(dirname(cleanupTarget), resolve(tmpdir()));
    assert.ok(basename(cleanupTarget).startsWith('bonira-header-identity-'));
    for (let i = 0; i < 20; i++) {
        try { await rm(cleanupTarget, {recursive: true, force: true}); break; } catch {}
        await new Promise(done => setTimeout(done, 100));
    }
}
