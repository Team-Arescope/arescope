#!/usr/bin/env node
'use strict';

// Offline only. No LAB server is started and no application source is changed.
// NODE_PATH and PLAYWRIGHT_BROWSERS_PATH are respected. Playwright 1.56.1 is
// supplied by the caller, or resolved from --root/package.json.
// Optional story metadata: targetId, helperId, roverNames, terrainPath,
// camera: {yaw, pitch, elevation}. Poses/status/recovery are never rewritten.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const {createRequire} = require('node:module');

const WIDTH = 1920, HEIGHT = 1080, FPS = 30, COUNT = 900;
const usage = 'node render_fleet_demo.cjs --root <service-dir> --story <story.json> --out <frames-dir> --fps 30 [--preview-only] [--browser-path <chromium>]';

function args(argv) {
  const options = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (key === '--help' || key === '-h') return {help: true};
    if (key === '--preview-only') { options.preview = true; continue; }
    if (!['--root', '--story', '--out', '--fps', '--browser-path'].includes(key)) throw new Error(`Unknown argument: ${key}`);
    if (!argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error(`Missing value for ${key}`);
    options[key.slice(2)] = argv[++i];
  }
  for (const key of ['root', 'story', 'out']) if (!options[key]) throw new Error(`Missing --${key}\n${usage}`);
  if (Number(options.fps ?? FPS) !== FPS) throw new Error('The delivery is exactly 900 frames at 30 fps.');
  return options;
}

// Deliberately use explicit source boundaries and fail on an upstream refactor.
// The capture adapter reuses draw() from its GL setup through the final terrain
// and rover passes. Only its network/camera scheduling prefix is bypassed.
function rendererSource(source) {
  function between(start, end) {
    const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
    if (a < 0 || b < 0) throw new Error(`LAB source boundary missing: ${start}`);
    return source.slice(a, b).trim();
  }
  const helpers = between('const wrapAngle =', 'const bytes =');
  const terrain = between('class Terrain {', 'function terrainDimensions(data)');
  const dimensions = between('function terrainDimensions(data)', 'function terrainLabels(data)');
  if (!terrain.includes('gl.POLYGON_OFFSET_FILL') || !terrain.includes('serviceReachable')) throw new Error('Unrecognized LAB terrain/depth/contact implementation.');
  return `(() => { const $ = id => document.getElementById(id);\n${helpers}\n${terrain}\n${dimensions}\nwindow.LabDemo = {Terrain, terrainDimensions, fleetColors}; })();`;
}

function validateStory(story) {
  if (!Array.isArray(story.frames) || story.frames.length !== COUNT) throw new Error('story.frames must contain exactly 900 authoritative fleet states.');
  const names = ['fault', 'approach', 'repair', 'validate', 'recovered'];
  let previous = -1;
  for (const key of names) {
    const t = story.timeline?.[key];
    if (!Number.isFinite(t) || t <= previous || t >= COUNT / FPS) throw new Error(`Invalid ordered timeline.${key}`);
    previous = t;
  }
  const ids = story.frames[0]?.rovers?.map(r => r.carrierId);
  if (!ids || ids.length !== 3 || ids.some(id => typeof id !== 'string' || !id) || new Set(ids).size !== 3) throw new Error('Three uniquely identified rovers are required.');
  for (const [i, state] of story.frames.entries()) {
    if (state.simulation !== true || state.terrainSource !== 'nasa-pds-hirise') throw new Error(`Frame ${i}: expected a simulated fleet on NASA HiRISE archive terrain.`);
    if (state.rovers?.length !== 3 || new Set(state.rovers.map(r => r.carrierId)).size !== 3) throw new Error(`Frame ${i}: inconsistent rover count/IDs.`);
    for (const r of state.rovers) {
      if (!ids.includes(r.carrierId) || !Array.isArray(r.position) || r.position.length !== 3 || !r.position.every(Number.isFinite)) throw new Error(`Frame ${i}: invalid authoritative pose.`);
      if (r.headingDeg != null && !Number.isFinite(r.headingDeg)) throw new Error(`Frame ${i}: invalid headingDeg.`);
    }
  }
}

function playwright(root) {
  const local = createRequire(path.join(root, 'package.json'));
  for (const loader of [require, local]) for (const name of ['playwright', 'playwright-core']) {
    try { return loader(name); } catch (error) { if (error.code !== 'MODULE_NOT_FOUND') throw error; }
  }
  throw new Error('Playwright is missing. Supply 1.56.1 through NODE_PATH or the service node_modules.');
}

