/* Inline Lucide icons, ISC license: https://lucide.dev/license */
(() => {
  'use strict';
  const icons = {
    aperture: '<circle cx="12" cy="12" r="10"/><path d="m14.31 8 5.74 9.94M9.69 8h11.48M7.38 12l5.74-9.94M9.69 16 3.95 6.06M14.31 16H2.83m13.79-4-5.74 9.94"/>',
    radio: '<path d="M4.9 19.1a10 10 0 0 1 0-14.2m14.2 0a10 10 0 0 1 0 14.2M7.8 16.2a6 6 0 0 1 0-8.4m8.4 0a6 6 0 0 1 0 8.4"/><circle cx="12" cy="12" r="2"/>',
    'shield-check': '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
    'alert-triangle': '<path d="m10.3 3.9-8.1 14A2 2 0 0 0 3.9 21h16.2a2 2 0 0 0 1.7-3.1l-8.1-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/>',
    play: '<path d="m6 3 14 9-14 9V3Z"/>',
    square: '<rect x="3" y="3" width="18" height="18" rx="2"/>',
    'step-forward': '<path d="m4 4 10 8-10 8V4Zm16 0v16"/>',
    truck: '<path d="M10 17h4V5H2v12h3m10-9h4l3 4v5h-3m-5 0h1"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="16.5" cy="17.5" r="2.5"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5"/>',
    'file-text': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm0 0v6h6M8 13h8m-8 4h6"/>',
    'sliders-horizontal': '<path d="M21 4h-7m-4 0H3m18 8H11m-4 0H3m18 8h-3m-4 0H3M14 2v4m-7 4v4m11 4v4"/>',
    'book-open': '<path d="M12 7v14m0-14C9 4 4 4 2 5v14c3-1 7-1 10 2 3-3 7-3 10-2V5c-2-1-7-1-10 2Z"/>',
    x: '<path d="m18 6-12 12M6 6l12 12"/>',
    clipboard: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    plug: '<path d="M12 22v-5M9 8V2m6 6V2M7 8h10v4a5 5 0 0 1-10 0V8Z"/>',
    'refresh-cw': '<path d="M3 12a9 9 0 0 1 15.4-6.4L21 8m0-5v5h-5m5 4a9 9 0 0 1-15.4 6.4L3 16m5 0H3v5"/>',
    'rotate-ccw': '<path d="M3 10a9 9 0 1 1 2.7 8.3M3 4v6h6"/>',
    'mouse-pointer-2': '<path d="m4 4 7.07 17 2.51-7.39L21 11.07 4 4Z"/>',
    'arrow-up-right': '<path d="M7 17 17 7M7 7h10v10"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5m-5 5V3"/>',
    trash: '<path d="M3 6h18M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M5 6l1 14h12l1-14M10 10v6m4-6v6"/>',
    eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'
  };
  function icon(name) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    el.setAttribute('viewBox', '0 0 24 24'); el.setAttribute('fill', 'none'); el.setAttribute('stroke', 'currentColor');
    el.setAttribute('stroke-width', '1.5'); el.setAttribute('stroke-linecap', 'round'); el.setAttribute('stroke-linejoin', 'round'); el.setAttribute('aria-hidden', 'true');
    if (!Object.hasOwn(icons, name)) throw new Error(`Unknown mission icon: ${name}`);
    el.innerHTML = icons[name];
    return el;
  }
  document.querySelectorAll('[data-icon]').forEach(el => el.replaceWith(icon(el.dataset.icon)));
  const drawer = document.querySelector('#drawer');
  const labels = {equipment: 'Equipment and live', guardian: 'Guardian', sessions: 'Sessions', logs: 'Device logs', settings: 'View settings'};
  let active = null;
  function close() {
    const old = active; active = null; drawer.hidden = true;
    document.body.classList.remove('drawer-open');
    document.querySelectorAll('[data-panel]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    if (old) document.querySelector(`[data-panel="${old}"]`).focus();
  }
  function openPanel(id, {focus = true} = {}) {
    const button = document.querySelector(`[data-panel="${id}"]`);
    if (!button || active === id) return;
    active = id; drawer.hidden = false; document.body.classList.add('drawer-open');
    document.querySelector('#drawer-title').textContent = labels[id];
    document.querySelectorAll('.drawer-pane').forEach(pane => { pane.hidden = pane.id !== id; });
    document.querySelectorAll('[data-panel]').forEach(b => b.setAttribute('aria-expanded', String(b === button)));
    if (focus) document.querySelector('#close-drawer').focus({preventScroll: true});
    document.dispatchEvent(new CustomEvent('panelchange', {detail: id}));
  }
  document.querySelectorAll('[data-panel]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.panel;
    if (active === id) close(); else openPanel(id);
  }));
  document.querySelector('#close-drawer').addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && active) close(); });
  const tick = () => { document.querySelector('#utc-clock').textContent = new Date().toISOString().slice(11, 19) + ' UTC'; };
  tick(); setInterval(tick, 1000);
  window.LabShell = {icon, openPanel};
})();
