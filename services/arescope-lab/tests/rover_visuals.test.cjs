const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static/app.js'), 'utf8');
const terrainSource = `const wrapAngle = angle => Math.atan2(Math.sin(angle), Math.cos(angle));
const fleetColors = ['#eeae76', '#80cdb5', '#8fbde7', '#c6a3df', '#d9ce86', '#ed9da7'];
${source.slice(source.indexOf('  class Terrain {'), source.indexOf('  let terrain,'))}`;
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'static/data/hirise-gale.json'), 'utf8'));
const point = (x, z) => [x, -4000 + x * .13 - z * .08 + x * z * .00001, z];
const slope = {source: 'nasa-pds-hirise', grid: {rows: 81, cols: 53}, points: Array.from({length: 81 * 53}, (_, i) => point((i % 53 - 26) * 77.9, (Math.floor(i / 53) - 40) * 81.2))};
const rover = (position = point(0, 0), extra = {}) => ({carrierId: 'test-rover', position, headingDeg: 90, status: 'surveying', fault: 'nominal', trail: [position], ...extra});
const state = (rovers, extra = {}) => ({simulation: true, terrainSource: 'nasa-pds-hirise', running: true, speedMultiplier: 60, elapsedS: 60, coverage: {cells: [[30, 20]]}, rovers, ...extra});

function harness() {
  let time = 0, frameId = 0; const frames = new Map(), documentEvents = new Map(), calls = [];
  const constants = ['VERTEX_SHADER', 'FRAGMENT_SHADER', 'COMPILE_STATUS', 'LINK_STATUS', 'ARRAY_BUFFER', 'ELEMENT_ARRAY_BUFFER', 'STATIC_DRAW', 'DYNAMIC_DRAW', 'FLOAT', 'TRIANGLES', 'LINES', 'LINE_STRIP', 'DEPTH_TEST', 'LEQUAL', 'POLYGON_OFFSET_FILL', 'UNSIGNED_SHORT', 'COLOR_BUFFER_BIT', 'DEPTH_BUFFER_BIT'];
  const gl = new Proxy(Object.fromEntries(constants.map((name, i) => [name, i + 1])), {get(object, key) {
    return key in object ? object[key] : (...args) => { calls.push({name: key, args}); if (key === 'getShaderParameter' || key === 'getProgramParameter') return true; return 1; };
  }});
  const canvas = {clientWidth: 1440, clientHeight: 900, dataset: {}, getContext: () => gl, addEventListener() {}, focus() {}};
  const document = {hidden: false, addEventListener: (name, fn) => documentEvents.set(name, fn)};
  const preference = {matches: false, addEventListener() {}};
  const Terrain = vm.runInNewContext(`${terrainSource}; Terrain`, {devicePixelRatio: 1, performance: {now: () => time}, document,
    ResizeObserver: class {observe() {}}, matchMedia: () => preference,
    requestAnimationFrame: fn => { frames.set(++frameId, fn); return frameId; }, cancelAnimationFrame: id => frames.delete(id)});
  const terrain = new Terrain(canvas); terrain.load(slope);
  return {terrain, canvas, calls, gl, frames, preference, document, documentEvents,
    at(ms) { time = ms; const callbacks = [...frames.values()]; frames.clear(); for (const fn of callbacks) fn(ms); },
    clock(ms) { time = ms; }};
}
const near = (a, b, tolerance = 1e-7) => assert.ok(Math.abs(a - b) < tolerance, `${a} vs ${b}`);

