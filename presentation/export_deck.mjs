import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Export a seven-slide deck through CDP without changing its interactive HTML.
// All generated files and the disposable Chrome profile stay in presentation/.
const baseDir = path.dirname(fileURLToPath(import.meta.url));
const pitchExport = process.argv.includes('--pitch');
const source = path.join(baseDir, pitchExport ? 'Arescope-V2-Pitch-With-Demo-Standalone.html' : 'Arescope — NASA Space Apps Challenge 2026.html');
const screenshotDir = path.join(baseDir, pitchExport ? 'pitch-screenshots' : 'screenshots');
const pdfPath = path.join(baseDir, pitchExport ? 'Arescope-V2-Pitch-With-Demo.pdf' : 'Arescope-V2-Deck.pdf');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let proc, ws, cdp, profile;

async function main() {
  const chrome = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  ].find(candidate => candidate && fs.existsSync(candidate));
  assert.ok(chrome, 'Chrome/Chromium not found. Set CHROME_PATH.');
  fs.mkdirSync(screenshotDir, { recursive: true });
  profile = fs.mkdtempSync(path.join(baseDir, '.export-chrome-'));
  let stderr = '', launchError;
  proc = spawn(chrome, [
    '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
    '--window-size=1280,720', '--disable-gpu', '--disable-dev-shm-usage',
    '--disable-extensions', '--no-first-run', '--no-default-browser-check', 'about:blank'
  ], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true });
  proc.on('error', error => { launchError = error; });
  proc.stderr.on('data', data => { stderr = (stderr + data).slice(-4000); });
  let endpoint;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (launchError) throw launchError;
    if (proc.exitCode !== null) throw new Error('Chrome exited early: ' + stderr);
    try {
      const port = fs.readFileSync(path.join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0].trim();
      const targets = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
      endpoint = targets.find(target => target.type === 'page')?.webSocketDebuggerUrl;
      if (endpoint) break;
    } catch {}
    await sleep(200);
  }
  assert.ok(endpoint, 'No Chrome DevTools target: ' + stderr);
  ws = new WebSocket(endpoint);
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('CDP connection timed out')), 10000);
    ws.addEventListener('open', () => { clearTimeout(timeout); resolve(); }, { once: true });
    ws.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('CDP connection failed')); }, { once: true });
  });
  let sequence = 0;
  const pending = new Map(), errors = [];
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data), request = pending.get(message.id);
    if (request) {
      clearTimeout(request.timeout);
      pending.delete(message.id);
      if (message.error) request.reject(new Error(message.error.message));
      else request.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      const detail = message.params.exceptionDetails;
      errors.push(detail.exception?.description || detail.text);
    } else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') {
      errors.push(message.params.args.map(arg => arg.description || String(arg.value)).join(' '));
    } else if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') {
      errors.push(message.params.entry.text);
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
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 30000);
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
  await cdp('Page.enable');
  await cdp('Runtime.enable');
  await cdp('Log.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
  await cdp('Network.enable');
  await cdp('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  const navigation = await cdp('Page.navigate', { url: pathToFileURL(source).href });
  assert.ok(!navigation.errorText, navigation.errorText);
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await evaluate(() => document.readyState === 'complete' && document.querySelectorAll('.slide').length === 7 && typeof go === 'function')) break;
    await sleep(100);
  }
  await evaluate('document.fonts.ready.then(() => true)');
  assert.equal(await evaluate(() => document.querySelectorAll('.slide').length), 7, 'V2 must contain seven slides');

  // Each page is cloned only after its live navigation/reveal has fully settled.
  // Keep vector text and SVGs. Capture the decorative background to avoid
  // Chrome's PDF clipping artifacts on the transformed, rounded Mars sphere.
  await evaluate(() => {
    const root = document.createElement('main');
    root.id = 'arescope-print-root';
    root.style.display = 'none';
    document.body.append(root);
  });
  for (let slide = 0; slide < 7; slide++) {
    await evaluate(n => go(n), slide);
    await sleep(1900);
    await evaluate(async () => {
      const video=document.querySelector('#stage > .slide.on video');
      if(video){
        video.pause();
        if(video.readyState<2)await new Promise(resolve=>video.addEventListener('loadeddata',resolve,{once:true}));
        await new Promise(resolve=>{video.addEventListener('seeked',resolve,{once:true});video.currentTime=17;});
      }
    });
    await evaluate(async () => {
      await Promise.all(document.querySelector('#stage > .slide.on').getAnimations({ subtree: true })
        .filter(animation => Number.isFinite(animation.effect.getComputedTiming().iterations))
        .map(animation => animation.finished.catch(() => {})));
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const state = await evaluate(n => {
      const slides = [...document.querySelectorAll('#stage > .slide')];
      const active = document.querySelector('#stage > .slide.on');
      return {
        slide: slides.indexOf(active) + 1, label: active.dataset.label,
        visible: getComputedStyle(active).visibility === 'visible' && Number(getComputedStyle(active).opacity) === 1,
        reveals: [...active.querySelectorAll('.r')].every(el => Number(getComputedStyle(el).opacity) === 1),
        width: innerWidth, height: innerHeight
      };
    }, slide);
    assert.equal(state.slide, slide + 1);
    assert.ok(state.visible && state.reveals, 'Unsettled slide: ' + JSON.stringify(state));
    assert.equal(state.width, 1280);
    assert.equal(state.height, 720);
    const shot = await cdp('Page.captureScreenshot', {
      format: 'png', fromSurface: true,
      clip: { x: 0, y: 0, width: 1280, height: 720, scale: 1 }
    });
    const png = Buffer.from(shot.data, 'base64');
    assert.equal(png.readUInt32BE(16), 1280);
    assert.equal(png.readUInt32BE(20), 720);
    fs.writeFileSync(path.join(screenshotDir, 'slide-' + (slide + 1) + '.png'), png);
    await evaluate(async () => {
      const hide = document.createElement('style');
      hide.id = 'arescope-background-capture';
      hide.textContent = '#stage > .slide, body > .hud, #dots, #nav, #hint, #bar { opacity: 0 !important; transition: none !important; }';
      document.head.append(hide);
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const background = await cdp('Page.captureScreenshot', {
      format: 'png', fromSurface: true,
      clip: { x: 0, y: 0, width: 1280, height: 720, scale: 1 }
    });
    await evaluate(({ n, background }) => {
      document.getElementById('arescope-background-capture').remove();
      const page = document.createElement('article');
      page.className = 'arescope-print-page';
      page.dataset.slide = String(n + 1);
      page.style.background = getComputedStyle(document.body).background;
      const backdrop = document.createElement('img');
      backdrop.className = 'arescope-print-background';
      backdrop.alt = '';
      backdrop.src = 'data:image/png;base64,' + background;
      page.append(backdrop);
      const stage = document.getElementById('stage').cloneNode(true);
      stage.removeAttribute('id');
      stage.classList.add('arescope-print-stage');
      stage.style.transform = 'none';
      for (const decoration of stage.querySelectorAll('.planet, .orb')) decoration.remove();
      for (const hidden of stage.querySelectorAll('.slide:not(.on)')) hidden.remove();
      const active = stage.querySelector('.slide');
      active.inert = false;
      active.setAttribute('aria-hidden', 'false');
      for (const note of stage.querySelectorAll('.speaker-notes')) note.remove();
      // PDF readers do not play HTML media. Preserve the demo as a poster with
      // a clickable link to the exact thirty-second public MP4.
      for(const video of stage.querySelectorAll('video')){
        const link=document.createElement('a');link.href='https://arescope.mrfenek.eu.cc/static/demo/Arescope-Fleet-Demo-30s.mp4';
        link.style.cssText='position:absolute;inset:0;display:block';
        const image=document.createElement('img');image.src=video.poster;image.alt='Thirty-second simulated fleet recovery demonstration';image.style.cssText='width:1280px;height:720px;display:block';
        const label=document.createElement('span');label.textContent='Play the 30-second demo';label.style.cssText='position:absolute;right:28px;bottom:84px;padding:10px 16px;color:#eee2d9;background:#160e0b;border:1px solid #ee8a5b;border-radius:5px;font:16px Manrope,sans-serif';
        link.append(image,label);video.replaceWith(link);
      }
      for(const control of stage.querySelectorAll('[data-video-ui]'))control.remove();
      page.append(stage);
      if(!active.classList.contains('demo-slide'))page.append(document.querySelector('.hud').cloneNode(true));
      document.getElementById('arescope-print-root').append(page);
    }, { n: slide, background: background.data });
    console.log('CAPTURE:', JSON.stringify({ ...state, bytes: png.length }));
  }

  // Export-only CSS: one visible, isolated 1280 x 720 surface per PDF page.
  // Screen media remains unchanged, including original IDs/navigation state.
  await evaluate(async () => {
    const style = document.createElement('style');
    style.textContent = `
      @page { size: 1280px 720px; margin: 0; }
      @media print {
        html, body { width: 1280px !important; height: auto !important; min-height: 0 !important; overflow: visible !important; margin: 0 !important; padding: 0 !important; }
        body > :not(#arescope-print-root) { display: none !important; }
        #arescope-print-root { display: block !important; width: 1280px; margin: 0; padding: 0; }
        #arescope-print-root, #arescope-print-root * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        #arescope-print-root *, #arescope-print-root *::before, #arescope-print-root *::after { transition: none !important; animation: none !important; }
        .arescope-print-page { position: relative; isolation: isolate; width: 1280px; height: 720px; margin: 0; padding: 0; overflow: hidden; break-inside: avoid; break-after: page; }
        .arescope-print-page:last-child { break-after: auto; }
        .arescope-print-background { position: absolute; inset: 0; width: 1280px; height: 720px; }
        .arescope-print-stage { position: absolute !important; left: 0 !important; top: 0 !important; width: 1280px; height: 720px; transform: none !important; }
        .arescope-print-page .slide { position: absolute; inset: 0; opacity: 1 !important; visibility: visible !important; transform: none !important; filter: none !important; }
        .arescope-print-page .r, .arescope-print-page .r.hl { opacity: 1 !important; visibility: visible !important; transform: none !important; }
        .arescope-print-page .hud { position: absolute; inset: 0; }
      }
    `;
    document.head.append(style);
    await Promise.all([...document.querySelectorAll('.arescope-print-background')].map(img => img.decode()));
    await document.fonts.ready;
  });
  await cdp('Emulation.setEmulatedMedia', { media: 'print' });
  const printLayout = await evaluate(async () => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return [...document.querySelectorAll('.arescope-print-page')].map(page => {
      const r = page.getBoundingClientRect(), slide = page.querySelector('.slide');
      return {
        slide: Number(page.dataset.slide), top: r.top, width: r.width, height: r.height,
        label: slide.dataset.label, visible: getComputedStyle(slide).visibility === 'visible' && Number(getComputedStyle(slide).opacity) === 1,
        reveals: [...slide.querySelectorAll('.r')].every(el => Number(getComputedStyle(el).opacity) === 1)
      };
    });
  });
  assert.equal(printLayout.length, 7);
  for (const [index, page] of printLayout.entries()) {
    assert.equal(page.top, index * 720);
    assert.equal(page.width, 1280);
    assert.equal(page.height, 720);
    assert.ok(page.visible && page.reveals, 'Hidden print content: ' + JSON.stringify(page));
  }
  console.log('PRINT_LAYOUT:', JSON.stringify(printLayout));
  assert.deepEqual(errors, [], 'Runtime/browser errors');
  const pdf = await cdp('Page.printToPDF', {
    landscape: true, printBackground: true, preferCSSPageSize: true,
    paperWidth: 1280 / 96, paperHeight: 720 / 96,
    marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0,
    displayHeaderFooter: false, scale: 1
  });
  const bytes = Buffer.from(pdf.data, 'base64');
  assert.ok(bytes.length > 100000, 'Unexpectedly small PDF');
  assert.equal(bytes.subarray(0, 5).toString(), '%PDF-');
  fs.writeFileSync(pdfPath, bytes);
  for (const stale of ['slide-8.png', 'slide-9.png']) {
    fs.rmSync(path.join(screenshotDir, stale), { force: true });
  }
  console.log('PDF:', JSON.stringify({ path: pdfPath, bytes: bytes.length }));
  console.log('Validate seven PDF pages and rendering with pdfinfo/pdftoppm before delivery.');
}

async function cleanup() {
  if (ws?.readyState === WebSocket.OPEN) {
    try { await cdp('Browser.close'); } catch {}
    ws.close();
  }
  if (proc && proc.exitCode === null) {
    proc.kill();
    await Promise.race([new Promise(resolve => proc.once('exit', resolve)), sleep(3000)]);
  }
  if (profile) {
    const relative = path.relative(baseDir, profile);
    assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative) && path.basename(profile).startsWith('.export-chrome-'), 'Unsafe profile cleanup path');
    for (let attempt = 0; attempt < 12; attempt++) {
      try { fs.rmSync(profile, { recursive: true, force: true }); break; }
      catch (error) { if (attempt === 11) throw error; await sleep(250); }
    }
  }
}

try { await main(); }
catch (error) { console.error(error.stack || error); process.exitCode = 1; }
finally { await cleanup(); }
