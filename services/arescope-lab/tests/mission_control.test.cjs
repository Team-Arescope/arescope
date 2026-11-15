const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const html = read('static/index.html');
const js = read('static/app.js') + '\n' + read('static/shell.js');
const routes = [...read('app.py').matchAll(/@app\.(get|post|put|delete|websocket)\("([^"]+)"/g)].map(m => ({method: m[1], route: m[2]}));
const normalize = p => p.split('?')[0].replace(/\$\{[^}]+\}/g, '{}').replace(/\{[^}]+\}/g, '{}');

test('every HTML, JS and CSS static asset reference resolves inside static/', () => {
  const source = html + js + read('static/style.css') + read('static/mission.css');
  const references = [...source.matchAll(/(?:["'(])((?:\/static\/)[^"'\s)<>`]+)/g)].map(m => m[1]);
  assert.ok(references.length >= 12);
  for (const ref of references) {
    const asset = path.resolve(root, '.' + ref.split('?')[0]);
    assert.ok(asset.startsWith(path.join(root, 'static') + path.sep));
    assert.ok(fs.statSync(asset).isFile(), ref);
    assert.ok(fs.statSync(asset).size > 0, ref);
  }
});

test('all frontend live API paths match backend decorators, including dynamic IDs', () => {
  const calls = [...js.matchAll(/["'`]((?:\/api\/live\/)[^"'`\s]+)/g)].map(m => m[1]);
  assert.ok(calls.length >= 9);
  for (const call of calls) assert.ok(routes.some(r => normalize(r.route) === normalize(call)), call);
  const producerOnly = routes.filter(r => r.method === 'post' && r.route.startsWith('/api/live/'));
  assert.deepEqual(producerOnly.map(r => r.route).sort(), ['/api/live/frame', '/api/live/log', '/api/live/mesh']);
  for (const route of routes.filter(r => r.route.startsWith('/api/live/') && r.method !== 'post')) {
    assert.ok(calls.some(call => normalize(route.route) === normalize(call)), `Unwired viewer route: ${route.route}`);
  }
});

test('V2 Guardian and simulator API paths and methods match the current backend', {
  skip: !routes.some(r => r.route === '/api/guardian/status') ? 'Track 1 app.py still has V1 routes; V2 parity awaits the backend update.' : false
}, () => {
  const calls = [...js.matchAll(/["'`]((?:\/api\/(?:guardian|sim)\/)[^"'`\s]+)/g)].map(m => m[1]);
  const contracts = [
    ['get', '/api/guardian/status'], ['get', '/api/guardian/model'], ['get', '/api/guardian/incidents'],
    ['post', '/api/guardian/incidents/{id}/label'], ['post', '/api/guardian/retrain'],
    ['post', '/api/guardian/deploy'], ['post', '/api/sim/rover']
  ];
  if (routes.some(r => r.route === '/api/sim/fleet')) contracts.push(['get', '/api/sim/fleet'], ['post', '/api/sim/fleet']);
  for (const [method, route] of contracts) {
    assert.ok(routes.some(r => r.method === method && normalize(r.route) === normalize(route)), `${method} ${route}`);
    assert.ok(calls.some(call => normalize(call) === normalize(route)), `Unwired V2 route: ${route}`);
  }
  for (const call of calls.filter(call => call !== '/api/sim/fleet' || routes.some(r => r.route === call))) assert.ok(routes.some(r => normalize(r.route) === normalize(call)), call);
  for (const route of routes.filter(r => /^\/api\/(guardian|sim)\//.test(r.route))) {
    assert.ok(calls.some(call => normalize(route.route) === normalize(call)), `Unwired V2 route: ${route.route}`);
  }
});

test('every static element ID and drawer control resolves without duplicates', () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  assert.equal(ids.length, new Set(ids).size, 'Duplicate HTML IDs');
  const refs = [...js.matchAll(/\$\('([^']+)'\)/g)].map(m => m[1]);
  for (const ref of refs) assert.ok(ids.includes(ref), `Missing element: ${ref}`);
  for (const pane of ['equipment', 'guardian', 'sessions', 'logs', 'settings']) {
    assert.match(html, new RegExp(`data-panel="${pane}" aria-controls="${pane}"`));
  }
});

test('all markup and generated icons have real Lucide paths with no fallback', () => {
  const shell = read('static/shell.js');
  const dictionary = shell.slice(shell.indexOf('const icons ='), shell.indexOf('document.querySelectorAll'));
  const icon = vm.runInNewContext(`(() => { ${dictionary} return icon; })()`, {
    document: {createElementNS: () => ({setAttribute() {}, innerHTML: ''})}
  });
  const names = [...html.matchAll(/data-icon="([^"]+)"/g)].map(m => m[1]);
  names.push(...[...js.matchAll(/button\('[^']*', '([^']+)'/g)].map(m => m[1]));
  for (const call of js.matchAll(/LabShell\.icon\(([^)]+)\)/g)) names.push(...[...call[1].matchAll(/'([^']+)'/g)].map(m => m[1]).filter(n => n !== 'rover'));
  for (const name of names) assert.match(icon(name).innerHTML, /<(path|circle|rect)\b/, name);
  for (const name of ['shield-check', 'play', 'square', 'step-forward', 'alert-triangle', 'truck']) assert.ok(names.includes(name), name);
  assert.throws(() => icon('missing-icon'), /Unknown mission icon/);
});

test('zero stale copy, unfinished markers, API paths in visible UI or glyph icons', () => {
  const source = html + js + read('static/style.css') + read('static/mission.css');
  const stale = /не поддерживается|не является live|Ни один режим|нет live|без live-связи|интеграция отсутствует|не подключена|БЕЗ LIVE|live is unavailable|no live support|not a live feed|TODO|FIXME|XXX|HACK|18964|AppCompat-fix|BETA 0\.\d/iu;
  assert.doesNotMatch(source, stale);
  assert.doesNotMatch(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ''), /\/api\//);
  assert.doesNotMatch(html + read('static/shell.js'), /[▶◈⌁◉⚙✕📡📁🗑]/u);
  assert.ok(html.includes('ARESCOPE LAB'));
  assert.ok(read('static/style.css').includes('#0d0907'));
  assert.ok(read('static/style.css').includes('#ee8a5b'));
});

test('both scripts parse without a build step', () => {
  for (const file of ['static/app.js', 'static/shell.js']) assert.doesNotThrow(() => new vm.Script(read(file), {filename: file}));
});

for (const [name, source] of [['mola', 'nasa-pds-mola'], ['hirise', 'nasa-pds-hirise']]) {
  test(`${name} fixture retains provenance and a regular grid at the expanded physical scale`, () => {
    const data = JSON.parse(read(`static/data/${name}-gale.json`));
    const {rows, cols} = data.grid;
    assert.equal(data.source, source); assert.equal(data.frame, 'mars-local-metres');
    assert.ok(Number.isInteger(rows) && rows > 1 && Number.isInteger(cols) && cols > 1);
    assert.equal(data.points.length, rows * cols);
    assert.ok(rows * cols + (rows - 1) * (cols - 1) <= 65536, 'source and cell-centre vertices fit Uint16 indices');
    assert.equal(data.metadata.live, false); assert.match(data.metadata.source_url, /^https:\/\//);
    assert.ok(data.metadata.product_id); assert.match(data.metadata.units, /metres/);
    for (const point of data.points) assert.ok(Array.isArray(point) && point.length === 3 && point.every(Number.isFinite));
    const stepX = data.points[1][0] - data.points[0][0];
    const stepZ = data.points[cols][2] - data.points[0][2];
    assert.ok(stepX > 0 && stepZ > 0);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const p = data.points[r * cols + c];
      assert.ok(Math.abs(p[0] - data.points[0][0] - c * stepX) < .001);
      assert.ok(Math.abs(p[2] - data.points[0][2] - r * stepZ) < .001);
    }
    const east = data.points[cols - 1][0] - data.points[0][0], south = data.points[(rows - 1) * cols][2] - data.points[0][2];
    const extent = data.metadata.extent_m_axes || data.metadata.extent_m;
    if (typeof extent === 'object') {
      assert.ok(Math.abs(extent.east - east) < .001); assert.ok(Math.abs(extent.south - south) < .001);
    } else assert.ok(Math.abs(extent - Math.max(east, south)) < .001);
    assert.ok(new Set(data.points.map(p => p[1])).size > 100);
    if (name === 'hirise') {
      assert.equal(data.metadata.product_id, 'DTEEC_001488_1750_001752_1750_U02');
      assert.ok(Math.abs(data.metadata.native_spacing_m - 1.0117467945795) < 1e-10);
      assert.ok(Math.abs(stepX - 77.9045031826215) < .00001 && Math.abs(stepX - stepZ) < .00001, 'display samples have equal ~77.9 m spacing');
      assert.ok(Math.max(east, south) > 9500 && Math.max(east, south) < 10500, 'long side covers about 10 km of the source stripe');
      assert.ok(east > 4000 && east < 4100 && south > 9900 && south < 10000, 'the valid stripe is about 4.05 km east by 9.97 km south');
      assert.ok(east * south / 1000000 > 40 && east * south / 1000000 < 41, 'survey area is about 40.4 km²');
      const stride = stepX / data.metadata.native_spacing_m;
      assert.ok(Math.abs(stride - Math.round(stride)) < .00001, 'display step is an exact native pixel stride');
    } else {
      assert.equal(data.metadata.product_id, 'MEGT00N000GB.IMG');
      assert.equal(data.metadata.grid_pixels_per_degree, 64);
      assert.ok(stepX > 900 && stepX < 1000 && stepZ > 900 && stepZ < 1000, 'MOLA steps are about 0.926 km');
      assert.ok(east > 57000 && east < 61000 && south > 57000 && south < 61000, 'regional extent is about 59 km on both axes');
      assert.ok(Math.abs(data.metadata.spacing_m.east - stepX) < .001);
      assert.ok(Math.abs(data.metadata.spacing_m.south - stepZ) < .001);
    }
  });
}

function rectangularTerrain(rows, cols, stepX = 77 * 1.0117467945795, stepZ = stepX) {
  const east = (cols - 1) * stepX, south = (rows - 1) * stepZ;
  return {source: 'nasa-pds-hirise', grid: {rows, cols}, metadata: {native_spacing_m: 1.0117467945795, effective_spacing_m: stepX, extent_m: Math.max(east, south), extent_m_axes: {east, south}},
    points: Array.from({length: rows * cols}, (_, i) => [(i % cols) * stepX - east / 2, Math.sin(i / cols) * 30 - 4000, Math.floor(i / cols) * stepZ - south / 2])};
}

function labelsFor(data) {
  const code = read('static/app.js');
  const labels = vm.runInNewContext(`${code.slice(code.indexOf('  function terrainDimensions('), code.indexOf('  let terrain,'))}; terrainLabels`);
  return {...labels(data)};
}

test('terrain labels and fleet description use both physical axes and source native spacing', () => {
  const data = rectangularTerrain(129, 53), labels = labelsFor(data);
  assert.equal(labels.count, '129 × 53 samples');
  assert.equal(labels.caption, 'HiRISE archive · 4.05 × 9.97 km');
  assert.match(labels.source, /77\.9 m display step/);
  assert.match(labels.notes, /129 × 53 \(rows × columns\)/);
  assert.match(labels.notes, /Native spacing: 1\.0117 m/);
  assert.match(labels.fleet, /4\.05 × 9\.97 km \(east × south\), 40\.4 km²/);
  assert.match(labels.fleet, /models are enlarged/);
  data.metadata.extent_m = 999999; delete data.metadata.extent_m_axes;
  data.metadata.effective_spacing_m = 1;
  assert.deepEqual(labelsFor(data), labels, 'legacy scalar metadata cannot square or stretch the actual grid');
  const mola = rectangularTerrain(4, 7, 921.99, 926.12); mola.source = 'nasa-pds-mola'; mola.metadata = {spacing_m: {east: 921.99, south: 926.12}, extent_m: {east: 5531.94, south: 2778.36}};
  const regional = labelsFor(mola);
  assert.equal(regional.caption, 'MOLA archive · 5.53 × 2.78 km');
  assert.equal(regional.source, 'NASA MGS / MOLA · 922.0 × 926.1 m display step');
  assert.doesNotMatch(regional.notes, /Native spacing/);
});

test('drawer geometry is constrained and accessible across desktop and mobile', () => {
  const css = read('static/mission.css');
  assert.match(css, /width:350px/); assert.match(css, /overflow-x:hidden/);
  assert.match(read('static/style.css'), /box-sizing:border-box/);
  assert.match(css, /overflow-y:auto/); assert.match(css, /@media\(max-width:760px\)/);
  for (const pane of ['equipment', 'guardian', 'sessions', 'logs', 'settings']) {
    assert.match(html, new RegExp(`id="${pane}" class="drawer-pane"`));
    assert.match(html, new RegExp(`aria-controls="${pane}"`));
  }
  assert.match(html, /id="paste-token"/); assert.match(html, /aria-live="polite"/);
});

test('Guardian controls, incident labels and low-confidence cues are wired', () => {
  const css = read('static/mission.css');
  for (const name of ['refreshGuardian', 'updateGuardianControls', 'resetValidation', 'guardianAction', 'renderIncidents']) assert.match(js, new RegExp(`function ${name}\\(`));
  for (const selector of ['#guardian', '.guardian-risk', '#guardian-meter', '.confidence-warning', '.guardian-controls', '.model-actions', '.carrier-badge', '.carrier-id', '.carrier-risk', '.incident-card']) assert.ok(css.includes(selector), selector);
  for (const risk of ['nominal', 'warning', 'critical']) assert.ok(css.includes(`[data-risk='${risk}']`));
  assert.match(js, /action: 'fault', fault: b\.dataset\.simFault/);
  assert.match(js, /approved: true, candidateVersion/); assert.match(js, /status\.candidateReady === true/);
  assert.match(js, /select\.reportValidity\(\)/);
  assert.match(html, /id="scan-telemetry"/); assert.match(html, /id="scan-guardian"/);
  assert.match(js, /!archived\(activeScan\) && now - activeScan\.receivedAt > 30/);
});

test('downloads use Authorization and Blob URLs; credentials stay in page memory', () => {
  assert.match(js, /Authorization: `Bearer \$\{auth\}`/);
  assert.match(js, /response\.blob\(\)/); assert.match(js, /URL\.createObjectURL\(blob\)/);
  assert.match(js, /URL\.revokeObjectURL/);
  assert.doesNotMatch(js, /localStorage|sessionStorage|document\.cookie/);
  const download = js.match(/async function download\([^]*?\n  }/)[0];
  assert.doesNotMatch(download, /token|searchParams/);
  assert.match(js, /gl\.enable\(gl\.DEPTH_TEST\)/);
  assert.match(js, /polygonal: minimal\.concat\(diagonals\)/);
});

function terrainHarness() {
  const calls = [], listeners = new Map(), raf = [];
  const constants = ['VERTEX_SHADER', 'FRAGMENT_SHADER', 'COMPILE_STATUS', 'LINK_STATUS', 'ARRAY_BUFFER', 'ELEMENT_ARRAY_BUFFER', 'STATIC_DRAW', 'DYNAMIC_DRAW', 'FLOAT', 'TRIANGLES', 'LINES', 'LINE_STRIP', 'DEPTH_TEST', 'LEQUAL', 'POLYGON_OFFSET_FILL', 'UNSIGNED_SHORT', 'COLOR_BUFFER_BIT', 'DEPTH_BUFFER_BIT'];
  const target = Object.fromEntries(constants.map((c, i) => [c, i + 1]));
  const gl = new Proxy(target, {get: (object, key) => key in object ? object[key] : (...args) => {
    calls.push({name: key, args});
    if (key === 'getShaderParameter' || key === 'getProgramParameter') return true;
    if (key === 'createBuffer') return {};
    if (key === 'getUniformLocation') return args[1];
    return 1;
  }});
  const canvas = {clientWidth: 1100, clientHeight: 800, dataset: {}, getContext: () => gl, addEventListener: (name, handler) => listeners.set(name, handler), setPointerCapture() {}, focus() {}};
  const code = read('static/app.js');
  const Terrain = vm.runInNewContext(`const wrapAngle = angle => Math.atan2(Math.sin(angle), Math.cos(angle));
    const fleetColors = ['#eeae76', '#80cdb5', '#8fbde7', '#c6a3df', '#d9ce86', '#ed9da7'];
    ${code.slice(code.indexOf('  class Terrain {'), code.indexOf('  let terrain,'))}; Terrain`, {
    ResizeObserver: class { observe() {} }, requestAnimationFrame: callback => { raf.push(callback); return raf.length; }, devicePixelRatio: 1
  });
  return {terrain: new Terrain(canvas), gl, calls, listeners, flush: () => { while (raf.length) raf.shift()(); }};
}

test('rectangular meshes preserve world proportions, cover edge cells and stay within Uint16 indices', () => {
  for (const cols of [40, 53, 87]) {
    const {terrain, gl, calls, flush} = terrainHarness(), rows = 129, data = rectangularTerrain(rows, cols);
    terrain.load(data);
    const cells = (rows - 1) * (cols - 1), vertices = rows * cols + cells;
    assert.equal(terrain.normalized.length / 3, vertices);
    assert.equal(terrain.counts.triangles, cells * 12);
    assert.equal(terrain.counts.minimal, 2 * (rows * (cols - 1) + cols * (rows - 1)));
    assert.equal(terrain.counts.polygonal, terrain.counts.minimal + cells * 8);
    for (const call of calls.filter(c => c.name === 'bufferData' && c.args[0] === gl.ELEMENT_ARRAY_BUFFER)) {
      const indices = call.args[1]; assert.equal(indices.BYTES_PER_ELEMENT, 2);
      assert.ok([...indices].every(i => i >= 0 && i < vertices));
    }
    const triangles = calls.find(c => c.name === 'bufferData' && c.args[0] === gl.ELEMENT_ARRAY_BUFFER).args[1];
    assert.ok([...triangles].includes(vertices - 1), 'last cell centre retains its unwrapped index');
    const nw = terrain.normalize(data.points[0]), ne = terrain.normalize(data.points[cols - 1]), sw = terrain.normalize(data.points[(rows - 1) * cols]);
    assert.ok(Math.abs((ne[0] - nw[0]) / (sw[2] - nw[2]) - (cols - 1) / (rows - 1)) < 1e-10);
    assert.ok(Math.abs((terrain.normalize(data.points[1])[0] - nw[0]) - (terrain.normalize(data.points[cols])[2] - nw[2])) < 1e-10, 'equal metre steps stay equal after normalization');
    const position = data.points[Math.floor(rows / 2) * cols + Math.floor(cols / 2)];
    terrain.setFleet({simulation: true, terrainSource: data.source, coverage: {cells: [[rows - 2, cols - 2]]}, rovers: [{carrierId: 'diagram-marker', position, headingDeg: 0}]}); flush();
    assert.equal(terrain.fleetGeometry[0].count, 12);
    const upload = calls.filter(c => c.name === 'bufferData' && c.args[2] === gl.DYNAMIC_DRAW).at(-1).args[1];
    const corner = terrain.normalize(data.points[(rows - 2) * cols + cols - 2]);
    for (const k of [0, 2]) assert.ok(Math.abs(upload[k] - corner[k]) < 1e-6);
    assert.ok([...upload].every(Number.isFinite));
    assert.equal(terrain.fleetAnchors[0].visualScale, .5);
    const origin = terrain.normalize(position), model = upload.slice(terrain.fleetGeometry[1].first * 3);
    let radiusM = 0;
    for (let i = 0; i < model.length; i += 3) radiusM = Math.max(radiusM, Math.hypot(model[i] - origin[0], model[i + 2] - origin[2]) * terrain.extent / 2);
    assert.ok(radiusM > 5 && radiusM < 25, 'model dimensions stay fixed in map metres on every rectangular terrain');
    assert.equal(terrain.pitch, .8);
  }
  const {terrain} = terrainHarness();
  assert.throws(() => terrain.load(rectangularTerrain(256, 129)), /vertex limit/, 'cell-centre vertices count toward the index budget');
});

test('camera supports complete vertical and horizontal revolutions, keyboard zoom and reset', () => {
  const {terrain, listeners} = terrainHarness();
  const key = key => { let prevented = false; listeners.get('keydown')({key, preventDefault() { prevented = true; }}); assert.ok(prevented); };
  const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} versus ${b}`);
  const wrap = n => Math.atan2(Math.sin(n), Math.cos(n));
  for (let n = 0; n < 120; n++) key('ArrowDown');
  near(terrain.pitch, wrap(.8 + 12));
  for (let n = 0; n < 120; n++) key('ArrowUp');
  near(terrain.pitch, .8);
  for (let n = 0; n < 120; n++) key('ArrowLeft');
  near(terrain.yaw, wrap(-.5 - 12));
  key('r'); near(terrain.yaw, -.5);
  listeners.get('pointerdown')({button: 0, clientX: 20, clientY: 30, pointerId: 1});
  listeners.get('pointermove')({clientX: 3020, clientY: 3030});
  near(terrain.yaw, wrap(-.5 + 18)); near(terrain.pitch, wrap(.8 + 15));
  listeners.get('lostpointercapture')({});
  const stopped = terrain.pitch; listeners.get('pointermove')({clientX: 4020, clientY: 4030}); near(terrain.pitch, stopped);
  for (let n = 0; n < 80; n++) key('+'); near(terrain.zoom, 2.3);
  for (let n = 0; n < 80; n++) key('-'); near(terrain.zoom, .55);
  listeners.get('wheel')({deltaY: -100000, preventDefault() {}}); near(terrain.zoom, 2.3);
  key('R'); near(terrain.zoom, 1); near(terrain.pitch, .8); near(terrain.yaw, -.5);
  terrain.draw();
  near(Number(terrain.canvas.dataset.pitch), .8); near(Number(terrain.canvas.dataset.yaw), -.5); near(Number(terrain.canvas.dataset.zoom), 1);
});

function fleetFixture() {
  const grid = JSON.parse(read('static/data/hirise-gale.json'));
  const {rows, cols} = grid.grid, row = Math.floor((rows - 1) / 2), col = Math.floor((cols - 1) / 2);
  const position = grid.points[row * cols + col], totalCells = (rows - 1) * (cols - 1);
  const areaM2 = (grid.points[1][0] - grid.points[0][0]) * (grid.points[cols][2] - grid.points[0][2]);
  return {running: true, count: 3, speedMultiplier: 60, elapsedS: 120, terrainSource: 'nasa-pds-hirise', simulation: true,
    coverage: {scannedCells: 1, totalCells, percent: 100 / totalCells, areaM2, totalAreaM2: areaM2 * totalCells, cells: [[row, col]]},
    rovers: Array.from({length: 3}, (_, i) => ({carrierId: `fleet-rover-${i + 1}`, position: [...position], headingDeg: i * 90, status: i ? 'responding' : 'halted', fault: i ? 'nominal' : 'dust', guardian: null, targetId: i ? 'fleet-rover-1' : null, assignedSector: `sector-${i + 1}`, trail: [grid.points[row * cols + Math.max(0, col - 1)], position]})),
    events: [{id: 1, ts: 100, type: 'guardian_halt', roverId: 'fleet-rover-1', targetId: null, message: 'Safety halt'}, {id: 2, ts: 101, type: 'assistance_dispatch', roverId: 'fleet-rover-2', targetId: 'fleet-rover-1', message: 'Inspection planned'}]};
}

test('fleet coverage, trails and markers share source normalization, camera uniforms and depth occlusion', () => {
  const {terrain, gl, calls, flush} = terrainHarness(), data = JSON.parse(read('static/data/hirise-gale.json')), state = fleetFixture();
  terrain.load(data); terrain.setFleet(state); flush();
  assert.ok(terrain.project([0, .02, 0]).depth < terrain.project([0, 0, 0]).depth, 'default camera views the top: raised geometry is closer than its terrain surface');
  assert.ok(terrain.fleetGeometry.length >= 7, 'coverage, three trails, three heading markers and a fault halo');
  const upload = calls.filter(c => c.name === 'bufferData' && c.args[2] === gl.DYNAMIC_DRAW).at(-1).args[1];
  const [row, col] = state.coverage.cells[0], {rows, cols} = data.grid;
  const corner = terrain.normalize(data.points[row * cols + col]);
  for (const k of [0, 2]) assert.ok(Math.abs(upload[k] - corner[k]) < 1e-6, 'coverage uses archive x/z without a second projection');
  const coverageLiftM = (upload[1] - corner[1]) * terrain.extent / 2;
  assert.ok(coverageLiftM > 0 && coverageLiftM < .1, 'coverage tint stays on the surface beneath rover wheels');
  assert.equal(terrain.fleetGeometry[0].count, 12, 'cell uses the same four centre triangles as the depth pass');
  assert.ok([...upload].every(Number.isFinite));
  const originalProjection = JSON.parse(terrain.canvas.dataset.fleetMarkers);
  assert.equal(originalProjection.length, 3);
  assert.equal(originalProjection[0].carrierId, state.rovers[0].carrierId);
  assert.ok(originalProjection.every(p => Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.depth)));
  const before = [...upload]; terrain.yaw = 2.1; terrain.pitch = 2.5; terrain.scale = 3; terrain.draw();
  assert.notDeepEqual(JSON.parse(terrain.canvas.dataset.fleetMarkers), originalProjection, 'marker projections follow the same 3D view');
  assert.deepEqual([...upload], before, 'orbit and elevation use shared shader uniforms rather than screen-space coordinates');
  for (const [key, value] of [['yaw', 2.1], ['pitch', 2.5], ['elevation', 3]]) assert.ok(calls.some(c => c.name === 'uniform1f' && c.args[0] === key && c.args[1] === value));
  assert.ok(calls.some(c => c.name === 'enable' && c.args[0] === gl.DEPTH_TEST));
  assert.ok(!calls.some(c => c.name === 'disable' && c.args[0] === gl.DEPTH_TEST), 'fleet never bypasses hills');
  assert.ok(calls.some(c => c.name === 'drawArrays'));
  const originalCount = terrain.fleetGeometry[0].count;
  state.coverage.cells.push([row, col], [-1, 0], [rows - 1, cols - 1], [0, cols], [NaN, 0]); terrain.setFleet(state);
  assert.equal(terrain.fleetGeometry[0].count, originalCount, 'invalid and duplicate cell addresses are ignored');
  terrain.load(JSON.parse(read('static/data/mola-gale.json'))); assert.equal(terrain.fleetGeometry.length, 0, 'HiRISE fleet cannot leak into the regional MOLA frame');
  terrain.load(data); assert.ok(terrain.fleetGeometry.length);
  terrain.setFleet({...state, simulation: false}); assert.equal(terrain.fleetGeometry.length, 0, 'live Quest coordinates cannot enter the archive');
  terrain.setFleet(null); assert.equal(terrain.fleetGeometry.length, 0);
});

function fleetHarness({publicAccess = false} = {}) {
  class Element {
    constructor(tag = 'div') { this.tagName = tag; this.children = []; this.dataset = {}; this.style = {setProperty() {}}; this.listeners = {}; this.textContent = ''; this.disabled = false; this.hidden = false; this._value = ''; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; this._value = ''; }
    get options() { return this.children; }
    get value() { return this._value || (this.tagName === 'select' ? this.children[0]?.value || '' : ''); }
    set value(value) { this._value = String(value); }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    click() { this.listeners.click?.(); }
    reportValidity() { return Number.isInteger(Number(this.value)) && Number(this.value) >= 1 && Number(this.value) <= 120; }
  }
  const elements = new Map([...html.matchAll(/<([\w-]+)\b[^>]*\bid="([^"]+)"/g)].map(m => [m[2], new Element(m[1])]));
  const actions = ['start', 'stop', 'step', 'reset'].map(action => { const b = new Element('button'); b.dataset.fleetAction = action; return b; });
  const timers = new Map(), requests = [], geometry = []; let timerId = 0, transport;
  const source = read('static/app.js');
  const scope = vm.runInNewContext(`
    let token = ${JSON.stringify(publicAccess ? '' : 'test-viewer')}, publicAccess = ${publicAccess}, publicConnected = ${publicAccess}, epoch = 1, fleetState = null, fleetPoll = null, fleetRequest = 0, fleetBusy = false, fleetAvailable = null, fleetSnapshot = '';
    const endpoints = {fleet: '/api/sim/fleet'};
    const $ = id => document.getElementById(id);
    const fleetColors = ['#eeae76', '#80cdb5', '#8fbde7', '#c6a3df', '#d9ce86', '#ed9da7'];
    ${source.slice(source.indexOf('  function node('), source.indexOf('  function button('))}
    ${source.slice(source.indexOf('  const hasViewer ='), source.indexOf('  async function api('))}
    ${source.slice(source.indexOf('  async function api('), source.indexOf('  async function download('))}
    ${source.slice(source.indexOf('  const number ='), source.indexOf('  function updateFleetControls('))}
    ${source.slice(source.indexOf('  function updateFleetControls('), source.indexOf('  function telemetrySummary('))}
    ({updateFleetControls, renderFleet, refreshFleet, fleetAction, startFleetPolling, disconnect() { epoch++; token = ''; publicConnected = false; resetFleet(); }, state() { return fleetState; }})`, {
    document: {getElementById: id => elements.get(id), createElement: tag => new Element(tag), createTextNode: text => ({textContent: text}), querySelectorAll: selector => selector === '[data-fleet-action]' ? actions : []},
    terrain: {setFleet: state => geometry.push(state)}, refreshGuardian() {},
    setTimeout: callback => { timers.set(++timerId, callback); return timerId; }, clearTimeout: id => timers.delete(id),
    fetch: async (path, options) => { requests.push({path, options}); return transport(path, options); }
  });
  elements.get('terrain-select').value = 'hirise'; elements.get('fleet-count').value = '3'; elements.get('fleet-speed').value = '60'; elements.get('fleet-fault').value = 'dust';
  return {scope, elements, actions, timers, requests, geometry, transport: fn => { transport = fn; }, response: (state, status = 200) => ({ok: status === 200, status, json: async () => state})};
}

test('fleet polling authenticates as viewer, tolerates missing service and refreshes with the drawer closed', async () => {
  const h = fleetHarness(); h.transport(() => h.response({}, 404));
  await h.scope.refreshFleet();
  assert.match(h.elements.get('fleet-message').textContent, /awaiting server support/);
  assert.equal(h.requests[0].options.headers.Authorization, 'Bearer test-viewer');
  await h.scope.refreshFleet(); assert.equal(h.requests.length, 1, 'do not hammer an unsupported endpoint');
  h.transport(() => h.response(fleetFixture())); h.elements.get('guardian').hidden = true;
  await h.scope.refreshFleet(true);
  assert.equal(h.elements.get('fleet-map').hidden, false);
  assert.equal(h.elements.get('fleet-rovers').children.length, 3);
  assert.equal(h.elements.get('fleet-summary-rovers').children.length, 3);
  assert.equal(h.elements.get('fleet-summary').hidden, false);
  assert.equal(h.elements.get('fleet-events').children[0].dataset.event, '2', 'newest events come first');
  assert.ok(h.geometry.at(-1).simulation);
  h.scope.startFleetPolling(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.timers.size, 1); assert.ok(h.requests.length >= 3);
  h.scope.disconnect(); assert.equal(h.timers.size, 0); assert.equal(h.geometry.at(-1), null);
  assert.equal(h.elements.get('fleet-map').hidden, true); assert.equal(h.elements.get('fleet-coverage').value, '0');
  assert.equal(h.elements.get('fleet-target').value, ''); assert.equal(h.elements.get('fleet-summary').hidden, true);
});

test('fleet commands use existing producer access, explicit target/cause and acknowledged state only', async () => {
  const h = fleetHarness(); h.scope.renderFleet(fleetFixture());
  h.transport((_path, options) => h.response({ok: true, fleetState: {...fleetFixture(), running: JSON.parse(options.body).action === 'start'}}));
  await h.scope.fleetAction('start'); assert.equal(h.requests.length, 0, 'producer is required');
  h.elements.get('producer-token').value = 'test-producer';
  h.elements.get('fleet-speed').value = '121'; await h.scope.fleetAction('start'); assert.equal(h.requests.length, 0, 'out-of-range speed is rejected');
  h.elements.get('fleet-speed').value = '60';
  for (const action of ['start', 'stop', 'step', 'reset']) {
    await h.scope.fleetAction(action);
    const request = h.requests.at(-1);
    assert.equal(request.path, '/api/sim/fleet'); assert.equal(request.options.method, 'POST'); assert.equal(request.options.headers.Authorization, 'Bearer test-producer');
    assert.deepEqual(JSON.parse(request.options.body), {action, ...(['start', 'reset'].includes(action) ? {count: 3, speedMultiplier: 60, autoRepair: true} : {})});
  }
  h.elements.get('fleet-target').value = 'fleet-rover-2'; h.elements.get('fleet-fault').value = 'wheel_slip';
  await h.scope.fleetAction('fault');
  assert.deepEqual(JSON.parse(h.requests.at(-1).options.body), {action: 'fault', roverId: 'fleet-rover-2', fault: 'wheel_slip'});
  const acknowledged = h.scope.state();
  h.transport(() => h.response({}, 403)); await h.scope.fleetAction('fault');
  assert.equal(h.scope.state(), acknowledged); assert.match(h.elements.get('fleet-message').textContent, /Token was not accepted/);
  assert.equal(h.elements.get('fleet-target').value, 'fleet-rover-2', 'polling and commands preserve operator fault selection');
});

test('fleet access instructions persist across polling and keep authentication gates intact', async () => {
  const h = fleetHarness(); h.scope.renderFleet(fleetFixture());
  const access = h.elements.get('fleet-access-status');
  const start = /data-fleet-action="start"[^>]*aria-describedby="fleet-access-status"/;
  assert.match(html, start);
  assert.match(access.textContent, /Enter a producer token in Operator access/);
  assert.ok(h.actions.every(b => b.disabled));
  assert.equal(h.elements.get('fleet-enter-producer').hidden, false);
  assert.equal(h.elements.get('fleet-enter-producer').disabled, false);
  h.transport(() => h.response(fleetFixture()));
  await h.scope.refreshFleet();
  assert.match(access.textContent, /Enter a producer token in Operator access/, 'successful polling cannot hide the missing role');
  await h.scope.fleetAction('start');
  assert.equal(h.requests.filter(r => r.options.method === 'POST').length, 0);
  h.elements.get('producer-token').value = 'test-producer'; h.scope.updateFleetControls();
  assert.match(access.textContent, /Fleet controls are available/);
  assert.ok(h.actions.every(b => !b.disabled));
  assert.equal(h.elements.get('fleet-access-steps').hidden, true);
  h.scope.disconnect();
  assert.match(access.textContent, /Connect a viewer in Equipment and live/);
  assert.ok(h.actions.every(b => b.disabled));
  assert.equal(h.elements.get('fleet-connect-viewer').hidden, false);
  assert.equal(h.elements.get('fleet-connect-viewer').disabled, false);
});

test('fleet access distinguishes loading, an in-flight command and an unavailable service', async () => {
  const h = fleetHarness(); h.elements.get('producer-token').value = 'test-producer';
  const access = h.elements.get('fleet-access-status');
  h.scope.updateFleetControls(); assert.match(access.textContent, /Loading fleet state/);
  h.scope.renderFleet(fleetFixture());
  let release;
  h.transport(() => new Promise(resolve => { release = resolve; }));
  const pending = h.scope.fleetAction('start');
  assert.match(access.textContent, /Applying fleet command/);
  assert.ok(h.actions.every(b => b.disabled));
  release(h.response({ok: true, fleetState: fleetFixture()})); await pending;
  assert.match(access.textContent, /Fleet controls are available/);
  h.transport(() => h.response({}, 404)); await h.scope.refreshFleet();
  assert.match(access.textContent, /Fleet service unavailable.*Refresh fleet/);
  assert.ok(h.actions.every(b => b.disabled));
  assert.equal(h.elements.get('refresh-fleet').disabled, false);
});

test('Mission Control decisions bind to the current recovery request and require producer access', async () => {
  const h = fleetHarness(), state = fleetFixture();
  state.rovers[0].fault = 'sensor_drop';
  state.rovers[0].recovery = {phase: 'awaiting_approval', requestId: 71, requiresApproval: true, approved: false, held: false, progress: 0};
  h.scope.renderFleet(state);
  assert.equal(h.elements.get('fleet-approvals').hidden, false);
  assert.equal(h.elements.get('fleet-approval-list').children.length, 1);
  assert.match(h.elements.get('fleet-map-recovery').textContent, /1 decision in Guardian/);
  await h.scope.fleetAction('approve_recovery', {roverId: state.rovers[0].carrierId, requestId: 71});
  assert.equal(h.requests.length, 0, 'viewer alone cannot send a recovery decision');
  h.elements.get('producer-token').value = 'test-producer';
  await h.scope.fleetAction('approve_recovery', {roverId: state.rovers[0].carrierId, requestId: 70});
  assert.equal(h.requests.length, 0, 'a stale UI request cannot authorize newer work');
  const next = structuredClone(state); next.rovers[0].recovery.phase = 'en_route'; next.rovers[0].recovery.approved = true;
  h.transport(() => h.response({ok: true, fleetState: next}));
  await h.scope.fleetAction('approve_recovery', {roverId: state.rovers[0].carrierId, requestId: 71});
  assert.deepEqual(JSON.parse(h.requests.at(-1).options.body), {action: 'approve_recovery', roverId: state.rovers[0].carrierId, requestId: 71});
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer test-producer');
  assert.equal(h.elements.get('fleet-approvals').hidden, true);
});

test('minor recovery mode uses acknowledged server state and rolls back a rejected change', async () => {
  const h = fleetHarness(), state = fleetFixture(); state.autoRepair = true;
  h.scope.renderFleet(state); h.elements.get('producer-token').value = 'test-producer';
  h.elements.get('fleet-auto-repair').checked = false;
  h.transport(() => h.response({ok: true, fleetState: {...state, autoRepair: false}}));
  await h.scope.fleetAction('configure');
  assert.deepEqual(JSON.parse(h.requests.at(-1).options.body), {action: 'configure', autoRepair: false});
  assert.equal(h.scope.state().autoRepair, false);
  h.elements.get('fleet-auto-repair').checked = true;
  h.transport(() => h.response({}, 401)); await h.scope.fleetAction('configure');
  assert.equal(h.elements.get('fleet-auto-repair').checked, false);
  assert.equal(h.scope.state().autoRepair, false);
});

test('late fleet GETs cannot replace acknowledged commands or restore a disconnected map', async () => {
  const h = fleetHarness(); h.scope.renderFleet(fleetFixture()); h.elements.get('producer-token').value = 'test-producer';
  let release;
  h.transport((_path, options) => options.method === 'POST' ? h.response({ok: true, fleetState: {...fleetFixture(), running: false}}) : new Promise(resolve => { release = resolve; }));
  const pending = h.scope.refreshFleet(); await h.scope.fleetAction('stop');
  release(h.response(fleetFixture())); await pending; assert.equal(h.scope.state().running, false);
  const next = h.scope.refreshFleet(); h.scope.disconnect(); release(h.response(fleetFixture())); await next;
  assert.equal(h.scope.state(), null); assert.equal(h.elements.get('fleet-map').hidden, true);
  let releaseCommand;
  // Exercise a separate connected generation for the command-in-flight case.
  const fresh = fleetHarness(); fresh.scope.renderFleet(fleetFixture()); fresh.elements.get('producer-token').value = 'test-producer';
  fresh.transport(() => new Promise(resolve => { releaseCommand = resolve; }));
  const command = fresh.scope.fleetAction('reset'); fresh.scope.disconnect(); releaseCommand(fresh.response({ok: true, fleetState: fleetFixture()})); await command;
  assert.equal(fresh.scope.state(), null); assert.equal(fresh.geometry.at(-1), null);
});

test('public fleet polling and commands work without viewer or producer credentials', async () => {
  const h = fleetHarness({publicAccess: true});
  h.transport((_path, options) => h.response(options.method === 'POST' ? {ok: true, fleetState: fleetFixture()} : fleetFixture()));
  await h.scope.refreshFleet();
  assert.ok(h.actions.every(b => !b.disabled));
  assert.equal(h.elements.get('fleet-access-steps').hidden, true);
  assert.match(h.elements.get('fleet-access-status').textContent, /Public simulation/);
  for (const action of ['start', 'stop', 'step', 'reset', 'configure', 'fault']) await h.scope.fleetAction(action);
  assert.equal(h.requests.filter(r => r.options.method === 'POST').length, 6);
  for (const {options} of h.requests) assert.equal(options.headers.Authorization, undefined);
  assert.equal(h.elements.get('producer-token').value, '');
  h.scope.disconnect();
  assert.ok(h.actions.every(b => b.disabled));
  assert.match(h.elements.get('fleet-access-status').textContent, /Select Reconnect/);
  const count = h.requests.length;
  await h.scope.fleetAction('start'); await h.scope.refreshFleet();
  assert.equal(h.requests.length, count);
});

test('public recovery still needs an explicit decision for the current request', async () => {
  const h = fleetHarness({publicAccess: true}), state = fleetFixture();
  state.rovers[0].recovery = {phase: 'awaiting_approval', requestId: 71, held: false};
  h.scope.renderFleet(state);
  h.transport(() => h.response({ok: true, fleetState: state}));
  assert.equal(h.requests.length, 0, 'rendering an approval request never approves it');
  await h.scope.fleetAction('approve_recovery', {roverId: state.rovers[0].carrierId, requestId: 70});
  assert.equal(h.requests.length, 0, 'stale approvals stay blocked in public mode');
  for (const action of ['hold_recovery', 'approve_recovery']) {
    await h.scope.fleetAction(action, {roverId: state.rovers[0].carrierId, requestId: 71});
    assert.deepEqual(JSON.parse(h.requests.at(-1).options.body), {action, roverId: state.rovers[0].carrierId, requestId: 71});
    assert.equal(h.requests.at(-1).options.headers.Authorization, undefined);
  }
});

function discoveryHarness(response) {
  const source = read('static/app.js'), calls = [], elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, {textContent: '', hidden: false, disabled: false}); return elements.get(id); };
  const scope = vm.runInNewContext(`
    let accessRequest = 0, epoch = 0, publicAccess = false, publicConnected = false;
    const $ = get, endpoints = {config: '/api/config'};
    function disconnect() { epoch++; publicConnected = false; }
    function updateAccessUI() { calls.push(['access', publicAccess]); }
    function updateGuardianControls() { calls.push(['controls', publicAccess && publicConnected]); }
    function state(text) { calls.push(['status', text]); }
    ${source.slice(source.indexOf('  async function discoverAccess('), source.indexOf('  function updateAccessUI('))}
    ({discoverAccess, access: () => ({publicAccess, publicConnected})})`, {
    get, calls, AbortSignal,
    window: {LabShell: {openPanel: id => calls.push(['panel', id])}},
    fetch: async (url, options) => { calls.push(['fetch', url, options]); if (response instanceof Error) throw response; return response; },
    openSocket: () => calls.push(['socket']), startFleetPolling: () => calls.push(['fleet']),
    ...Object.fromEntries(['latest', 'refreshSessions', 'refreshLogs', 'refreshStats', 'refreshGuardian'].map(name => [name, async () => { calls.push([name]); }]))
  });
  return {scope, calls, elements};
}

test('config alone enables public startup, loads all services and opens Guardian', async () => {
  const h = discoveryHarness({ok: true, json: async () => ({publicAccess: true})});
  await h.scope.discoverAccess();
  assert.deepEqual({...h.scope.access()}, {publicAccess: true, publicConnected: true});
  assert.deepEqual(h.calls.find(c => c[0] === 'panel'), ['panel', 'guardian']);
  for (const service of ['socket', 'fleet', 'latest', 'refreshSessions', 'refreshLogs', 'refreshStats', 'refreshGuardian']) assert.ok(h.calls.some(c => c[0] === service), service);
  const [, url, options] = h.calls.find(c => c[0] === 'fetch');
  assert.equal(url, '/api/config'); assert.equal(options.cache, 'no-store'); assert.equal(options.headers, undefined);
  assert.equal(h.elements.get('reconnect-lab').disabled, false);
});

test('private, unavailable and malformed config never open unauthenticated services', async () => {
  for (const response of [{ok: true, json: async () => ({publicAccess: false})}, {ok: false}, new Error('offline'), ...[{}, null, {publicAccess: 'true'}, {publicAccess: 1}].map(data => ({ok: true, json: async () => data}))]) {
    const h = discoveryHarness(response); await h.scope.discoverAccess();
    assert.deepEqual({...h.scope.access()}, {publicAccess: false, publicConnected: false});
    assert.ok(!h.calls.some(c => ['socket', 'fleet', 'panel', 'latest'].includes(c[0])));
    assert.equal(h.elements.get('reconnect-lab').disabled, false);
  }
});

test('public assets are cache-versioned and initial Guardian copy has no auth instruction', () => {
  for (const asset of ['app.js', 'shell.js']) assert.ok(html.includes(`/static/${asset}?v=public-20261115`));
  assert.ok(html.includes('/static/mission.css?v=rover-buttons-20261115'));
  assert.match(html, /id="guardian-carrier">No current Guardian telemetry\./);
  assert.match(js, /document\.body\.dataset\.publicAccess = String\(publicAccess\)/);
  assert.match(js, /if \(!publicAccess\) url\.searchParams\.set\('token', token\)/);
});