test('six wheel contacts follow bilinear rectangular slopes at every heading and elevation setting', () => {
  const h = harness();
  for (const headingDeg of [0, 37, 90, 180, 270]) for (const elevation of [.5, 1.5, 3]) {
    h.terrain.scale = elevation; h.terrain.setFleet(state([rover(point(13, 37), {headingDeg})])); h.at(10);
    const anchor = h.terrain.fleetAnchors[0];
    assert.equal(anchor.wheelCount, 6); assert.equal(anchor.grounded, true);
    assert.equal(new Set(anchor.groundContacts.map(p => p.join(','))).size, 6);
    for (const p of anchor.groundContacts) near(p[1], point(p[0], p[2])[1]);
    assert.ok(Math.max(...anchor.groundContacts.map(p => p[1])) - Math.min(...anchor.groundContacts.map(p => p[1])) > .5);
    for (const call of h.calls.filter(c => c.name === 'bufferData' || c.name === 'bufferSubData')) {
      const data = call.args[call.name === 'bufferData' ? 1 : 2]; assert.ok([...data].every(Number.isFinite));
    }
  }
});

test('models keep a fixed half-metre part scale at edges and interior without moving their centre', () => {
  const h = harness(); h.terrain.load(fixture); const p0 = fixture.points[0], pn = fixture.points.at(-1), step = fixture.metadata.effective_spacing_m;
  for (const position of [[p0[0] + step / 2, 0, p0[2] + step / 2], [pn[0] - step / 2, 0, pn[2] - step / 2], [0, 0, 0]]) {
    for (const headingDeg of [0, 45, 90, 225]) {
      position[1] = h.terrain.surface(position[0], position[2]).height;
      h.terrain.setFleet(state([rover(position, {headingDeg})])); h.at(0);
      const anchor = h.terrain.fleetAnchors[0]; assert.ok(anchor.grounded); assert.equal(anchor.wheelCount, 6);
      near(anchor.worldPosition[0], position[0]); near(anchor.worldPosition[2], position[2]);
      for (const p of anchor.groundContacts) { assert.ok(p[0] > p0[0] && p[0] < pn[0]); assert.ok(p[2] > p0[2] && p[2] < pn[2]); }
      assert.equal(anchor.visualScale, .5, 'fixed display scale at every position and heading');
    }
  }
  assert.ok(h.terrain.focusRover('test-rover')); h.at(10); assert.equal(h.canvas.dataset.focusedRover, 'test-rover'); assert.ok(h.terrain.viewScale > 10);
  assert.ok(h.terrain.project(h.terrain.normalize(h.terrain.roverMotion.get('test-rover').sample.position)).inViewport);
  h.terrain.reset(); assert.equal(h.terrain.viewScale, 1); assert.equal(h.canvas.dataset.focusedRover, '');
});

test('default rover focus and fleet framing share projection, track snapshots and reset to the region', () => {
  const h = harness(); h.terrain.setFleet(state([rover(point(-800, -500)), rover(point(800, -500), {carrierId: 'second'})])); h.at(0);
  assert.equal(h.canvas.dataset.cameraMode, 'rover'); assert.equal(h.canvas.dataset.focusedRover, 'test-rover');
  assert.ok(h.terrain.focusFleet()); h.at(10); assert.equal(h.canvas.dataset.cameraMode, 'fleet');
  assert.ok(h.terrain.fleetAnchors.every(a => h.terrain.project(a.position).inViewport));
  const previous = h.terrain.viewCenter.slice();
  h.terrain.setFleet(state([rover(point(-700, -400)), rover(point(900, -400), {carrierId: 'second'})])); h.at(20);
  assert.notDeepEqual(h.terrain.viewCenter, previous); h.terrain.reset();
  assert.equal(h.canvas.dataset.cameraMode, 'region'); assert.equal(h.terrain.viewScale, 1);
  h.terrain.setFleet(state([rover(point(0, 0))])); h.at(30); assert.equal(h.canvas.dataset.cameraMode, 'region', 'polling preserves a requested overview');
});

