(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const endpoints = {
    latest: '/api/live/latest', stream: '/api/live/stream', sessions: '/api/live/sessions',
    session: id => `/api/live/sessions/${id}`, stats: '/api/live/stats',
    ply: (id, frame) => `/api/live/sessions/${id}/export.ply?frame=${frame}`,
    mesh: id => `/api/live/sessions/${id}/mesh`, logs: '/api/live/logs',
    log: name => `/api/live/logs/${encodeURIComponent(name)}`
  };
  const bytes = n => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KiB` : `${(n / 1048576).toFixed(1)} MiB`;
  const date = at => new Date(at * 1000).toLocaleString();
  function node(tag, text, className) { const el = document.createElement(tag); if (text) el.textContent = text; if (className) el.className = className; return el; }
  function button(text, symbol, handler) {
    const b = node('button'); b.type = 'button'; b.append(window.LabShell.icon(symbol), document.createTextNode(text));
    b.addEventListener('click', async () => {
      b.disabled = true;
      try { await handler(); } catch (e) { $(b.closest('#logs') ? 'log-message' : 'session-message').textContent = e.message; }
      finally { b.disabled = false; }
    }); return b;
  }

  class Terrain {
    constructor(canvas) {
      this.canvas = canvas;
      this.gl = canvas.getContext('webgl', {antialias: true, alpha: true});
      this.yaw = -.5; this.pitch = -.8; this.zoom = 1; this.scale = 1.5; this.mode = 'polygonal';
      if (!this.gl) throw new Error('3D rendering is unavailable in this browser.');
      const gl = this.gl;
      const compile = (type, source) => {
        const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error('Terrain shader could not start.');
        return shader;
      };
      const vs = compile(gl.VERTEX_SHADER, `
        attribute vec3 position; uniform float yaw; uniform float pitch; uniform float zoom;
        uniform float aspect; uniform float elevation; varying float height; varying float depth;
        void main(){
          vec3 p=vec3(position.x,position.y*elevation,position.z);
          vec3 r=vec3(cos(yaw)*p.x+sin(yaw)*p.z,p.y,-sin(yaw)*p.x+cos(yaw)*p.z);
          r=vec3(r.x,cos(pitch)*r.y-sin(pitch)*r.z,sin(pitch)*r.y+cos(pitch)*r.z);
          float d=3.8/zoom-r.z;
          gl_Position=vec4(r.x*2.2/aspect,r.y*2.2,1.002*d-.2002,d);
          height=position.y;depth=d;
        }`);
      const fs = compile(gl.FRAGMENT_SHADER, `
        precision mediump float; uniform vec3 color; uniform float line; varying float height; varying float depth;
        void main(){float light=clamp(.8+height*.9,.55,1.4); float fog=clamp((depth-2.0)/9.0,0.0,.7);
          gl_FragColor=vec4(mix(color*mix(light,1.0,line),vec3(.051,.035,.027),fog),1.0);}`);
      this.program = gl.createProgram(); gl.attachShader(this.program, vs); gl.attachShader(this.program, fs); gl.linkProgram(this.program);
      if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) throw new Error('Terrain renderer could not start.');
      this.uniforms = Object.fromEntries(['yaw', 'pitch', 'zoom', 'aspect', 'elevation', 'color', 'line'].map(k => [k, gl.getUniformLocation(this.program, k)]));
      this.buffers = Object.fromEntries(['points', 'triangles', 'minimal', 'polygonal'].map(k => [k, gl.createBuffer()]));
      new ResizeObserver(() => this.draw()).observe(canvas);
      let drag = null;
      canvas.addEventListener('pointerdown', e => { drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
      canvas.addEventListener('pointermove', e => {
        if (!drag) return;
        this.yaw += (e.clientX - drag[0]) * .006; this.pitch = Math.max(-1.48, Math.min(-.15, this.pitch + (e.clientY - drag[1]) * .005));
        drag = [e.clientX, e.clientY]; this.schedule();
      });
      canvas.addEventListener('pointerup', () => { drag = null; });
      canvas.addEventListener('pointercancel', () => { drag = null; });
      canvas.addEventListener('wheel', e => { e.preventDefault(); this.zoom = Math.max(.55, Math.min(2.3, this.zoom * Math.exp(-e.deltaY * .001))); this.schedule(); }, {passive: false});
      canvas.addEventListener('keydown', e => {
        if (e.key.toLowerCase() === 'r') this.reset();
        else if (e.key === 'ArrowLeft') this.yaw -= .1;
        else if (e.key === 'ArrowRight') this.yaw += .1;
        else if (e.key === 'ArrowUp') this.pitch = Math.max(-1.48, this.pitch - .1);
        else if (e.key === 'ArrowDown') this.pitch = Math.min(-.15, this.pitch + .1);
        else return;
        e.preventDefault(); this.schedule();
      });
      canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); $('terrain-error').hidden = false; });
      canvas.addEventListener('webglcontextrestored', () => location.reload());
    }
    reset() { this.yaw = -.5; this.pitch = -.8; this.zoom = 1; this.draw(); }
    schedule() { if (!this.pending) this.pending = requestAnimationFrame(() => { this.pending = 0; this.draw(); }); }
    load(data) {
      const {rows, cols} = data.grid, points = data.points, gl = this.gl;
      if (points.length !== rows * cols || points.some(p => p.length !== 3 || !p.every(Number.isFinite))) throw new Error('Invalid terrain grid.');
      let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
      for (const p of points) p.forEach((v, k) => { lo[k] = Math.min(lo[k], v); hi[k] = Math.max(hi[k], v); });
      const extent = Math.max(hi[0] - lo[0], hi[2] - lo[2]);
      const normalized = points.flatMap(p => p.map((v, k) => (v - (lo[k] + hi[k]) / 2) * 2 / extent));
      const triangles = [], minimal = [], diagonals = [];
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        const a = r * cols + c;
        if (c < cols - 1) minimal.push(a, a + 1);
        if (r < rows - 1) minimal.push(a, a + cols);
        if (r < rows - 1 && c < cols - 1) {
          const b = a + 1, d = a + cols, e = d + 1;
          // Four triangles share a bilinear cell centre. Both diagonals then
          // follow the same surface as the depth pass, avoiding depth speckle.
          const m = normalized.length / 3;
          for (let k = 0; k < 3; k++) normalized.push((normalized[a * 3 + k] + normalized[b * 3 + k] + normalized[d * 3 + k] + normalized[e * 3 + k]) / 4);
          triangles.push(a, b, m, b, e, m, e, d, m, d, a, m);
          diagonals.push(a, m, m, e, b, m, m, d);
        }
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.points); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(normalized), gl.STATIC_DRAW);
      this.counts = {};
      for (const [name, indices] of Object.entries({triangles, minimal, polygonal: minimal.concat(diagonals)})) {
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[name]); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW); this.counts[name] = indices.length;
      }
      this.draw();
    }
    draw() {
      if (!this.counts) return;
      const gl = this.gl, canvas = this.canvas, dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * dpr)); canvas.height = Math.max(1, Math.round(canvas.clientHeight * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.useProgram(this.program); gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
      const u = this.uniforms;
      for (const [key, value] of Object.entries({yaw: this.yaw, pitch: this.pitch, zoom: this.zoom, aspect: canvas.width / canvas.height, elevation: this.scale})) gl.uniform1f(u[key], value);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.points);
      const attr = gl.getAttribLocation(this.program, 'position'); gl.enableVertexAttribArray(attr); gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, 0, 0);
      // Filled terrain writes depth, so lines behind slopes stay occluded.
      gl.enable(gl.POLYGON_OFFSET_FILL); gl.polygonOffset(2, 2); gl.uniform3f(u.color, .075, .039, .025); gl.uniform1f(u.line, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers.triangles); gl.drawElements(gl.TRIANGLES, this.counts.triangles, gl.UNSIGNED_SHORT, 0); gl.disable(gl.POLYGON_OFFSET_FILL);
      gl.uniform3f(u.color, .35, .18, .10); gl.uniform1f(u.line, 1);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[this.mode]); gl.drawElements(gl.LINES, this.counts[this.mode], gl.UNSIGNED_SHORT, 0);
      canvas.dataset.ready = 'true';
    }
  }
  let terrain, terrainLoad = 0;
  try { terrain = new Terrain($('terrain')); } catch (e) { $('terrain-error').hidden = false; $('terrain-caption').textContent = e.message; }
  async function loadTerrain() {
    const version = ++terrainLoad, type = $('terrain-select').value;
    try {
      if (!terrain) throw new Error('Enable 3D rendering and reload this page.');
      const path = type === 'mola' ? '/static/data/mola-gale.json' : '/static/data/hirise-gale.json';
      const r = await fetch(path); if (!r.ok) throw new Error('Terrain is temporarily unavailable.');
      const data = await r.json(); if (version !== terrainLoad) return;
      terrain.load(data); $('terrain-error').hidden = true;
      $('grid-count').textContent = `${data.grid.rows} × ${data.grid.cols} samples`;
      $('terrain-caption').textContent = type === 'mola' ? 'MOLA regional archive · 118 km extent' : 'HiRISE local archive · 1.04 km extent';
      $('terrain-source').textContent = type === 'mola' ? 'NASA MGS / MOLA · 1.85 km step' : 'NASA MRO / HiRISE · 8.09 m display step';
      $('source-notes').textContent = type === 'mola' ? 'MOLA display grid: 65 × 65. About 118 km across, with a 1.85 km step. Regional altimetry from NASA MGS.' : 'HiRISE display grid: 129 × 129. About 1.04 km across, with an 8.09 m display step. Native spacing: 1.0117 m.';
    } catch (e) { $('terrain-error').hidden = false; $('terrain-caption').textContent = e.message; }
  }
  $('terrain-select').addEventListener('change', loadTerrain);
  $('retry-terrain').addEventListener('click', loadTerrain);
  $('grid-mode').addEventListener('change', () => { if (terrain) { terrain.mode = $('grid-mode').value; terrain.draw(); } });
  $('exaggeration').addEventListener('input', () => { $('exaggeration-value').textContent = `${Number($('exaggeration').value).toFixed(1)}×`; if (terrain) { terrain.scale = Number($('exaggeration').value); terrain.draw(); } });
  $('reset-view').addEventListener('click', () => terrain?.reset());
  loadTerrain();

  let token = '', socket = null, poll = null, reconnect = null, epoch = 0, activeScan = null;
  const rooms = new Map();
  async function api(path, options = {}, producer = null) {
    const auth = producer === null ? token : producer;
    if (!auth) throw new Error('Connect a viewer first.');
    const response = await fetch(path, {...options, cache: 'no-store', headers: {...options.headers, Authorization: `Bearer ${auth}`}});
    if (!response.ok) throw new Error(response.status === 401 ? 'Token was not accepted.' : response.status === 404 ? 'This item is no longer available.' : 'Request could not be completed. Try again.');
    return response;
  }
  async function download(path, name) {
    const response = await api(path), blob = await response.blob(), url = URL.createObjectURL(blob);
    const a = node('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function state(text, active = false) { $('connection-status').textContent = text; $('connection-dot').classList.toggle('active', active); }
  function renderRooms() {
    $('rooms').replaceChildren();
    for (const [room, frame] of rooms) {
      const card = node('article', null, 'card'); card.append(node('h3', room), node('p', `${frame.pointCount} points · ${date(frame.receivedAt)}`), button('Inspect scan', 'eye', () => showScan(frame))); $('rooms').append(card);
    }
    if (!rooms.size) $('rooms').append(node('p', 'Awaiting a new room scan.', 'muted'));
  }
  function accept(message) {
    if (Array.isArray(message.rooms)) { rooms.clear(); message.rooms.forEach(f => rooms.set(f.room, f)); }
    else if (message.source === 'live-quest' && Array.isArray(message.points)) {
      rooms.set(message.room, message);
      if (activeScan?.source !== 'archived-quest') showScan(message);
      $('live-message').textContent = `Receiving scans from ${message.room}.`;
    }
    renderRooms();
  }
  async function latest(generation) {
    try { const r = await api(endpoints.latest); const data = await r.json(); if (generation === epoch) accept(data); }
    catch (e) { if (generation === epoch) $('live-message').textContent = e.message; }
  }
  function openSocket(generation) {
    if (!token || generation !== epoch) return;
    const url = new URL(endpoints.stream, location.href); url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    // WebSocket's contract uses the viewer query parameter. Downloads always use headers.
    url.searchParams.set('token', token);
    const ws = new WebSocket(url); socket = ws;
    ws.onopen = () => {
      if (generation !== epoch) { ws.close(); return; }
      clearInterval(poll); poll = null; state('Viewer connected', true); $('live-message').textContent = 'Live feed connected. Waiting for room scans.';
    };
    ws.onmessage = e => { if (generation === epoch) { try { accept(JSON.parse(e.data)); } catch { $('live-message').textContent = 'A scan update could not be read.'; } } };
    ws.onclose = e => {
      if (generation !== epoch || !token) return;
      if (e.code === 4401) { disconnect(); $('live-message').textContent = 'Token was not accepted.'; return; }
      state('Viewer reconnecting'); $('live-message').textContent = 'Fetching updates while the stream reconnects.';
      if (!poll) { latest(generation); poll = setInterval(() => latest(generation), 2000); }
      reconnect = setTimeout(() => openSocket(generation), 5000);
    };
    ws.onerror = () => ws.close();
  }
  function disconnect() {
    epoch++; token = ''; clearInterval(poll); clearTimeout(reconnect); poll = reconnect = null;
    if (socket) { socket.close(); socket = null; }
    rooms.clear(); activeScan = null; renderRooms(); $('live-overlay').hidden = true;
    $('viewer-token').value = ''; $('producer-token').value = ''; $('disconnect').hidden = true;
    $('session-list').replaceChildren(node('p', 'Connect a viewer to load sessions.', 'muted'));
    $('log-list').replaceChildren(node('p', 'Connect a viewer to load logs.', 'muted')); $('log-preview').hidden = true;
    state('Ready to connect'); $('live-message').textContent = 'Viewer disconnected.';
  }
  $('connect-form').addEventListener('submit', async e => {
    e.preventDefault(); const value = $('viewer-token').value.trim(); if (!value) return;
    disconnect(); token = value; const generation = epoch; $('live-message').textContent = 'Checking viewer access.';
    try {
      const r = await api(endpoints.latest), data = await r.json(); if (generation !== epoch) return;
      accept(data); $('disconnect').hidden = false; openSocket(generation);
      await Promise.allSettled([refreshSessions(), refreshLogs(), refreshStats()]);
    } catch (error) { if (generation === epoch) { disconnect(); $('live-message').textContent = error.message; } }
  });
  $('disconnect').addEventListener('click', disconnect);
  $('paste-token').addEventListener('click', async () => {
    try { $('viewer-token').value = await navigator.clipboard.readText(); $('viewer-token').focus(); }
    catch { $('live-message').textContent = 'Paste your viewer token into the field manually.'; }
  });

  async function refreshSessions() {
    const generation = epoch;
    try {
      const data = await (await api(endpoints.sessions + '?limit=20')).json(); if (generation !== epoch) return;
      $('session-list').replaceChildren(); $('session-message').textContent = `${data.total} sessions · ${bytes(data.storedBytes)} stored · ${data.retentionDays} day retention`;
      for (const s of data.sessions) {
        const card = node('article', null, 'card'), actions = node('div', null, 'actions');
        card.append(node('h3', `${s.room} · Session ${s.id}`), node('p', `${date(s.startedAt)} · ${s.frameCount} frames · ${s.maxPoints} points`));
        actions.append(button('Inspect', 'eye', async () => { const data = await (await api(endpoints.session(s.id))).json(); if (data.frame) showScan(data.frame); else $('session-message').textContent = 'This session has no stored frames.'; }),
          button('Merged PLY', 'download', () => download(endpoints.ply(s.id, 'merged'), `arescope-${s.id}-merged.ply`)),
          button('Last PLY', 'download', () => download(endpoints.ply(s.id, 'last'), `arescope-${s.id}-last.ply`)));
        if (s.hasMesh) actions.append(button('ARSM mesh', 'download', () => download(endpoints.mesh(s.id), `${s.id}.arsm`)));
        const remove = button('Delete', 'trash', async () => {
          const producer = $('producer-token').value; $('producer-token').value = '';
          if (!producer) { $('session-message').textContent = 'Enter a producer token below to remove a session.'; $('producer-token').focus(); return; }
          if (remove.dataset.confirm !== 'yes') { remove.dataset.confirm = 'yes'; remove.lastChild.textContent = 'Confirm delete'; $('session-message').textContent = 'Select Confirm delete to remove this session. Enter the producer token again.'; return; }
          await api(endpoints.session(s.id), {method: 'DELETE'}, producer); await refreshSessions(); await refreshStats();
        });
        actions.append(remove); card.append(actions); $('session-list').append(card);
      }
      if (!data.sessions.length) $('session-list').append(node('p', 'Stored scans will appear here.', 'muted'));
    } catch (e) { if (generation === epoch) $('session-message').textContent = e.message; }
  }
  async function refreshLogs() {
    const generation = epoch;
    try {
      const data = await (await api(endpoints.logs + '?limit=20')).json(); if (generation !== epoch) return;
      $('log-list').replaceChildren();
      for (const log of data.logs) {
        const card = node('article', null, 'card'), actions = node('div', null, 'actions');
        card.append(node('h3', log.file), node('p', `${bytes(log.bytes)} · ${new Date(log.at).toLocaleString()}`));
        actions.append(button('Read log', 'eye', async () => { const text = await (await api(endpoints.log(log.file))).text(); $('log-preview').textContent = text; $('log-preview').hidden = false; }), button('Download', 'download', () => download(endpoints.log(log.file), log.file)));
        card.append(actions); $('log-list').append(card);
      }
      if (!data.logs.length) $('log-list').append(node('p', 'Uploaded diagnostics will appear here.', 'muted'));
      $('log-message').textContent = '';
    } catch (e) { if (generation === epoch) $('log-message').textContent = e.message; }
  }
  async function refreshStats() {
    const generation = epoch;
    try {
      const s = await (await api(endpoints.stats)).json(); if (generation !== epoch) return;
      $('storage-stats').replaceChildren();
      for (const [label, value] of [['Retention', `${s.retentionDays} days`], ['Stored payload', `${bytes(s.payloadBytes)} / ${bytes(s.maxBytes)}`], ['Database', bytes(s.dbBytes)], ['History', `${s.sessionCount} sessions / ${s.frameCount} frames`], ['Accepted frames', s.ingest], ['Storage errors', s.storage_errors]]) {
        const row = node('div'); row.append(node('dt', label), node('dd', String(value))); $('storage-stats').append(row);
      }
    } catch (e) { if (generation === epoch) $('live-message').textContent = e.message; }
  }
  $('refresh-sessions').addEventListener('click', refreshSessions); $('refresh-logs').addEventListener('click', refreshLogs);
  document.addEventListener('panelchange', e => { if (token) { if (e.detail === 'sessions') refreshSessions(); if (e.detail === 'logs') refreshLogs(); if (e.detail === 'equipment') refreshStats(); } });

  function drawScan() {
    if (!activeScan) return;
    const canvas = $('scan'), ctx = canvas.getContext('2d'), dpr = Math.min(devicePixelRatio || 1, 2);
    const w = canvas.clientWidth, h = canvas.clientHeight; canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
    const pts = activeScan.points; if (!pts.length) return;
    const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
    for (const p of pts) p.forEach((v, k) => { low[k] = Math.min(low[k], v); high[k] = Math.max(high[k], v); });
    const center = low.map((v, k) => (v + high[k]) / 2), extent = Math.max(1, ...low.map((v, k) => high[k] - v)), scale = Math.min(w, h) / extent * .58;
    ctx.fillStyle = '#ee8a5b';
    for (const p of pts) {
      const [x, y, z] = p.map((v, k) => v - center[k]);
      ctx.globalAlpha = .55 + (y - low[1] + center[1]) / Math.max(1, high[1] - low[1]) * .45;
      ctx.fillRect(w / 2 + (x * .85 + z * .5) * scale, h / 2 + (z * .5 - x * .3 - y * .85) * scale, 2, 2);
    }
    ctx.globalAlpha = 1;
  }
  function showScan(frame) {
    if (!Array.isArray(frame.points)) return;
    activeScan = frame; $('live-overlay').hidden = !$('show-live').checked;
    $('overlay-title').textContent = frame.source === 'archived-quest' ? 'Quest archive' : 'Quest live';
    $('scan-caption').textContent = `${frame.room} · ${frame.points.length} points · Local metres`; drawScan();
  }
  $('close-overlay').addEventListener('click', () => { $('show-live').checked = false; $('live-overlay').hidden = true; });
  $('show-live').addEventListener('change', () => { $('live-overlay').hidden = !$('show-live').checked || !activeScan; drawScan(); });
  new ResizeObserver(drawScan).observe($('scan'));
  setInterval(() => {
    const now = Date.now() / 1000;
    for (const [room, frame] of rooms) if (now - frame.receivedAt > 30) rooms.delete(room);
    if (activeScan?.source === 'live-quest' && now - activeScan.receivedAt > 30) { activeScan = null; $('live-overlay').hidden = true; }
    renderRooms();
  }, 2000);
  setInterval(() => { if (token) refreshStats(); }, 15000);
})();
