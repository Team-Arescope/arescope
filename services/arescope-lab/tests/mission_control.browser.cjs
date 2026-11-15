/* Real Chromium QA: no production service, account or credentials required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const net = require('node:net');
const root = path.resolve(__dirname, '..');
// Track 2 may write only static/ and these two test files.
const runtimeRoot = path.join(root, 'static/.qa'); fs.mkdirSync(runtimeRoot, {recursive: true});
const run = fs.mkdtempSync(path.join(runtimeRoot, 'browser-'));
process.env.TEMP = process.env.TMP = process.env.TMPDIR = run;
const {chromium} = require('playwright');
let base, server;
const artifacts = path.join(runtimeRoot, 'artifacts'); fs.mkdirSync(artifacts, {recursive: true});
const python = process.env.ARESCOPE_PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
let serverError = '';
let context, fixturePulse, liveSocket;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function request(url, {method = 'GET', body, producer = false, json = false} = {}) {
  const r = await fetch(base + url, {method, headers: {Authorization: `Bearer test-${producer ? 'producer' : 'viewer'}`, ...(json ? {'Content-Type': 'application/json'} : {})}, body: json ? JSON.stringify(body) : body});
  assert.equal(r.status, 200, `${method} ${url}: ${r.status}`); return r;
}
(async () => {
  try {
    const port = await new Promise((resolve, reject) => {
      const probe = net.createServer(); probe.on('error', reject);
      probe.listen(0, '127.0.0.1', () => { const port = probe.address().port; probe.close(() => resolve(port)); });
    });
    base = `http://127.0.0.1:${port}`;
    const serverCode = [
      'from pathlib import Path', 'import sys, uvicorn', 'from app import Settings, create_app',
      'runtime = Path(sys.argv[1]).resolve()',
      'settings = Settings(producer_token="test-producer", viewer_token="test-viewer", db=runtime/"live.sqlite3", mesh_dir=runtime/"meshes", log_dir=runtime/"logs", min_history_interval=0)',
      'uvicorn.run(create_app(settings), host="127.0.0.1", port=int(sys.argv[2]), access_log=False, log_level="warning")'
    ].join('\n');
    server = spawn(python, ['-B', '-c', serverCode, run, String(port)], {cwd: root, env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, windowsHide: true});
    server.stderr.on('data', b => { serverError += b; }); server.on('error', e => { serverError += e.message; });
    const bindDeadline = Date.now() + 60_000;
    while (true) {
      if (server.exitCode !== null) throw new Error(serverError || 'QA server exited');
      try { if ((await fetch(base + '/healthz', {signal: AbortSignal.timeout(500)})).ok) break; } catch {}
      await pause(100);
      if (Date.now() >= bindDeadline) throw new Error('QA server did not bind: ' + serverError);
    }
    const executable = process.env.ARESCOPE_BROWSER_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined);
    context = await chromium.launchPersistentContext(path.join(run, 'profile'), {executablePath: executable, headless: true, viewport: {width: 1440, height: 900}, acceptDownloads: true, downloadsPath: path.join(run, 'downloads'), args: ['--enable-unsafe-swiftshader']});
    const page = await context.newPage(); const errors = [], badAssets = [], authorizedDownloads = [];
    const cdp = await context.newCDPSession(page); await cdp.send('Network.setCacheDisabled', {cacheDisabled: true});
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', r => { if (r.url().includes('/static/') && r.status() >= 400) badAssets.push(r.url()); });
    page.on('request', r => { if (/export\.ply|\/mesh$/.test(r.url())) authorizedDownloads.push({url: r.url(), auth: r.headers().authorization}); });
    await page.goto(base); await page.waitForSelector('#terrain[data-ready="true"]');
    await page.locator('[data-panel="guardian"]').click();
    assert.ok(await page.locator('[data-fleet-action="start"]').isDisabled());
    assert.match(await page.locator('#fleet-access-status').innerText(), /Connect a viewer in Equipment and live/);
    assert.ok(await page.locator('#fleet-connect-viewer').isEnabled());
    await page.locator('#fleet-connect-viewer').click();
    assert.equal(await page.locator('[data-panel="equipment"]').getAttribute('aria-expanded'), 'true');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'viewer-token');
    await page.locator('#viewer-token').fill('test-producer');
    await page.locator('#connect-form button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('#live-message').textContent.includes('Token was not accepted'));
    assert.ok(await page.locator('[data-fleet-action="start"]').isDisabled(), 'producer credentials cannot establish viewer access');
    await page.locator('[data-panel="guardian"]').click();
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
    await page.locator('#session-list').getByRole('button', {name: 'Inspect', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#overlay-title').textContent === 'Mast testbed archive');
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
    const terrainFixtures = await Promise.all(['mola', 'hirise'].map(async name => ({name, data: await (await page.request.get(`${base}/static/data/${name}-gale.json`)).json()})));
    const fleetDescription = await page.locator('#fleet-description').textContent();
    for (const {name, data} of terrainFixtures) {
      const {rows, cols} = data.grid, first = data.points[0];
      const east = data.points[cols - 1][0] - first[0], south = data.points[(rows - 1) * cols][2] - first[2];
      const stepX = data.points[1][0] - first[0], stepZ = data.points[cols][2] - first[2];
      const extent = `${(east / 1000).toFixed(2)} × ${(south / 1000).toFixed(2)} km`;
      const samples = `${rows} × ${cols}`, spacing = Math.abs(stepX - stepZ) < .00001 ? `${stepX.toFixed(1)} m` : `${stepX.toFixed(1)} × ${stepZ.toFixed(1)} m`;
      await page.locator('#terrain-select').selectOption(name);
      await page.waitForFunction(count => document.querySelector('#grid-count').textContent === count, `${samples} samples`);
      assert.ok((await page.locator('#terrain-caption').textContent()).includes(extent), `${name} caption follows both physical axes`);
      assert.ok((await page.locator('#terrain-source').textContent()).includes(`${spacing} display step`));
      const notes = await page.locator('#source-notes').textContent();
      assert.ok(notes.includes(`${samples} (rows × columns)`) && notes.includes(extent));
      if (name === 'hirise') {
        assert.ok(notes.includes(`Native spacing: ${data.metadata.native_spacing_m.toFixed(4)} m`));
        const description = await page.locator('#fleet-description').textContent();
        assert.ok(description.includes(samples) && description.includes(spacing) && description.includes(extent));
        assert.ok(description.includes(`${(east * south / 1000000).toFixed(1)} km²`));
      } else assert.equal(await page.locator('#fleet-description').textContent(), fleetDescription, 'regional view retains the HiRISE fleet frame description');
    }
    await page.locator('#grid-mode').selectOption('polygonal');
    assert.equal(await page.locator('#terrain').evaluate(el => el.getContext('webgl').getError()), 0);

    // The real Track 1 backend must support the viewer/operator contracts too.
    await page.locator('[data-panel="guardian"]').click();
    await page.waitForFunction(() => document.querySelector('#guardian-model').textContent !== '—');
    assert.ok(await page.locator('[data-fleet-action="start"]').isDisabled());
    assert.match(await page.locator('#fleet-access-status').innerText(), /Enter a producer token in Operator access/);
    const fleetPoll = page.waitForResponse(r => new URL(r.url()).pathname === '/api/sim/fleet' && r.request().method() === 'GET');
    await page.locator('#refresh-fleet').click(); await fleetPoll;
    assert.match(await page.locator('#fleet-access-status').innerText(), /Enter a producer token in Operator access/, 'polling leaves the next access step visible');
    await page.locator('#fleet-enter-producer').click();
    assert.equal(await page.locator('[data-panel="guardian"]').getAttribute('aria-expanded'), 'true', 'focusing producer access keeps the current panel open');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'producer-token');
    const actualStatus = await (await request('/api/guardian/status')).json();
    assert.equal(await page.locator('#guardian-model').innerText(), actualStatus.modelVersion);
    assert.equal(typeof actualStatus.candidateReady, 'boolean'); assert.ok(actualStatus.simState);
    const modelDownload = page.waitForEvent('download'); await page.locator('#guardian-export').click();
    const exported = await modelDownload; const modelFile = path.join(artifacts, 'guardian-model.json'); await exported.saveAs(modelFile);
    assert.equal(JSON.parse(fs.readFileSync(modelFile)).modelVersion, actualStatus.modelVersion);
    await page.locator('#producer-token').fill('test-viewer');
    const rejectedFleet = page.waitForResponse(r => new URL(r.url()).pathname === '/api/sim/fleet' && r.request().method() === 'POST');
    await page.locator('[data-fleet-action="start"]').click();
    assert.equal((await rejectedFleet).status(), 401, 'a viewer token cannot control the fleet');
    await page.waitForFunction(() => !document.querySelector('[data-fleet-action="start"]').disabled);
    assert.equal((await (await request('/api/sim/fleet')).json()).running, false, 'rejected operator access leaves the fleet stopped');
    await page.locator('#producer-token').fill('test-producer');
    assert.match(await page.locator('#fleet-access-status').innerText(), /Fleet controls are available/);
    assert.ok(await page.locator('#fleet-access-steps').isHidden());
    await page.locator('[data-fleet-action="start"]').click();
    await page.waitForFunction(() => document.querySelector('#fleet-status').textContent.startsWith('Running') && !document.querySelector('[data-fleet-action="stop"]').disabled);
    await page.locator('[data-fleet-action="stop"]').click();
    await page.waitForFunction(() => document.querySelector('#fleet-status').textContent.startsWith('Stopped') && !document.querySelector('[data-fleet-action="start"]').disabled);
    await page.locator('[data-sim-action="step"]').click();
    await page.waitForFunction(() => !document.querySelector('#guardian-retrain').disabled && document.querySelector('#sim-status').textContent.includes('1 steps'));
    await page.locator('[data-sim-fault="sensor_drop"]').click();
    await page.waitForFunction(() => document.querySelector('[data-sim-fault="sensor_drop"]').getAttribute('aria-pressed') === 'true');
    const observed = {room: 'browser-rover', carrierId: 'browser-rover-01', carrierType: 'rover', source: 'simulated-rover', points,
      telemetry: {pointCount: 10, fps: 1, poseJumpM: .95, lumaContrast: .58, slipRatio: .02, linkOk: false}};
    for (let i = 0; i < 5; i++) await request('/api/live/frame', {method: 'POST', producer: true, json: true, body: observed});
    await page.waitForFunction(() => !document.querySelector('#guardian-confidence').hidden);
    await page.locator('#refresh-guardian').click(); await page.waitForSelector('#incident-list .incident-card');
    const firstIncident = page.locator('#incident-list .incident-card').first();
    await firstIncident.locator('select').selectOption('sensor_drop'); await firstIncident.getByRole('button', {name: 'Save label', exact: true}).click();
    await page.waitForFunction(() => [...document.querySelectorAll('#incident-list .incident-status')].some(el => el.textContent === 'labeled'));
    await page.locator('#guardian-retrain').click();
    await page.waitForFunction(() => !document.querySelector('#guardian-retrain').disabled && document.querySelector('#guardian-retrained-f1').textContent !== '—');
    assert.equal(await page.locator('#guardian-model').innerText(), actualStatus.modelVersion, 'Real retraining keeps the active model until approval');
    const trainedStatus = await (await request('/api/guardian/status')).json();
    assert.equal(await page.locator('#guardian-deploy').isEnabled(), trainedStatus.candidateReady);
    console.log('Real backend QA passed: V1 transport/assets, Guardian status/model export, simulator, incident labeling and retraining.');

    // Deterministic V2 UI fixtures also exercise errors/races without a provider.
    // V1 transport/download checks above continue to use the real backend.
    await page.locator('[data-panel="equipment"]').click(); await page.locator('#disconnect').click();
    const metrics = {caughtFailures: 24, totalFailures: 30, meanLeadTimeS: 4.25, falseAlarms: 3, F1: .81, evaluatedWindows: 1152};
    const candidateMetrics = {...metrics, caughtFailures: 27, falseAlarms: 2, F1: .89};
    const sim = {running: false, fault: 'nominal', steps: 1};
    const model = {modelVersion: 'v1', currentMetrics: metrics, baselineMetrics: metrics, candidateReady: false, candidateVersion: null, candidateMetrics: null, simState: sim};
    const incidents = [{id: 7, carrierId: 'rover-' + 'x'.repeat(100), predictedCause: 'dust', createdAt: Date.now() / 1000, status: 'pending', trueCause: null}];
    const posts = []; let delayLabel = false, releaseLabel, rejectFault = false;
    const rover = {room: 'gale-rover-sim', carrierId: 'rover-' + 'x'.repeat(100), carrierType: 'rover', source: 'simulated-rover', points, receivedAt: Date.now() / 1000,
      telemetry: {pointCount: 384, slipRatio: .65, lumaContrast: .08, poseJumpM: .2},
      guardian: {riskLevel: 'critical', riskScore: .91, predictedCause: 'dust', leadTimeS: 3.5, modelVersion: 'v1', lowConfidence: true, recoveryAction: 'Stop and inspect the optical sensor.'}};
    const mast = {...rover, room: 'mast-testbed', carrierId: 'quest-mast-01', carrierType: 'mast-testbed', source: 'live-quest', telemetry: {pointCount: 384}, guardian: {...rover.guardian, riskLevel: 'nominal', riskScore: .12, predictedCause: 'nominal', lowConfidence: false}};
    const fresh = f => ({...f, receivedAt: Date.now() / 1000});
    await page.route('**/api/live/latest', route => route.fulfill({json: {rooms: [fresh(mast), fresh(rover)]}}));
    await page.routeWebSocket('**/api/live/stream?token=test-viewer', ws => { liveSocket = ws; ws.send(JSON.stringify({rooms: [fresh(mast), fresh(rover)]})); });
    fixturePulse = setInterval(() => { if (liveSocket) liveSocket.send(JSON.stringify({rooms: [fresh(mast), fresh(rover)]})); }, 5000);
    await page.route(/\/api\/(guardian|sim)\//, async route => {
      const r = route.request(), url = new URL(r.url());
      if (r.method() === 'GET') {
        assert.equal(r.headers().authorization, 'Bearer test-viewer');
        assert.ok(!url.pathname.endsWith('/rover'), 'Simulator status comes from Guardian status');
        return route.fulfill({json: url.pathname.endsWith('/incidents') ? {incidents} : model});
      }
      assert.equal(r.headers().authorization, 'Bearer test-producer');
      assert.equal(url.searchParams.has('token'), false);
      const payload = r.postDataJSON(); posts.push({path: url.pathname, payload});
      if (url.pathname.endsWith('/label')) {
        if (delayLabel) await new Promise(resolve => { releaseLabel = resolve; });
        incidents[0].trueCause = payload.trueCause; incidents[0].status = 'labeled';
      } else if (url.pathname.endsWith('/retrain')) {
        model.candidateReady = true; model.candidateVersion = 'v2'; model.candidateMetrics = candidateMetrics;
      } else if (url.pathname.endsWith('/deploy')) {
        assert.deepEqual(payload, {approved: true, candidateVersion: 'v2'});
        model.modelVersion = 'v2'; model.currentMetrics = candidateMetrics; model.candidateReady = false; model.candidateVersion = null; model.candidateMetrics = null;
      } else if (url.pathname.endsWith('/rover')) {
        if (rejectFault && payload.action === 'fault') return route.fulfill({status: 403, json: {detail: 'Forbidden'}});
        if (payload.action === 'fault') sim.fault = payload.fault;
        else if (payload.action === 'step') sim.steps++;
        else sim.running = payload.action === 'start';
      } else throw new Error(`Unexpected fixture route: ${url.pathname}`);
      return route.fulfill({json: {ok: true, simState: sim, latestFrame: fresh(rover), ...(url.pathname.endsWith('/retrain') ? {candidateVersion: 'v2'} : {})}});
    });
    await page.reload(); await page.waitForSelector('#terrain[data-ready="true"]');
    await page.evaluate(() => document.fonts.ready);
    await page.locator('[data-panel="equipment"]').click();
    await page.locator('#viewer-token').fill('test-viewer'); await page.locator('#connect-form button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('#connection-status').textContent === 'Viewer connected');
    await page.locator('[data-panel="guardian"]').click(); await page.waitForSelector('#incident-list .incident-card');
    await page.waitForFunction(() => document.querySelector('#guardian-score').textContent === '91%');
    assert.equal(await page.locator('#guardian-score').innerText(), '91%');
    assert.equal(await page.locator('#guardian-risk').getAttribute('data-risk'), 'critical');
    assert.equal(await page.locator('#guardian-meter').evaluate(el => el.value), .91);
    assert.ok(await page.locator('#guardian-confidence').isVisible());
    assert.equal(await page.locator('.carrier-card').count(), 2);
    assert.ok(await page.locator('.carrier-card[data-low-confidence="true"]').count() === 1);
    assert.equal(await page.locator('#overlay-title').innerText(), 'Rover simulation');
    assert.match(await page.locator('#scan-telemetry').innerText(), /Slip 65%/);
    assert.match(await page.locator('#scan-guardian').innerText(), /Critical.*Dust or occlusion/);
    assert.ok(await page.locator('#guardian-retrain').isDisabled());
    await page.locator('#producer-token').fill('test-producer');
    assert.ok(await page.locator('#guardian-deploy').isDisabled());
    await page.getByRole('button', {name: 'Save label', exact: true}).click(); assert.equal(posts.length, 0, 'Predicted causes are not silently accepted as verified labels');
    await page.locator('#incident-cause-7').selectOption('dust'); await page.getByRole('button', {name: 'Save label', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#incident-list .incident-status').textContent === 'labeled');
    assert.deepEqual(posts[0], {path: '/api/guardian/incidents/7/label', payload: {trueCause: 'dust'}});
    for (const action of ['start', 'stop', 'step']) {
      await page.locator(`[data-sim-action="${action}"]`).click();
      await page.waitForFunction(() => !document.querySelector('#guardian-retrain').disabled);
      assert.deepEqual(posts.at(-1).payload, {action});
    }
    for (const fault of ['nominal', 'dust', 'low_texture', 'glare', 'wheel_slip', 'sensor_drop']) {
      await page.locator(`[data-sim-fault="${fault}"]`).click();
      await page.waitForFunction(f => document.querySelector(`[data-sim-fault="${f}"]`).getAttribute('aria-pressed') === 'true' && !document.querySelector('#guardian-retrain').disabled, fault);
      assert.deepEqual(posts.at(-1).payload, {action: 'fault', fault});
    }
    await page.locator('#guardian-retrain').click(); await page.waitForFunction(() => !document.querySelector('#guardian-deploy').disabled);
    assert.equal(await page.locator('#guardian-model').innerText(), 'v1', 'Retraining never deploys automatically');
    assert.equal(await page.locator('#guardian-baseline-f1').innerText(), '81.0%');
    assert.equal(await page.locator('#guardian-retrained-f1').innerText(), '89.0%');
    assert.match(await page.locator('#guardian-deploy-note').innerText(), /27 \/ 30 faults caught/);
    await page.locator('#guardian-deploy').click(); await page.waitForFunction(() => document.querySelector('#guardian-model').textContent === 'v2');
    assert.ok(await page.locator('#guardian-deploy').isDisabled());
    rejectFault = true; await page.locator('[data-sim-fault="dust"]').click();
    await page.waitForFunction(() => document.querySelector('#guardian-message').textContent.includes('Token was not accepted'));
    assert.equal(await page.locator('[data-sim-fault="sensor_drop"]').getAttribute('aria-pressed'), 'true', 'Rejected actions preserve acknowledged simulator state');
    assert.ok(await page.locator('#producer-token').inputValue() === 'test-producer');
    rejectFault = false;

    const measurements = [];
    for (const [width, height] of [[1440, 900], [390, 844]]) {
      await page.setViewportSize({width, height});
      for (const pane of ['equipment', 'guardian', 'sessions', 'logs', 'settings']) {
        if (await page.locator(`[data-panel="${pane}"]`).getAttribute('aria-expanded') !== 'true') await page.locator(`[data-panel="${pane}"]`).click();
        const m = await page.locator('#' + pane).evaluate(el => {
          const right = el.getBoundingClientRect().right;
          return {overflow: el.scrollWidth - el.clientWidth, outliers: [...el.querySelectorAll('*')].filter(child => child.getBoundingClientRect().width > 0 && child.getBoundingClientRect().right > right + .5).length, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight};
        });
        assert.equal(m.overflow, 0, `${width} ${pane} horizontal overflow`); assert.equal(m.outliers, 0, `${width} ${pane} overflowing children`);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0, `${width} ${pane} page overflow`);
        if (width === 390 && pane === 'equipment') assert.ok(m.scrollHeight > m.clientHeight, 'Mobile pane scrolls vertically');
        measurements.push({width, pane, ...m});
      }
      await page.locator('[data-panel="equipment"]').click();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.screenshot({path: path.join(artifacts, `mission-${width}.png`)});
      await page.locator('[data-panel="guardian"]').click();
      await page.locator('#guardian').evaluate(el => { el.scrollTop = 0; });
      await page.screenshot({path: path.join(artifacts, `guardian-${width}.png`)});
      await page.locator('#close-drawer').click();
      const instruments = await page.evaluate(() => Object.fromEntries(['carrier-stage', 'live-overlay'].map(id => {
        const el = document.getElementById(id), r = el.getBoundingClientRect();
        return [id, {width: r.width, height: r.height, top: r.top, bottom: r.bottom, overflow: el.scrollWidth - el.clientWidth}];
      })));
      for (const [name, r] of Object.entries(instruments)) { assert.ok(r.width > 0 && r.height > 0, `${width} ${name} visible geometry`); assert.equal(r.overflow, 0, `${width} ${name} overflow`); }
      if (width === 390) assert.ok(instruments['carrier-stage'].bottom <= instruments['live-overlay'].top, 'Mobile carrier list and scan overlay do not overlap');
      await page.screenshot({path: path.join(artifacts, `carriers-${width}.png`)});
    }
    await page.setViewportSize({width: 1440, height: 900});
    await page.screenshot({path: path.join(artifacts, 'mission-terrain.png')});
    // A disappearing live carrier must clear the overlay, including rover sources.
    clearInterval(fixturePulse);
    liveSocket.send(JSON.stringify({...rover, receivedAt: Date.now() / 1000 - 31}));
    await page.waitForFunction(() => document.querySelector('#live-overlay').hidden);
    liveSocket.send(JSON.stringify({...rover, receivedAt: Date.now() / 1000, points: []}));
    await page.waitForFunction(() => document.querySelector('#scan-caption').textContent.includes('No scan points'));
    await page.locator('[data-panel="guardian"]').click();
    delayLabel = true; await page.locator('#incident-cause-7').selectOption('glare');
    await page.getByRole('button', {name: 'Save label', exact: true}).click();
    while (!releaseLabel) await pause(10);
    await page.locator('[data-panel="equipment"]').click(); await page.locator('#disconnect').click();
    releaseLabel(); await pause(100);
    assert.equal(await page.locator('#session-list .card').count(), 0);
    assert.ok(await page.locator('#log-preview').isHidden());
    assert.equal(await page.locator('#viewer-token').inputValue(), '');
    assert.equal(await page.locator('#producer-token').inputValue(), '');
    assert.equal(await page.locator('#guardian-model').innerText(), '—');
    assert.ok(await page.locator('#guardian-deploy').isDisabled());
    assert.ok(await page.locator('#guardian-retrain').isDisabled());
    assert.equal(await page.locator('#incident-list .incident-card').count(), 0, 'Late producer response cannot restore disconnected state');
    assert.ok(await page.locator('[data-fleet-action="start"]').isDisabled());
    assert.match(await page.locator('#fleet-access-status').textContent(), /Connect a viewer in Equipment and live/);
    assert.deepEqual(await page.evaluate(() => ({local: {...localStorage}, session: {...sessionStorage}, cookies: document.cookie})), {local: {}, session: {}, cookies: ''});
    assert.deepEqual(errors, []); assert.deepEqual(badAssets, []);
    fs.writeFileSync(path.join(artifacts, 'browser-report.json'), JSON.stringify({ok: true, measurements, pageErrors: errors, failedAssets: badAssets, authenticatedDownloads: authorizedDownloads.length}, null, 2));
    console.log('Browser QA passed: real WebSocket, PLY/ARSM downloads, logs, both terrains/grid modes; Guardian operator workflow, faults, explicit deploy, stale response and token cleanup using V2 fixtures; 10 pane/viewport checks have zero horizontal overflow and zero overflowing children.');
  } finally {
    clearInterval(fixturePulse);
    if (liveSocket) liveSocket.close();
    if (context) await context.close();
    if (server) server.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