test('interpolation follows acknowledged corners and wheel rotation follows distance without extrapolation', () => {
  const h = harness(), a = point(0, 0), corner = point(80, 0), b = point(80, 80);
  h.terrain.setFleet(state([rover(a)])); h.at(0);
  h.clock(1000); h.terrain.setFleet(state([rover(b, {trail: [a, corner, b]})], {elapsedS: 120}));
  h.at(1250); let anchor = h.terrain.fleetAnchors[0];
  assert.ok(anchor.worldPosition[0] > 0 && anchor.worldPosition[0] < 80); near(anchor.worldPosition[2], 0);
  assert.ok(anchor.wheelAngle > 0); const rotation = anchor.wheelAngle;
  h.at(2125); anchor = h.terrain.fleetAnchors[0]; near(anchor.worldPosition[0], 80);
  assert.ok(anchor.worldPosition[2] > 0 && anchor.worldPosition[2] < 80); assert.ok(anchor.wheelAngle > rotation);
  h.at(2500); anchor = h.terrain.fleetAnchors[0]; near(anchor.worldPosition[0], 80); near(anchor.worldPosition[2], 80);
  const length = Math.hypot(...corner.map((v, k) => v - a[k])) + Math.hypot(...b.map((v, k) => v - corner[k]));
  near(anchor.wheelAngle, length / (4.2 * .5));
  h.at(4000);
  assert.equal(h.frames.size, 0, 'render loop ends when the snapshot is reached');
  h.at(10000); near(h.terrain.fleetAnchors[0].wheelAngle, anchor.wheelAngle);
});

test('repeated snapshots retain the interpolation deadline and missing trail junctions never cut corners', () => {
  const h = harness(), a = point(0, 0), b = point(100, 0);
  h.terrain.setFleet(state([rover(a)])); h.at(0);
  h.clock(1000); const snapshot = state([rover(b, {trail: [a, b]})], {elapsedS: 120}); h.terrain.setFleet(snapshot);
  h.at(1300); const before = h.terrain.fleetAnchors[0].worldPosition[0];
  h.clock(1400); h.terrain.setFleet(snapshot); assert.equal(h.terrain.roverMotion.get('test-rover').started, 1000);
  h.at(1500); assert.ok(h.terrain.fleetAnchors[0].worldPosition[0] > before);
  const remote = point(-300, 200); h.clock(1600); h.terrain.setFleet(state([rover(remote, {trail: [remote]})], {elapsedS: 180})); h.at(4000);
  near(h.terrain.fleetAnchors[0].worldPosition[0], remote[0]); assert.equal(h.frames.size, 0);
});

test('pause, halt, reset, reduced motion and hidden tabs leave no perpetual animation loop', () => {
  for (const stop of ['pause', 'halt', 'reduced', 'hidden', 'reset']) {
    const h = harness(), a = point(0, 0), b = point(100, 0);
    h.terrain.setFleet(state([rover(a)])); h.at(0); h.clock(1000);
    const snapshot = state([rover(b, {trail: [a, b]})], {elapsedS: 120}); h.terrain.setFleet(snapshot); h.at(1250);
    if (stop === 'pause') h.terrain.setFleet({...snapshot, running: false});
    if (stop === 'halt') h.terrain.setFleet({...snapshot, rovers: [rover(b, {status: 'halted', fault: 'dust'})]});
    if (stop === 'reduced') h.preference.matches = true;
    if (stop === 'hidden') { h.document.hidden = true; h.documentEvents.get('visibilitychange')(); }
    if (stop === 'reset') h.terrain.setFleet(state([rover(a)], {elapsedS: 0, running: false}));
    h.at(1350); const angle = h.terrain.fleetAnchors[0].wheelAngle; h.at(5000);
    near(h.terrain.fleetAnchors[0].wheelAngle, angle); assert.equal(h.frames.size, 0, stop);
  }
});