const hash = data => crypto.createHash('sha256').update(data).digest('hex');
async function main() {
  const options = args(process.argv.slice(2));
  if (options.help) { console.log(usage); return; }
  const root = path.resolve(options.root), out = path.resolve(options.out);
  const storyBytes = await fs.readFile(path.resolve(options.story));
  const story = JSON.parse(storyBytes);
  validateStory(story);
  const metadata = story.metadata || {};
  const terrainPath = path.resolve(root, story.terrainPath || metadata.terrainPath || 'static/data/hirise-gale.json');
  const [source, terrainBytes, template, manrope, mono] = await Promise.all([
    fs.readFile(path.join(root, 'static/app.js'), 'utf8'), fs.readFile(terrainPath),
    fs.readFile(path.join(__dirname, 'fleet_demo_capture.html'), 'utf8'),
    fs.readFile(path.join(root, 'static/fonts/manrope.woff2')),
    fs.readFile(path.join(root, 'static/fonts/dm-mono.woff2'))
  ]);
  const terrain = JSON.parse(terrainBytes);
  if (terrain.source !== 'nasa-pds-hirise') throw new Error('The capture requires the actual NASA HiRISE terrain JSON.');
  const library = rendererSource(source);
  const html = template.replace('__MANROPE_BASE64__', manrope.toString('base64')).replace('__DMMONO_BASE64__', mono.toString('base64'));
  const last = COUNT - 1;
  const previews = [...new Set([0, Math.round(4.5 * FPS), 8 * FPS, Math.min(last, Math.round((story.timeline.repair + 2) * FPS)), Math.min(last, Math.round((story.timeline.recovered + 2) * FPS)), last])].sort((a, b) => a - b);
  const indices = options.preview ? previews : Array.from({length: COUNT}, (_, i) => i);
  await fs.mkdir(out, {recursive: true});
  // A preview followed by a full capture may reuse the directory; these exact
  // output names are replaced. Unrelated files are neither touched nor removed.
  const {chromium} = playwright(root);
  let browser;
  const report = {
    complete: false, mode: options.preview ? 'preview' : 'full', width: WIDTH, height: HEIGHT,
    fps: FPS, expectedFrameCount: COUNT, capturedFrameCount: 0, timeline: story.timeline,
    previewIndices: previews, frameNaming: '%06d.png', storySha256: hash(storyBytes),
    appSha256: hash(source), terrainSha256: hash(terrainBytes), terrainPath,
    note: 'Authoritative story poses; original LAB model, fixed model scale, terrain triangles/depth and contact solver. Wheel rotation is a distance-driven visual animation, not wheel physics.',
    frames: [], warnings: [], browserErrors: []
  };
  try {
    browser = await chromium.launch({headless: true, ...(options['browser-path'] ? {executablePath: path.resolve(options['browser-path'])} : {}), args: [
      '--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
      '--hide-scrollbars', '--force-color-profile=srgb', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'
    ]});
    report.browserVersion = browser.version();
    const context = await browser.newContext({viewport: {width: WIDTH, height: HEIGHT}, deviceScaleFactor: 1, reducedMotion: 'no-preference', locale: 'en-US', timezoneId: 'UTC', colorScheme: 'dark', serviceWorkers: 'block'});
    // Every asset is injected from the filesystem; this cannot poll a live LAB.
    await context.route('**/*', route => route.abort());
    const page = await context.newPage();
    page.setDefaultTimeout(120000);
    page.on('pageerror', e => report.browserErrors.push(e.message));
    await page.setContent(html, {waitUntil: 'load'});
    await page.addScriptTag({content: library});
    report.setup = await page.evaluate(async payload => window.initializeDemo(payload), {story, terrain, fps: FPS});
    console.log(JSON.stringify({ready: true, out, mode: report.mode, indices: options.preview ? indices : '0..899', setup: report.setup}));
    for (const i of indices) {
      const frame = await page.evaluate(index => window.renderDemoFrame(index), i);
      if (report.browserErrors.length) throw new Error(report.browserErrors.at(-1));
      const filename = `${String(i).padStart(6, '0')}.png`;
      // renderDemoFrame calls gl.finish(). No RAF or wall-clock wait advances
      // the world while Chromium composites and writes this lossless frame.
      const png = await page.screenshot({path: path.join(out, filename), type: 'png', animations: 'disabled', fullPage: false, scale: 'css', timeout: 120000});
      if (png.readUInt32BE(16) !== WIDTH || png.readUInt32BE(20) !== HEIGHT) throw new Error(`Unexpected PNG size: ${filename}`);
      report.frames.push({...frame, file: filename, sha256: hash(png)});
      report.capturedFrameCount++;
      if (options.preview || i % FPS === 0 || i === last) console.log(JSON.stringify({frame: i, time: i / FPS, file: filename, captured: report.capturedFrameCount}));
    }
    // Seeking to a frame twice must return identical model/camera/arm state.
    const probeIndex = previews[3];
    const first = report.frames.find(f => f.index === probeIndex);
    const again = await page.evaluate(index => window.renderDemoFrame(index), probeIndex);
    report.deterministicState = JSON.stringify(again) === JSON.stringify(Object.fromEntries(Object.entries(first).filter(([key]) => !['file', 'sha256'].includes(key))));
    const repeatedPng = await page.screenshot({type: 'png', animations: 'disabled', scale: 'css'});
    report.deterministicPixels = hash(repeatedPng) === first.sha256;
    report.summary = await page.evaluate(() => window.demoSummary());
    report.warnings = report.summary.warnings;
    if (!report.deterministicState || !report.deterministicPixels) throw new Error('Repeated frame did not reproduce identical state and pixels.');
    report.complete = true;
    console.log(JSON.stringify({complete: true, captured: report.capturedFrameCount, deterministic: true, report: path.join(out, 'validation.json'), summary: report.summary}));
  } catch (error) {
    report.error = error.stack || String(error);
    throw error;
  } finally {
    await fs.writeFile(path.join(out, 'validation.json'), JSON.stringify(report, null, 2) + '\n');
    if (browser) await browser.close();
  }
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = {args, rendererSource, validateStory};
