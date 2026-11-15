// Paste this entire file into Chrome DevTools Console on the project edit form.
// Uses the form's normal input events. No fetch, credential access or submission.
(async () => {
  'use strict';
  const sources = [
    ['Python', 'https://www.python.org/'],
    ['FastAPI', 'https://github.com/fastapi/fastapi'],
    ['Uvicorn', 'https://github.com/encode/uvicorn'],
    ['HTTPX', 'https://github.com/encode/httpx'],
    ['python-dotenv', 'https://github.com/theskumar/python-dotenv'],
    ['SQLite', 'https://www.sqlite.org/'],
    ['Unity — Quest sensor-mast prototype', 'https://unity.com/'],
    ['Meta XR SDK — Quest development', 'https://developers.meta.com/horizon/'],
    ['OpenXR', 'https://www.khronos.org/openxr/'],
    ['QuestRoomScan — reconstruction dependency, pinned source', 'https://github.com/arghyasur1991/QuestRoomScan/tree/4791b24b81015641d4cfb010a93c6283d4eb3dee'],
    ['Lucide icons — ISC licence', 'https://lucide.dev/license'],
    ['Tabler icons — MIT licence, Quest HUD', 'https://github.com/tabler/tabler-icons'],
    ['Manrope font — SIL Open Font License', 'https://github.com/googlefonts/manrope'],
    ['DM Mono font — SIL Open Font License', 'https://github.com/googlefonts/dm-mono'],
    ['Marcellus font — original archived presentation', 'https://fonts.google.com/specimen/Marcellus'],
    ['Quicksand font — original archived presentation', 'https://fonts.google.com/specimen/Quicksand'],
    ['unslop — UI methodology by Damir Sokolovsky, CC BY 4.0', 'https://github.com/heydamir/unslop'],
    ['Poly Haven — CC0 resources in historical simulator preparation', 'https://polyhaven.com/'],
    ['Playwright — browser testing and screen capture', 'https://github.com/microsoft/playwright'],
    ['pytest — automated tests', 'https://github.com/pytest-dev/pytest'],
    ['FFmpeg — demo encoding', 'https://ffmpeg.org/'],
    ['OpenAI Codex — AI-assisted development', 'https://openai.com/codex/'],
    ['OmniRoute — server-side AI routing', 'https://github.com/cheaper-inference/OmniRoute'],
    ['InstaBox — cloud development environment', 'https://instabox.sh/']
  ];
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  const tick = () => new Promise(resolve => setTimeout(resolve, 80));
  const canonical = value => {
    try { return new URL(value.trim()).href.replace(/\/$/, ''); }
    catch { return value.trim(); }
  };
  const fields = [...document.querySelectorAll('input[type="hidden"][name="projectReferences"]')];
  assert(fields.length === 1, 'Open the project EDIT form with Space Agency Partner & Other Data.');
  const hidden = fields[0], field = hidden.parentElement;
  assert(field.textContent.includes('Space Agency Partner & Other Data'), 'Form structure changed; stopped without editing.');
  const list = field.querySelector('ul');
  assert(list, 'The source list was not found.');
  const rows = () => [...list.querySelectorAll('li')].map(li => ({
    text: li.querySelector('input[name="text"]'), url: li.querySelector('input[name="url"]')
  })).filter(row => row.text && row.url);
  const blank = row => row.text.value === '' && row.url.value === '';
  const original = rows().map(row => ({text: row.text.value, url: row.url.value}));
  const existing = new Set(original.filter(row => row.url.trim()).map(row => canonical(row.url)));
  const missing = sources.filter(([, url]) => !existing.has(canonical(url)));
  const requiredRows = rows().length + Math.max(0, missing.length - rows().filter(blank).length);
  assert(requiredRows <= 25, `Need ${requiredRows} rows, but this form supports 25. Existing entries were preserved; nothing changed.`);
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  const waitFor = async (condition, message) => {
    for (let n = 0; n < 40; n++) { if (condition()) return; await tick(); }
    throw new Error(message);
  };
  async function fill(input, value) {
    assert(input.isConnected && !input.disabled && !input.readOnly, 'Input is unavailable; stopped.');
    setter.call(input, value);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    await tick(); // Let React commit before touching the next controlled field.
  }
  let added = 0;
  for (const [text, url] of missing) {
    let index = rows().findIndex(blank);
    if (index < 0) {
      const before = rows().length;
      const add = [...list.querySelectorAll('button[type="button"]')].find(b => b.textContent.trim() === 'Add New Link');
      assert(add && !add.disabled, 'Add New Link is unavailable; the form may have reached its limit.');
      add.click();
      await waitFor(() => rows().length > before, 'No row appeared. Use the live edit page, not a saved HTML snapshot.');
      index = rows().findIndex(blank);
    }
    assert(index >= 0, 'No empty row is available; existing entries were preserved.');
    await fill(rows()[index].text, text);
    await fill(rows()[index].url, url);
    await waitFor(() => rows()[index]?.text.value === text && rows()[index]?.url.value === url && hidden.value.includes(`[${text}](${url})`),
      'The form did not retain a source in its underlying state. Stopped; review before saving.');
    added++;
  }
  assert(original.filter(row => row.text || row.url).every(row => rows().some(current => current.text.value === row.text && current.url.value === row.url)),
    'An existing entry changed unexpectedly; review the form.');
  assert(sources.every(([, url]) => rows().some(row => canonical(row.url.value) === canonical(url))), 'Some sources are missing.');
  console.table(rows().filter(row => !blank(row)).map(row => ({name: row.text.value, url: row.url.value})));
  const result = {added, alreadyPresent: sources.length - missing.length, totalSources: sources.length};
  console.info('Arescope sources ready. Review the list, then save the form yourself.', result);
  return result;
})().catch(error => { console.error('Arescope source import stopped:', error.message); return {error: error.message}; });