test('repair animation is bounded by live snapshots, preserves progress and never spins halted wheels', () => {
  const h = harness(), recovery = {phase: 'repairing', progress: .4, helperId: 'helper', requiresApproval: false};
  const target = rover(point(0, 0), {status: 'halted', fault: 'dust', recovery});
  const helper = rover(point(24, 0), {carrierId: 'helper', headingDeg: -90, status: 'repairing', targetId: target.carrierId});
  const snapshot = state([target, helper]); h.terrain.setFleet(snapshot); h.at(100);
  assert.ok(h.terrain.fleetAnchors.every(a => h.terrain.project(a.position).inViewport), 'follow view includes the stopped rover and its repairing helper');
  assert.equal(h.terrain.fleetAnchors[1].repairing, true);
  assert.ok(h.frames.size > 0); const firstUpload = h.calls.filter(c => c.name === 'bufferSubData').at(-1).args[2];
  h.at(600); const nextUpload = h.calls.filter(c => c.name === 'bufferSubData').at(-1).args[2]; assert.notDeepEqual(firstUpload, nextUpload);
  assert.ok(h.terrain.fleetAnchors.every(a => a.wheelAngle === 0));
  assert.equal(snapshot.rovers[0].recovery.progress, .4); assert.equal(snapshot.rovers[0].fault, 'dust');
  h.at(1601); assert.equal(h.frames.size, 0, 'missing updates stop the synthetic tool motion');
  h.terrain.setFleet({...snapshot, running: false}); h.at(2000); assert.equal(h.frames.size, 0);
  h.terrain.setFleet(state([rover(point(0, 0), {status: 'halted', fault: 'sensor_dropout', recovery: {phase: 'awaiting_approval', requiresApproval: true}})]));
  h.at(2100); h.at(5000); assert.equal(h.terrain.fleetAnchors[0].repairing, false); assert.equal(h.frames.size, 0);
});

test('fixed scale survives different terrain extents, low orbit angles and zoom, without foreground magnification', () => {
  const h = harness();
  for (const grid of [slope, fixture]) {
    h.terrain.load(grid);
    const a = grid.points[0], positions = [[a[0] + 39, 0, a[2] + 39], [0, 0, 0], [100, 0, 200]];
    h.terrain.setFleet(state(positions.map((p, i) => rover(p, {carrierId: `scale-${i}`})), {running: false}));
    h.terrain.focusRover('scale-1'); h.at(1);
    for (const pitch of [-1.5, -.05, 0, .05, 1.5]) for (const zoom of [.55, 1, 1.6, 12]) {
      h.terrain.pitch = pitch; h.terrain.zoom = zoom; h.terrain.draw();
      assert.equal(h.terrain.inspectionCamera, true); assert.ok(h.terrain.zoom <= 1.6);
      const projectedLengths = h.terrain.fleetAnchors.map(anchor => {
        assert.equal(anchor.visualScale, .5);
        const p = anchor.worldPosition, start = h.terrain.project(h.terrain.normalize(p));
        const end = h.terrain.project(h.terrain.normalize([p[0] + 18, p[1], p[2]]));
        return Math.hypot(start.x - end.x, start.y - end.y);
      });
      for (const length of projectedLengths) { near(length, projectedLengths[0], 1e-6); assert.ok(length < 240, `bounded rover footprint: ${length}px`); }
    }
    // Sampling outside a raster clamps heights; it never shrinks or relocates a rover.
    h.terrain.setFleet(state([rover(a)], {running: false})); h.terrain.draw();
    const edge = h.terrain.fleetAnchors[0]; near(edge.visualScale, .5); near(edge.worldPosition[0], a[0]); near(edge.worldPosition[2], a[2]);
    assert.equal(edge.groundContacts.length, 6); assert.ok(edge.grounded);
  }
});

