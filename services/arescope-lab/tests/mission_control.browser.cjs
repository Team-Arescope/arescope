/* Real Chromium QA: no production service, account or credentials required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const runtimeRoot = path.join(root, '.runtime'); fs.mkdirSync(runtimeRoot, {recursive: true});
const run = fs.mkdtempSync(path.join(runtimeRoot, 'browser-'));
process.env.TEMP = process.env.TMP = process.env.TMPDIR = run;
const {chromium} = require('playwright');
const base = 'http://127.0.0.1:18965';
const artifacts = path.join(root, 'tests/artifacts'); fs.mkdirSync(artifacts, {recursive: true});
const python = process.env.ARESCOPE_PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const server = spawn(python, ['-B', 'tools/browser_server.py', run], {cwd: root, env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, windowsHide: true});
let serverError = ''; server.stderr.on('data', b => { serverError += b; });
let context;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function request(url, {method = 'GET', body, producer = false, json = false} = {}) {
  const r = await fetch(base + url, {method, headers: {Authorization: `Bearer test-${producer ? 'producer' : 'viewer'}`, ...(json ? {'Content-Type': 'application/json'} : {})}, body: json ? JSON.stringify(body) : body});
  assert.equal(r.status, 200, `${method} ${url}: ${r.status}`); return r;
}
(async () => {
  try {
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(serverError || 'QA server exited');
      try { if ((await fetch(base + '/healthz')).ok) break; } catch {}
      await pause(100);
      if (i === 99) throw new Error('QA server did not bind');
    }
    const executable = process.env.ARESCOPE_BROWSER_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined);
    context = await chromium.launchPersistentContext(path.join(run, 'profile'), {executablePath: executable, headless: true, viewport: {width: 1440, height: 900}, acceptDownloads: true, downloadsPath: path.join(run, 'downloads'), args: ['--enable-unsafe-swiftshader']});
    const page = await context.newPage(); const errors = [], badAssets = [], authorizedDownloads = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', r => { if (r.url().includes('/static/') && r.status() >= 400) badAssets.push(r.url()); });
    page.on('request', r => { if (/export\.ply|\/mesh$/.test(r.url())) authorizedDownloads.push({url: r.url(), auth: r.headers().authorization}); });
    await page.goto(base); await page.waitForSelector('#terrain[data-ready="true"]');
    const deniedCode = await page.evaluate(() => new Promise(resolve => {
      const ws = new WebSocket(`ws://${location.host}/api/live/stream?token=bad`);
      ws.onclose = e => resolve(e.code);
    }));
    assert.equal(deniedCode, 4401, 'Real browsers receive the authentication close code');
    await page.evaluate(() => document.fonts.ready);
    assert.ok(await page.evaluate(() => document.fonts.check('400 13px Manrope') && document.fonts.check('400 11px "DM Mono"')));
    const points = Array.from({length: 384}, (_, i) => [Math.cos(i * .1) * 3, i / 100, Math.sin(i * .1) * 3]);
    const frame = {room: 'Quest room with a long display name to verify wrapping', yawDeg: 28, points};
    const sid = (await (await request('/api/live/frame', {method: 'POST', producer: true, body: frame, json: true})).json()).sessionId;
    const mesh = Buffer.alloc(76); mesh.write('ARSM'); mesh.writeUInt32LE(1, 4); mesh.writeUInt32LE(3, 8); mesh.writeUInt32LE(3, 12); mesh.writeUInt32LE(1, 68); mesh.writeUInt32LE(2, 72);
    await request(`/api/live/mesh?session=${sid}`, {method: 'POST', producer: true, body: mesh});
    await request('/api/live/log?source=device', {method: 'POST', producer: true, body: '[ARS] scan | points=384\nBrowser QA fixture'});
    await page.locator('[data-panel="equipment"]').click();
    await page.locator('#viewer-token').fill('test-viewer'); await page.locator('#connect-form button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('#connection-status').textContent === 'Viewer connected');
    await request('/api/live/frame', {method: 'POST', producer: true, body: frame, json: true});
    await page.waitForSelector('#live-overlay:not([hidden])');
    assert.match(await page.locator('#scan-caption').innerText(), /384 points/);
    await page.locator('[data-panel="sessions"]').click(); await page.waitForSelector('#session-list .card');
    await page.getByRole('button', {name: 'Inspect', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#overlay-title').textContent === 'Quest archive');
    for (const [label, filename, check] of [
      ['Merged PLY', 'browser-merged.ply', b => assert.match(b.toString(), /^ply\nformat ascii 1\.0\n/)],
      ['ARSM mesh', 'browser-mesh.arsm', b => assert.deepEqual(b, mesh)]
    ]) {
      const waiting = page.waitForEvent('download'); await page.getByRole('button', {name: label, exact: true}).click();
      const download = await waiting; const output = path.join(artifacts, filename); await download.saveAs(output); check(fs.readFileSync(output));
    }
    assert.equal(authorizedDownloads.length, 2);
    for (const r of authorizedDownloads) { assert.equal(r.auth, 'Bearer test-viewer'); assert.ok(!r.url.includes('token=')); }
    await page.locator('[data-panel="logs"]').click(); await page.getByRole('button', {name: 'Read log', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#log-preview').textContent.includes('Browser QA fixture'));
    await page.locator('[data-panel="settings"]').click();
    const polygonal = await page.locator('#terrain').screenshot();
    await page.locator('#grid-mode').selectOption('minimal');
    assert.notDeepEqual(await page.locator('#terrain').screenshot(), polygonal, 'Grid modes change the rendered canvas');
    await page.locator('#terrain-select').selectOption('mola');
    await page.waitForFunction(() => document.querySelector('#grid-count').textContent.startsWith('65'));
    await page.locator('#terrain-select').selectOption('hirise'); await page.locator('#grid-mode').selectOption('polygonal');
    await page.waitForFunction(() => document.querySelector('#grid-count').textContent.startsWith('129'));
    assert.equal(await page.locator('#terrain').evaluate(el => el.getContext('webgl').getError()), 0);
    const measurements = [];
    for (const [width, height] of [[1440, 900], [390, 844]]) {
      await page.setViewportSize({width, height});
      for (const pane of ['equipment', 'sessions', 'logs', 'settings']) {
        if (await page.locator(`[data-panel="${pane}"]`).getAttribute('aria-expanded') !== 'true') await page.locator(`[data-panel="${pane}"]`).click();
        const m = await page.locator('#' + pane).evaluate(el => {
          const right = el.getBoundingClientRect().right;
          return {overflow: el.scrollWidth - el.clientWidth, outliers: [...el.querySelectorAll('*')].filter(child => child.getBoundingClientRect().width > 0 && child.getBoundingClientRect().right > right + .5).length, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight};
        });
        assert.equal(m.overflow, 0, `${width} ${pane} horizontal overflow`); assert.equal(m.outliers, 0, `${width} ${pane} overflowing children`);
        if (width === 390 && pane === 'equipment') assert.ok(m.scrollHeight > m.clientHeight, 'Mobile pane scrolls vertically');
        measurements.push({width, pane, ...m});
      }
      await page.locator('[data-panel="equipment"]').click();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.screenshot({path: path.join(artifacts, `mission-${width}.png`)});
      await page.locator('#close-drawer').click();
    }
    await page.setViewportSize({width: 1440, height: 900});
    await page.screenshot({path: path.join(artifacts, 'mission-terrain.png')});
    await page.locator('[data-panel="equipment"]').click(); await page.locator('#disconnect').click();
    assert.equal(await page.locator('#session-list .card').count(), 0);
    assert.ok(await page.locator('#log-preview').isHidden());
    assert.equal(await page.locator('#viewer-token').inputValue(), '');
    assert.deepEqual(errors, []); assert.deepEqual(badAssets, []);
    fs.writeFileSync(path.join(artifacts, 'browser-report.json'), JSON.stringify({ok: true, measurements, pageErrors: errors, failedAssets: badAssets, authenticatedDownloads: authorizedDownloads.length}, null, 2));
    console.log('Browser QA passed: real WebSocket, PLY/ARSM downloads, logs, both terrains and grid modes; 8 pane/viewport checks have zero horizontal overflow and zero overflowing children.');
  } finally {
    if (context) await context.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
