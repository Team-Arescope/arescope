const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const html = read('static/index.html');
const js = read('static/app.js') + '\n' + read('static/shell.js');

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
  const routes = [...read('app.py').matchAll(/@app\.(get|post|delete|websocket)\("([^"]+)"/g)].map(m => ({method: m[1], route: m[2]}));
  const calls = [...js.matchAll(/["'`]((?:\/api\/live\/)[^"'`\s]+)/g)].map(m => m[1]);
  assert.ok(calls.length >= 9);
  const normalize = p => p.split('?')[0].replace(/\$\{[^}]+\}/g, '{}').replace(/\{[^}]+\}/g, '{}');
  for (const call of calls) assert.ok(routes.some(r => normalize(r.route) === normalize(call)), call);
  const producerOnly = routes.filter(r => r.method === 'post');
  assert.deepEqual(producerOnly.map(r => r.route).sort(), ['/api/live/frame', '/api/live/log', '/api/live/mesh']);
  for (const route of routes.filter(r => r.route.startsWith('/api/live/') && r.method !== 'post')) {
    assert.ok(calls.some(call => normalize(route.route) === normalize(call)), `Unwired viewer route: ${route.route}`);
  }
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

for (const [name, size, source] of [['mola', 65, 'nasa-pds-mola'], ['hirise', 129, 'nasa-pds-hirise']]) {
  test(`${name} fixture is a finite, regular ${size}x${size} Gale grid with provenance`, () => {
    const data = JSON.parse(read(`static/data/${name}-gale.json`));
    assert.equal(data.source, source); assert.equal(data.frame, 'mars-local-metres');
    assert.deepEqual(data.grid, {rows: size, cols: size}); assert.equal(data.points.length, size * size);
    assert.equal(data.metadata.live, false); assert.match(data.metadata.source_url, /^https:\/\//);
    assert.ok(data.metadata.product_id); assert.match(data.metadata.units, /metres/);
    for (const point of data.points) assert.ok(Array.isArray(point) && point.length === 3 && point.every(Number.isFinite));
    const stepX = data.points[1][0] - data.points[0][0];
    const stepZ = data.points[size][2] - data.points[0][2];
    assert.ok(stepX > 0 && stepZ > 0);
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
      const p = data.points[r * size + c];
      assert.ok(Math.abs(p[0] - data.points[0][0] - c * stepX) < .001);
      assert.ok(Math.abs(p[2] - data.points[0][2] - r * stepZ) < .001);
    }
    assert.ok(new Set(data.points.map(p => p[1])).size > 100);
    if (name === 'hirise') {
      assert.ok(Math.abs(stepX - 8.093974) < .00001);
      assert.equal(data.metadata.native_spacing_m, 1.0117467945795);
    }
  });
}

test('drawer geometry is constrained and accessible across desktop and mobile', () => {
  const css = read('static/mission.css');
  assert.match(css, /width:350px/); assert.match(css, /overflow-x:hidden/);
  assert.match(read('static/style.css'), /box-sizing:border-box/);
  assert.match(css, /overflow-y:auto/); assert.match(css, /@media\(max-width:760px\)/);
  for (const pane of ['equipment', 'sessions', 'logs', 'settings']) {
    assert.match(html, new RegExp(`id="${pane}" class="drawer-pane"`));
    assert.match(html, new RegExp(`aria-controls="${pane}"`));
  }
  assert.match(html, /id="paste-token"/); assert.match(html, /aria-live="polite"/);
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