test('irregular receipt cadence keeps acknowledged movement continuous, then settles without extrapolation', () => {
  const h = harness(); let now = 0, x = 0, elapsedS = 0, trail = [point(0, 0)];
  h.terrain.setFleet(state([rover(trail[0])], {elapsedS})); h.at(now);
  let prior = 0;
  for (const interval of [1100, 1100, 1300, 1500, 1100, 1300, 1500]) {
    now += interval; x += 80; elapsedS += 60; trail.push(point(x, 0)); h.clock(now);
    const before = h.terrain.sampleMotion(h.terrain.roverMotion.get('test-rover'), now).position[0];
    h.terrain.setFleet(state([rover(point(x, 0), {trail})], {elapsedS})); h.at(now);
    near(h.terrain.fleetAnchors[0].worldPosition[0], before);
    for (const dt of [50, 500, 1000]) {
      h.at(now + dt); const position = h.terrain.fleetAnchors[0].worldPosition[0];
      assert.ok(position > prior, `no periodic hold at ${now + dt}`); assert.ok(position < x); prior = position;
    }
  }
  h.at(now + 3000); const last = h.terrain.fleetAnchors[0]; near(last.worldPosition[0], x);
  h.at(now + 6000); near(h.terrain.fleetAnchors[0].wheelAngle, last.wheelAngle); assert.equal(h.frames.size, 0);
});

test('completed approach interpolates its last trail and keeps the arm folded until arrival', () => {
  const h = harness(), target = rover(point(0, 0), {status: 'halted', fault: 'dust', recovery: {phase: 'repairing', helperId: 'helper'}});
  const helper = p => rover(point(p, 0), {carrierId: 'helper', headingDeg: -90, status: 'approaching', targetId: target.carrierId});
  h.terrain.setFleet(state([target, helper(120)])); h.at(0); h.clock(1000);
  const trail = Array.from({length: 25}, (_, i) => point(120 - i * 4, 0));
  h.terrain.setFleet(state([target, {...helper(24), status: 'assisting', trail}], {elapsedS: 120}));
  h.at(1300); let anchor = h.terrain.fleetAnchors[1]; assert.ok(anchor.worldPosition[0] > 24 && anchor.worldPosition[0] < 120); assert.equal(anchor.repairing, false);
  h.clock(1500); h.terrain.setFleet(state([target, {...helper(24), status: 'repairing', trail}], {elapsedS: 150}));
  h.at(1700); anchor = h.terrain.fleetAnchors[1]; assert.ok(anchor.worldPosition[0] > 24); assert.equal(anchor.repairing, false);
  h.at(2600); anchor = h.terrain.fleetAnchors[1]; near(anchor.worldPosition[0], 24); assert.ok(anchor.repairing && anchor.serviceReachable);
});

test('service tool touches the target with fixed-length articulated links and freezes exactly on pause, stale or reduced motion', () => {
  for (const stop of ['pause', 'stale', 'reduced']) {
    const h = harness(), target = rover(point(0, 0), {status: 'halted', fault: 'dust', recovery: {phase: 'repairing', helperId: 'helper', progress: .4}});
    const snapshot = state([target, rover(point(24, 0), {carrierId: 'helper', headingDeg: -90, status: 'repairing', targetId: target.carrierId})]);
    h.terrain.setFleet(snapshot); h.at(0); const first = h.terrain.fleetAnchors[1];
    for (let t = 20; t <= 500; t += 20) h.at(t);
    const next = h.terrain.fleetAnchors[1];
    const distance = (a, b) => Math.hypot(...a.map((v, k) => v - b[k]));
    const visual = p => [p[0], p[1] * h.terrain.scale, p[2]];
    assert.ok(next.repairing && next.serviceReachable); assert.ok(distance(first.toolTip, next.toolTip) > .5);
    assert.ok(distance(first.armJoints.elbow, next.armJoints.elbow) > .5);
    near(distance(visual(next.armJoints.shoulder), visual(next.armJoints.elbow)), 7.2);
    near(distance(visual(next.armJoints.elbow), visual(next.armJoints.wrist)), 6.15);
    near(distance(next.toolTip, next.serviceContact), 0); assert.ok(distance(next.toolTip, target.position) < 13);
    assert.ok(Math.abs(next.jointSwivel - first.jointSwivel) > .15, 'elbow visibly sweeps several degrees');
    if (stop === 'pause') h.terrain.setFleet({...snapshot, running: false});
    if (stop === 'reduced') h.preference.matches = true;
    h.at(stop === 'stale' ? 1700 : 520); const frozen = h.terrain.fleetAnchors[1];
    h.at(4000); h.terrain.draw(); const end = h.terrain.fleetAnchors[1];
    assert.deepEqual(end.armJoints, frozen.armJoints); assert.deepEqual(end.toolTip, frozen.toolTip); assert.equal(h.frames.size, 0);
    h.terrain.setFleet(state([target, rover(point(180, 0), {carrierId: 'helper', status: 'repairing', targetId: target.carrierId})])); h.terrain.draw();
    assert.equal(h.terrain.fleetAnchors[1].repairing, false); assert.equal(h.terrain.fleetAnchors[1].serviceContact, null);
  }
});

