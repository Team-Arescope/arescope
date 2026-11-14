import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const baseDir = import.meta.dirname;
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const outDir = path.join(baseDir, 'screenshots');
fs.mkdirSync(outDir, { recursive: true });

const defaultHtml = path.join(baseDir, 'Arescope — NASA Space Apps Challenge 2026.html');
const cliTarget = process.argv[2];
const targetUrl = cliTarget
  ? (/^https?:|^file:/i.test(cliTarget) ? cliTarget : pathToFileURL(path.resolve(cliTarget)).href)
  : pathToFileURL(defaultHtml).href;

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'arescope-chrome-'));
const port = Number(process.env.CDP_PORT || 9341);

const proc = spawn(chromePath, [
  '--headless=new',
  `--remote-debugging-port=${port}`,
  '--remote-allow-origins=*',
  `--user-data-dir=${userDataDir}`,
  '--window-size=1280,720',
  '--disable-gpu',
  '--disable-gpu-compositing',
  '--disable-gpu-sandbox',
  '--no-sandbox',
  '--disable-dev-shm-usage',
  '--disable-extensions',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank'
], { stdio: ['ignore', 'pipe', 'pipe'] });

proc.stderr.on('data', d => console.error('CHROME:', d.toString().trim()));
proc.on('exit', code => console.error('CHROME EXITED:', code));

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  let wsUrl;
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json`);
      const list = await res.json();
      const page = list.find(x => x.type === 'page');
      if (page?.webSocketDebuggerUrl) { wsUrl = page.webSocketDebuggerUrl; break; }
    } catch {}
    await sleep(250);
  }
  if (!wsUrl) throw new Error('No CDP target');
  console.log('TARGET:', targetUrl);
  console.log('WS:', wsUrl);

  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => {
    ws.addEventListener('open', res);
    ws.addEventListener('error', () => rej(new Error('WS error')));
  });

  let seq = 0;
  const pending = new Map();
  const errors = [];

  ws.addEventListener('message', ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    } else if (msg.method === 'Runtime.exceptionThrown') {
      errors.push(msg.params.exceptionDetails.text);
    }
  });

  ws.addEventListener('close', e => {
    for (const [, p] of pending) p.reject(new Error('WS closed ' + e.code));
    pending.clear();
  });

  const cdp = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });

  await cdp('Page.enable');
  await cdp('Runtime.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
  await cdp('Page.navigate', { url: targetUrl });
  await sleep(1800);

  const evalJS = async (expr, awaitPromise = false) => {
    const r = await cdp('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result?.value;
  };

  await evalJS(`document.fonts ? document.fonts.ready.then(() => true) : true`, true);
  const slideCount = await evalJS(`document.querySelectorAll('.slide').length`);

  for (let s = 0; s < slideCount; s++) {
    await evalJS(`go(${s})`);
    await sleep(1700);
    const metrics = await evalJS(`(() => {
      const slide = document.querySelectorAll('.slide')[${s}];
      const pad = slide.querySelector('.pad');
      const r = pad.getBoundingClientRect();
      const nav = document.getElementById('nav').getBoundingClientRect();
      const dots = document.getElementById('dots').getBoundingClientRect();
      return {
        slide: ${s + 1},
        cnt: document.getElementById('cnt').textContent,
        scrollH: pad.scrollHeight,
        clientH: pad.clientHeight,
        overflowY: pad.scrollHeight - pad.clientHeight,
        scrollW: pad.scrollWidth,
        clientW: pad.clientWidth,
        overflowX: pad.scrollWidth - pad.clientWidth,
        padTop: Math.round(r.top),
        padBottom: Math.round(r.bottom),
        navTop: Math.round(nav.top),
        dotsTop: Math.round(dots.top)
      };
    })()`);
    console.log(JSON.stringify(metrics));
    const shot = await cdp('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(outDir, `slide-${s + 1}.png`), Buffer.from(shot.data, 'base64'));
  }

  await evalJS(`document.dispatchEvent(new KeyboardEvent('keydown', { key: '1' }))`);
  await sleep(300);
  const afterKey1 = await evalJS(`[...document.querySelectorAll('.slide')].findIndex(el => el.classList.contains('on')) + 1`);
  await evalJS(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))`);
  await sleep(300);
  const afterArrow = await evalJS(`[...document.querySelectorAll('.slide')].findIndex(el => el.classList.contains('on')) + 1`);
  console.log('NAV_CHECK:', JSON.stringify({ afterKey1, afterArrow }));

  console.log('ERRORS:', JSON.stringify(errors));
  ws.close();
  proc.kill();
}

main()
  .catch(err => { console.error(err); proc.kill(); process.exitCode = 1; })
  .finally(() => {
    setTimeout(() => {
      try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch {}
    }, 500);
  });
