import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Default QA checks both files offline. Generated files stay inside presentation/.
const baseDir = path.dirname(fileURLToPath(import.meta.url));
const deckPaths = [
  'Arescope — NASA Space Apps Challenge 2026.html',
  'Arescope — NASA Space Apps Challenge 2026 (Standalone).html'
].map(name => path.join(baseDir, name));
const cliTarget = process.argv[2];
const targets = cliTarget
  ? [{ name: 'custom', url: /^(https?:|file:)/i.test(cliTarget) ? cliTarget : pathToFileURL(path.resolve(cliTarget)).href }]
  : deckPaths.map((file, index) => ({ name: index ? 'standalone' : 'main', url: pathToFileURL(file).href }));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const failures = [], errors = [];
let currentTarget = 'startup', proc, ws, cdp, userDataDir;

function check(condition, message, details) {
  if (!condition) failures.push({ target: currentTarget, message, ...(details ? { details } : {}) });
}

async function main() {
  if (!cliTarget) assert.ok(fs.readFileSync(deckPaths[0]).equals(fs.readFileSync(deckPaths[1])), 'HTML deliverables are not synchronized');
  const chromePath = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  ].find(candidate => candidate && fs.existsSync(candidate));
  assert.ok(chromePath, 'Chrome/Chromium not found. Set CHROME_PATH.');
  const outDir = fs.mkdtempSync(path.join(baseDir, '.verify-slides-'));
  userDataDir = fs.mkdtempSync(path.join(baseDir, '.verify-chrome-'));
  console.log('SCREENSHOTS:', outDir);
  let browserStderr = '', launchError;
  proc = spawn(chromePath, [
    '--headless=new', '--remote-debugging-port=0',
    '--user-data-dir=' + userDataDir, '--window-size=1280,720',
    '--disable-gpu', '--disable-dev-shm-usage', '--disable-extensions',
    '--no-first-run', '--no-default-browser-check', 'about:blank'
  ], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true });
  proc.on('error', error => { launchError = error; });
  proc.stderr.on('data', data => { browserStderr = (browserStderr + data).slice(-4000); });
  let endpoint;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (launchError) throw launchError;
    if (proc.exitCode !== null) throw new Error('Chrome exited early: ' + browserStderr);
    try {
      const port = fs.readFileSync(path.join(userDataDir, 'DevToolsActivePort'), 'utf8').split('\n')[0].trim();
      const response = await fetch('http://127.0.0.1:' + port + '/json/list');
      endpoint = (await response.json()).find(target => target.type === 'page')?.webSocketDebuggerUrl;
      if (endpoint) break;
    } catch {}
    await sleep(200);
  }
  assert.ok(endpoint, 'No Chrome DevTools target: ' + browserStderr);
  ws = new WebSocket(endpoint);
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('CDP connection timed out')), 10000);
    ws.addEventListener('open', () => { clearTimeout(timeout); resolve(); }, { once: true });
    ws.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('CDP connection failed')); }, { once: true });
  });
  let sequence = 0;
  const pending = new Map();
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (pending.has(message.id)) {
      const request = pending.get(message.id);
      clearTimeout(request.timeout);
      pending.delete(message.id);
      if (message.error) request.reject(new Error(message.error.message));
      else request.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      const detail = message.params.exceptionDetails;
      errors.push({ target: currentTarget, type: 'exception', text: detail.exception?.description || detail.text });
    } else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') {
      errors.push({ target: currentTarget, type: 'console', text: message.params.args.map(arg => arg.description || String(arg.value)).join(' ') });
    } else if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') {
      errors.push({ target: currentTarget, type: 'browser', text: message.params.entry.text });
    }
  });
  ws.addEventListener('close', () => {
    for (const request of pending.values()) {
      clearTimeout(request.timeout);
      request.reject(new Error('CDP connection closed'));
    }
    pending.clear();
  });
  cdp = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 15000);
    pending.set(id, { resolve, reject, timeout });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression, arg) => {
    const result = await cdp('Runtime.evaluate', {
      expression: typeof expression === 'function' ? '(' + expression.toString() + ')(' + JSON.stringify(arg ?? null) + ')' : expression,
      returnByValue: true, awaitPromise: true
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  };
  const key = async (value, code, keyCode) => {
    const text = value === 'Enter' ? '\r' : value === ' ' ? ' ' : '';
    await cdp('Input.dispatchKeyEvent', { type: 'keyDown', key: value, code, windowsVirtualKeyCode: keyCode, text, unmodifiedText: text });
    await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key: value, code, windowsVirtualKeyCode: keyCode });
    await sleep(120);
  };
  const click = async selector => {
    await evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const point = await evaluate(selector => {
      const r = document.querySelector(selector).getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    }, selector);
    await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
    await cdp('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 });
    await cdp('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 });
    await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1279, y: 719 });
    await sleep(150);
  };
  const activeSlide = () => evaluate(() => [...document.querySelectorAll('.slide')].findIndex(slide => slide.classList.contains('on')) + 1);
  const linkState = () => evaluate(() => ({
    live: document.querySelector('[data-link="live"]')?.getAttribute('aria-pressed'),
    delay: document.querySelector('[data-link="delay"]')?.getAttribute('aria-pressed'),
    localAutonomy: !!document.getElementById('sub1')?.classList.contains('pulse-local'),
    cards: ['sub1', 'sub2', 'sub3'].map(id => document.getElementById(id)?.className ?? null),
    tags: ['tg1', 'tg2', 'tg3'].map(id => document.getElementById(id)?.textContent.trim() ?? ''),
    description: document.getElementById('linkDesc')?.textContent.trim() ?? ''
  }));
  const settle = async () => {
    await sleep(1900);
    await evaluate(() => Promise.all(document.querySelector('.slide.on').getAnimations({ subtree: true })
      .filter(animation => Number.isFinite(animation.effect.getComputedTiming().iterations))
      .map(animation => animation.finished.catch(() => {}))));
    await evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  };
  const screenshot = async (name, state) => {
    const shot = await cdp('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(outDir, name + '-' + state + '.png'), Buffer.from(shot.data, 'base64'));
  };
  const layout = async state => {
    const metrics = await evaluate(() => {
      const slide = document.querySelector('.slide.on'), pad = slide.querySelector('.pad');
      const bounds = pad.getBoundingClientRect(), outside = [], clipped = [];
      for (const el of pad.querySelectorAll('*')) {
        if (el instanceof SVGElement || !el.getClientRects().length) continue;
        const r = el.getBoundingClientRect(), label = el.id || el.className || el.tagName;
        if (r.left < bounds.left - 1 || r.right > bounds.right + 1 || r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1) outside.push(label);
        if (el.clientWidth > 0 && el.clientHeight > 0 && (el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight)) {
          clipped.push({ element: label, x: el.scrollWidth - el.clientWidth, y: el.scrollHeight - el.clientHeight });
        }
      }
      const controls = ['nav', 'dots'].map(id => document.getElementById(id).getBoundingClientRect());
      return {
        slide: [...document.querySelectorAll('.slide')].indexOf(slide) + 1, label: slide.dataset.label,
        scrollH: pad.scrollHeight, clientH: pad.clientHeight, scrollW: pad.scrollWidth, clientW: pad.clientWidth,
        overflowY: Math.max(0, pad.scrollHeight - pad.clientHeight), overflowX: Math.max(0, pad.scrollWidth - pad.clientWidth),
        documentOverflowX: Math.max(0, document.documentElement.scrollWidth - innerWidth),
        documentOverflowY: Math.max(0, document.documentElement.scrollHeight - innerHeight),
        overlapsNavigation: controls.some(r => r.top < bounds.bottom && r.bottom > bounds.top && r.left < bounds.right && r.right > bounds.left),
        outside, clipped
      };
    });
    console.log(JSON.stringify({ target: currentTarget, state, ...metrics }));
    check(metrics.scrollH <= metrics.clientH && metrics.scrollW <= metrics.clientW, state + ': pad overflow', metrics);
    check(!metrics.documentOverflowX && !metrics.documentOverflowY, state + ': document overflow', metrics);
    check(!metrics.outside.length && !metrics.clipped.length && !metrics.overlapsNavigation, state + ': clipped content or overlap', metrics);
  };
  await cdp('Page.enable');
  await cdp('Runtime.enable');
  await cdp('Log.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
  // Local files must render with embedded fonts even without internet access.
  await cdp('Network.enable');
  await cdp('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });

  for (const target of targets) {
    currentTarget = target.name;
    const navigation = await cdp('Page.navigate', { url: target.url });
    assert.ok(!navigation.errorText, navigation.errorText);
    await settle();
    await evaluate('document.fonts.ready.then(()=>true)');
    const content = await evaluate(() => ({
      count: document.querySelectorAll('.slide').length,
      text: [...document.querySelectorAll('.pad')].map(p => p.textContent).join(' '),
      slides: [...document.querySelectorAll('.slide .pad')].map(p => p.textContent.replace(/\s+/g, ' ').trim()),
      blocks: [...document.querySelectorAll('.pad .c, .pad p, .pad .bridge')].map(el => el.textContent.replace(/\s+/g, ' ').trim()),
      architecture: [...document.querySelectorAll('.slide[data-architecture="target"]')].map(slide => ({
        number: [...document.querySelectorAll('.slide')].indexOf(slide) + 1,
        text: slide.querySelector('.pad')?.textContent.replace(/\s+/g, ' ').trim() ?? '',
        levels: [...slide.querySelectorAll('[data-ai-level]')].map(el => ({ level: el.dataset.aiLevel, text: el.textContent.replace(/\s+/g, ' ').trim() }))
      })),
      deployment: {
        scope: document.getElementById('deployment-boundary')?.dataset.deployment,
        text: document.getElementById('deployment-boundary')?.textContent.replace(/\s+/g, ' ').trim() ?? ''
      },
      fonts: ['Manrope', 'DM Mono'].map(f => ({ family: f, loaded: [...document.fonts].some(face => face.family.replace(/['"]/g, '') === f && face.status === 'loaded') })),
      metrics: [...document.querySelectorAll('[data-metric]')].map(el => ({ key: el.dataset.metric, value: el.textContent.trim() })),
      notesSeconds: [...document.querySelectorAll('.speaker-notes')].reduce((sum, n) => sum + Number(n.dataset.seconds), 0),
      troy: !!document.querySelectorAll('.slide')[1]?.querySelector('.troy-svg .mer-spirit'),
      bg: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),
      copper: getComputedStyle(document.documentElement).getPropertyValue('--copper').trim()
    }));
    check(content.count === 7, 'Expected seven slides', content.count);
    check(!/astronaut|helmet|\bEVA\b|humanoid/i.test(content.text), 'Legacy crew framing remains');
    check(content.troy && content.bg === '#0d0907' && content.copper === '#ee8a5b', 'Artwork or design system missing');
    check(content.fonts.every(font => font.loaded), 'Embedded fonts did not load offline', content.fonts);
    check(content.notesSeconds === 180, 'Speaker notes must cover three minutes', content.notesSeconds);
    // Check the story's meaning without locking headings or card copy to exact sentences.
    const architecture = content.architecture[0], architectureText = architecture?.text || '';
    const levels = architecture?.levels || [];
    const levelText = level => levels.find(item => item.level === String(level))?.text || '';
    check(content.architecture.length === 1 && architecture.number === 5 && levels.length === 3 && /protect/i.test(levelText(1)) && /mission/i.test(levelText(2)) && /coordinat/i.test(levelText(2)) && /analys/i.test(levelText(3)) && /learn/i.test(levelText(3)), 'Explicit three-level target AI architecture is missing', content.architecture);
    check(/\b(?:station|base|hub)\b/i.test(architectureText) && /\boptional\b/i.test(architectureText) && /\b(?:uncrewed|unmanned)\b/i.test(architectureText) && /comput/i.test(architectureText) && /\b(?:future|planned|next)\b/i.test(content.deployment.text), 'Local station must be an optional future uncrewed compute hub');
    check(content.deployment.scope === 'lab' && /Guardian/i.test(content.deployment.text) && /\bLAB\b/i.test(content.deployment.text) && /\b(?:now|today|current(?:ly)?)\b/i.test(content.deployment.text), 'Current Guardian deployment must be scoped to LAB', content.deployment);
    check(/\b(?:on[ -]?board|on[ -]rover)\b/i.test(content.deployment.text) && /inferenc|deploy|Guardian/i.test(content.deployment.text) && /\b(?:next|future|planned)\b/i.test(content.deployment.text), 'Onboard Guardian inference must remain a next step');
    // Simulated fleet coordination may be demonstrated now; physical deployment is future work.
    check(/\b(?:field|physical|real[ -]world)\b/i.test(levelText(2)) && /\b(?:planned|future|next|pending)\b/i.test(levelText(2)), 'Field fleet coordination must remain planned');
    check(content.blocks.some(text => /\b(?:hardware|device|headset|Quest|physical)\b/i.test(text) && /validat|test|check|trial/i.test(text) && /pending|not yet|unvalidated|await|to be/i.test(text)), 'Hardware validation must remain pending');
    check(/architectur/i.test(content.slides[4] || '') && /illustrat|diagram|concept/i.test(content.slides[4] || ''), 'Slide five link controls must be identified as an architecture illustration');
    const metricKeys = ['GUARDIAN_CAUGHT', 'GUARDIAN_LEAD', 'GUARDIAN_FALSE_ALARMS', 'GUARDIAN_BEFORE_F1', 'GUARDIAN_AFTER_F1'];
    check(content.metrics.length === 5 && metricKeys.every(key => content.metrics.some(metric => metric.key === key && /\d/.test(metric.value) && !/\{\{|\}\}/.test(metric.value))), 'Five measured Guardian metrics required; placeholders are not allowed', content.metrics);
    check(!/\{\{|\}\}/.test(content.text), 'Unresolved deck placeholder remains');
    console.log('METRICS:', JSON.stringify({ target: target.name, values: content.metrics }));
    for (let slide = 0; slide < content.count; slide++) {
      await evaluate(n => go(n), slide);
      await settle();
      await layout('slide-' + (slide + 1));
      await screenshot(target.name, 'slide-' + (slide + 1));
      check(await activeSlide() === slide + 1, 'Slide navigation failed');
      check(await evaluate(n => document.querySelectorAll('.slide:not([inert])').length === 1 && document.getElementById('cnt').textContent === String(n + 1).padStart(2, '0') + ' / ' + String(document.querySelectorAll('.slide').length).padStart(2, '0'), slide), 'Slide counter or focus isolation failed');
    }

    await evaluate('go(1)');
    await settle();
    await click('#troyCard');
    await sleep(600);
    check(await evaluate(() => document.getElementById('troyCard').getAttribute('aria-pressed') === 'true') && await activeSlide() === 2, 'Troy mouse toggle navigated or failed');
    await layout('troy-surface-scan');
    await screenshot(target.name, 'troy-surface-scan');
    await key('Enter', 'Enter', 13);
    check(await evaluate(() => document.getElementById('troyCard').getAttribute('aria-pressed') === 'false') && await activeSlide() === 2, 'Troy Enter toggle navigated or failed');
    await key(' ', 'Space', 32);
    check(await evaluate(() => document.getElementById('troyCard').getAttribute('aria-pressed') === 'true') && await activeSlide() === 2, 'Troy Space toggle navigated or failed');

    await evaluate('go(4)');
    await settle();
    const available = await linkState();
    check(available.live === 'true' && available.delay === 'false' && available.localAutonomy && available.cards.every(Boolean) && available.tags.every(Boolean) && available.description, 'Earth-link architecture illustration must start available', available);
    await click('[data-link="delay"]');
    await sleep(400);
    const interrupted = await linkState();
    check(interrupted.delay === 'true' && interrupted.live === 'false' && interrupted.localAutonomy && interrupted.tags.every(Boolean) && interrupted.tags.some((tag, index) => tag !== available.tags[index]) && interrupted.description && interrupted.description !== available.description && await activeSlide() === 5, 'Interrupted Earth-link illustration must retain distributed autonomy and update status without navigation', interrupted);
    await layout('architecture-link-interrupted');
    await screenshot(target.name, 'architecture-link-interrupted');
    await evaluate(() => document.querySelector('[data-link="live"]').focus());
    await key('Enter', 'Enter', 13);
    const restored = await linkState();
    check(restored.live === 'true' && restored.delay === 'false' && restored.localAutonomy && restored.tags.every((tag, index) => tag === available.tags[index]) && restored.cards.every((card, index) => card === available.cards[index]) && restored.description === available.description && await activeSlide() === 5, 'Earth-link architecture keyboard control must restore the available state without navigation', restored);

    await evaluate('document.activeElement.blur()');
    await key('1', 'Digit1', 49);
    check(await activeSlide() === 1, 'Number key navigation failed');
    await key('ArrowRight', 'ArrowRight', 39);
    check(await activeSlide() === 2, 'Arrow navigation failed');
    await key('End', 'End', 35);
    check(await activeSlide() === content.count, 'End navigation failed');
    await key('Home', 'Home', 36);
    check(await activeSlide() === 1, 'Home navigation failed');
    await settle();
    await click('#nx');
    check(await activeSlide() === 2, 'Next button failed');
    await click('#pv');
    check(await activeSlide() === 1, 'Previous button failed');
    await click('#dots button:nth-child(5)');
    check(await activeSlide() === 5, 'Dot navigation failed');
    await evaluate('go(0);document.activeElement.blur()');
    await settle();
    await cdp('Input.dispatchMouseEvent', { type: 'mousePressed', x: 1100, y: 650, button: 'left', clickCount: 1 });
    await cdp('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 1100, y: 650, button: 'left', clickCount: 1 });
    check(await activeSlide() === 2, 'Background mouse navigation failed');
    await evaluate('go(0);document.activeElement.blur()');
    await settle();
    await cdp('Emulation.setTouchEmulationEnabled', { enabled: true });
    const swipe = async (from, to) => {
      await cdp('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: from, y: 630 }] });
      await cdp('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: to, y: 630 }] });
      await cdp('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    };
    await swipe(600, 350);
    check(await activeSlide() === 2, 'Touch forward swipe failed');
    await settle();
    const touchTarget = await evaluate(() => { const el = document.elementFromPoint(350, 630); return { tag: el.tagName, className: el.className, control: !!el.closest('button,a,[role="button"],#linkBar') }; });
    await swipe(350, 600);
    check(await activeSlide() === 1, 'Touch backward swipe failed', { touchTarget, slide: await activeSlide() });
    await cdp('Emulation.setTouchEmulationEnabled', { enabled: false });
    console.log('NAV_CHECK:', JSON.stringify({ target: target.name, failures: failures.filter(f => /navigation|toggle|swipe|button|control/.test(f.message)).length }));
  }
  check(errors.length === 0, 'Runtime or browser errors', errors);
  console.log('ERRORS:', JSON.stringify(errors));
  console.log('FAILURES:', JSON.stringify(failures));
  if (failures.length) throw new Error(failures.length + ' verification check(s) failed');
  console.log('PASS: ' + targets.length + ' HTML file(s), every slide at 1280x720, zero overflow and zero runtime errors.');
}

async function cleanup() {
  if (ws?.readyState === WebSocket.OPEN) {
    try { await cdp('Browser.close'); } catch {}
    ws.close();
  }
  if (proc && proc.exitCode === null) proc.kill();
  if (userDataDir) {
    const relative = path.relative(baseDir, path.resolve(userDataDir));
    assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative) && path.basename(userDataDir).startsWith('.verify-chrome-'), 'Unsafe browser profile cleanup path');
    for (let attempt = 0; attempt < 8; attempt++) {
      try { fs.rmSync(userDataDir, { recursive: true, force: true }); break; } catch { await sleep(250); }
    }
  }
}

try {
  await main();
} catch (error) {
  console.error(error.stack || error);
  process.exitCode = 1;
} finally {
  await cleanup();
}