test('disconnect and switching away from HiRISE cancel an active model animation', () => {
  for (const disconnect of [true, false]) {
    const h = harness(), a = point(0, 0), b = point(100, 0);
    h.terrain.setFleet(state([rover(a)])); h.at(0); h.clock(1000);
    h.terrain.setFleet(state([rover(b, {trail: [a, b]})], {elapsedS: 120})); h.at(1200);
    assert.ok(h.frames.size > 0);
    if (disconnect) h.terrain.setFleet(null);
    else h.terrain.load({...slope, source: 'nasa-pds-mola'});
    h.at(1300); assert.equal(h.frames.size, 0); assert.equal(h.terrain.fleetGeometry.length, 0);
  }
});

test('real Chromium renders the six-wheel geometry, moves and stops without WebGL errors', {skip: process.env.ROVER_VISUAL_BROWSER !== '1'}, async () => {
  const {chromium} = require('playwright');
  const artifacts = path.join(root, 'static/.qa/rover-visuals'); fs.mkdirSync(artifacts, {recursive: true});
  const browser = await chromium.launch({headless: true, executablePath: process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined, args: ['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 960}, deviceScaleFactor: 1});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<style>html,body{margin:0;background:#0d0907;color:#e4d3c7;font:14px Arial}header{position:absolute;left:28px;top:24px;pointer-events:none}small{color:#b8a599}canvas{display:block;width:100vw;height:100vh;outline:none}</style><header>ARESCOPE LAB · Fleet visual QA<br><small>NASA HiRISE archive · Enlarged rover models · Synthetic service animation</small></header><canvas id="terrain" tabindex="0"></canvas>');
    await page.addScriptTag({content: `${terrainSource}; window.viz = new Terrain(document.getElementById('terrain'));`});
    const sample = (row, col) => fixture.points[row * fixture.grid.cols + col];
    const targetPoint = sample(64, 18);
    const positions = [targetPoint, [targetPoint[0] + 24, targetPoint[1], targetPoint[2]], sample(69, 31)];
    const snapshot = state(positions.map((p, i) => rover(p, {carrierId: `rover-${i}`, headingDeg: [90, -90, 105][i]})));
    await page.evaluate(({grid, snapshot}) => { viz.load(grid); viz.setFleet(snapshot); }, {grid: fixture, snapshot});
    await page.waitForSelector('#terrain[data-ready="true"]');
    await page.screenshot({path: path.join(artifacts, 'fleet-default.png')});
    await page.evaluate(() => { viz.focusFleet(); viz.draw(); });
    await page.screenshot({path: path.join(artifacts, 'fleet-focused.png')});
    await page.evaluate(() => viz.reset());
    await page.screenshot({path: path.join(artifacts, 'fleet-region.png')});
    await page.evaluate(() => { viz.zoom = 2.3; viz.pitch = .65; viz.yaw = -.65; viz.draw(); });
    await page.screenshot({path: path.join(artifacts, 'fleet-close.png')});
    const next = structuredClone(snapshot); next.elapsedS = 120;
    next.rovers[2].position = sample(69, 33); next.rovers[2].trail.push(sample(69, 32), next.rovers[2].position);
    next.rovers[0].status = 'halted'; next.rovers[0].fault = 'dust'; next.rovers[0].recovery = {phase: 'repairing', progress: .55, helperId: 'rover-1', requiresApproval: false};
    next.rovers[1].status = 'repairing'; next.rovers[1].targetId = 'rover-0'; next.rovers[1].position = [positions[0][0] + 24, positions[0][1], positions[0][2]];
    await page.evaluate(snapshot => viz.setFleet(snapshot), next);
    await page.waitForTimeout(350);
    const moving = await page.evaluate(() => JSON.parse(viz.canvas.dataset.fleetMarkers));
    assert.ok(moving[2].wheelAngle > 0); assert.ok(moving.every(r => r.grounded && r.wheelCount === 6));
    assert.equal(moving[1].repairing, true); assert.equal(moving[0].wheelAngle, 0);
    await page.screenshot({path: path.join(artifacts, 'fleet-repair.png')});
    await page.evaluate(() => { viz.focusRover('rover-1'); viz.pitch = .45; viz.draw(); });
    await page.screenshot({path: path.join(artifacts, 'fleet-repair-detail.png')});
    await page.evaluate(snapshot => viz.setFleet(snapshot), next);
    const before = await page.evaluate(() => viz.fleetAnchors.find(a => a.carrierId === 'rover-1'));
    await page.waitForTimeout(500);
    const after = await page.evaluate(() => viz.fleetAnchors.find(a => a.carrierId === 'rover-1'));
    assert.ok(after.serviceReachable); assert.ok(Math.hypot(...after.toolTip.map((v, i) => v - before.toolTip[i])) > .5);
    assert.deepEqual(after.toolTip, after.serviceContact);
    await page.screenshot({path: path.join(artifacts, 'fleet-repair-sweep.png')});
    await page.evaluate(snapshot => viz.setFleet({...snapshot, running: false}), next); await page.waitForTimeout(100);
    const stopped = await page.evaluate(() => ({markers: viz.canvas.dataset.fleetMarkers, error: viz.gl.getError(), pending: viz.pending}));
    await page.waitForTimeout(200);
    assert.equal(await page.evaluate(() => viz.canvas.dataset.fleetMarkers), stopped.markers);
    assert.equal(stopped.error, 0); assert.equal(stopped.pending, 0); assert.deepEqual(errors, []);
    await page.screenshot({path: path.join(artifacts, 'fleet-repair-paused.png')});
    await page.emulateMedia({reducedMotion: 'reduce'}); await page.evaluate(snapshot => viz.setFleet(snapshot), next); await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => viz.pending), 0);
    const corner = [fixture.points[0][0] + fixture.metadata.effective_spacing_m / 2, 0, fixture.points[0][2] + fixture.metadata.effective_spacing_m / 2];
    await page.evaluate(snapshot => { viz.setFleet(snapshot); viz.focusRover('test-rover'); viz.draw(); }, state([rover(corner)], {running: false, elapsedS: 0}));
    await page.screenshot({path: path.join(artifacts, 'fleet-boundary-detail.png')});
    assert.ok((await page.evaluate(() => JSON.parse(viz.canvas.dataset.fleetMarkers)))[0].grounded);
    // Reproduce the user's mixed edge/interior low-angle scene with the actual raster.
    const regression = state([rover(corner), rover(sample(64, 24), {carrierId: 'middle'}), rover(sample(64, 25), {carrierId: 'near'})], {running: false});
    await page.evaluate(snapshot => { viz.setFleet(snapshot); viz.focusRover('middle'); viz.pitch = .04; viz.yaw = -.5; viz.zoom = 1.6; viz.draw(); }, regression);
    const visible = await page.evaluate(() => JSON.parse(viz.canvas.dataset.fleetMarkers));
    assert.ok(visible.every(a => a.visualScale === .5 && a.grounded));
    await page.screenshot({path: path.join(artifacts, 'fleet-fixed-scale-low-orbit.png')});
    assert.equal(await page.evaluate(() => viz.gl.getError()), 0);
    console.log(`Rover screenshot QA: ${artifacts}`);
  } finally { await browser.close(); }
});
