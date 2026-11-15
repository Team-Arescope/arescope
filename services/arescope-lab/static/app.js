(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const endpoints = {
    latest: '/api/live/latest', stream: '/api/live/stream', sessions: '/api/live/sessions',
    session: id => `/api/live/sessions/${id}`, stats: '/api/live/stats',
    ply: (id, frame) => `/api/live/sessions/${id}/export.ply?frame=${frame}`,
    mesh: id => `/api/live/sessions/${id}/mesh`, logs: '/api/live/logs',
    log: name => `/api/live/logs/${encodeURIComponent(name)}`,
    guardianStatus: '/api/guardian/status', guardianModel: '/api/guardian/model',
    incidents: '/api/guardian/incidents?limit=30',
    label: id => `/api/guardian/incidents/${encodeURIComponent(id)}/label`,
    retrain: '/api/guardian/retrain', deploy: '/api/guardian/deploy', simulator: '/api/sim/rover', fleet: '/api/sim/fleet'
  };
  const wrapAngle = angle => Math.atan2(Math.sin(angle), Math.cos(angle));
  const fleetColors = ['#eeae76', '#80cdb5', '#8fbde7', '#c6a3df', '#d9ce86', '#ed9da7'];
  const bytes = n => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KiB` : `${(n / 1048576).toFixed(1)} MiB`;
  const date = at => new Date(at * 1000).toLocaleString();
  function node(tag, text, className) { const el = document.createElement(tag); if (text) el.textContent = text; if (className) el.className = className; return el; }
  function button(text, symbol, handler) {
    const b = node('button'); b.type = 'button'; b.append(window.LabShell.icon(symbol), document.createTextNode(text));
    b.addEventListener('click', async () => {
      b.disabled = true;
      const generation = epoch;
      try { await handler(); } catch (e) { if (generation === epoch) $(b.closest('#guardian') ? 'guardian-message' : b.closest('#logs') ? 'log-message' : 'session-message').textContent = e.message; }
      finally { if (b.closest('#guardian')) updateGuardianControls(); else b.disabled = false; }
    }); return b;
  }

  class Terrain {
    constructor(canvas) {
      this.canvas = canvas;
      this.gl = canvas.getContext('webgl', {antialias: true, alpha: true});
      this.yaw = -.5; this.pitch = .8; this.zoom = 1; this.scale = 1.5; this.mode = 'polygonal';
      this.viewCenter = [0, 0, 0]; this.viewScale = 1; this.focusedRover = null; this.fleetFocused = false; this.needsInitialFocus = true;
      this.roverMotion = new Map(); this.fleetStatic = []; this.fleetReceivedAt = 0;
      this.motionPreference = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null;
      this.motionPreference?.addEventListener('change', () => this.schedule());
      if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => {
        if (document.hidden && this.pending) { cancelAnimationFrame(this.pending); this.pending = 0; }
        else this.schedule();
      });
      if (!this.gl) throw new Error('3D rendering is unavailable in this browser.');
      const gl = this.gl;
      const compile = (type, source) => {
        const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error('Terrain shader could not start.');
        return shader;
      };
      const vs = compile(gl.VERTEX_SHADER, `
        attribute vec3 position; uniform float yaw; uniform float pitch; uniform float zoom;
        uniform float aspect; uniform float elevation; uniform vec3 viewCenter; uniform float viewScale; uniform float orthographic; varying float height; varying float depth;
        void main(){
          vec3 q=(position-viewCenter)*viewScale;
          vec3 p=vec3(q.x,q.y*elevation,q.z);
          vec3 r=vec3(cos(yaw)*p.x+sin(yaw)*p.z,p.y,-sin(yaw)*p.x+cos(yaw)*p.z);
          r=vec3(r.x,cos(pitch)*r.y-sin(pitch)*r.z,sin(pitch)*r.y+cos(pitch)*r.z);
          float d=3.8/zoom-r.z;
          // The inspection camera uses a parallel lens: a passing rover cannot
          // explode in size as it crosses the eye plane of a low-angle orbit.
          gl_Position=mix(vec4(r.x*2.2/aspect,r.y*2.2,1.002*d-.2002,d),
            vec4(r.x*2.2*zoom/(3.8*aspect),r.y*2.2*zoom/3.8,-r.z/256.0,1.0),orthographic);
          height=position.y;depth=d;
        }`);
      const fs = compile(gl.FRAGMENT_SHADER, `
        precision mediump float; uniform vec3 color; uniform float line; varying float height; varying float depth;
        void main(){float light=clamp(.8+height*.9,.55,1.4); float fog=clamp((depth-2.0)/9.0,0.0,.7);
          gl_FragColor=vec4(mix(color*mix(light,1.0,line),vec3(.051,.035,.027),fog),1.0);}`);
      this.program = gl.createProgram(); gl.attachShader(this.program, vs); gl.attachShader(this.program, fs); gl.linkProgram(this.program);
      if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) throw new Error('Terrain renderer could not start.');
      this.uniforms = Object.fromEntries(['yaw', 'pitch', 'zoom', 'aspect', 'elevation', 'color', 'line', 'viewCenter', 'viewScale', 'orthographic'].map(k => [k, gl.getUniformLocation(this.program, k)]));
      this.buffers = Object.fromEntries(['points', 'triangles', 'minimal', 'polygonal', 'fleet'].map(k => [k, gl.createBuffer()]));
      new ResizeObserver(() => this.draw()).observe(canvas);
      let drag = null;
      canvas.addEventListener('pointerdown', e => { if (e.button !== 0) return; canvas.focus({preventScroll: true}); drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
      canvas.addEventListener('pointermove', e => {
        if (!drag) return;
        this.yaw = wrapAngle(this.yaw + (e.clientX - drag[0]) * .006); this.pitch = wrapAngle(this.pitch + (e.clientY - drag[1]) * .005);
        drag = [e.clientX, e.clientY]; this.schedule();
      });
      canvas.addEventListener('pointerup', () => { drag = null; });
      canvas.addEventListener('pointercancel', () => { drag = null; });
      canvas.addEventListener('lostpointercapture', () => { drag = null; });
      canvas.addEventListener('dblclick', e => {
        const bounds = canvas.getBoundingClientRect(), x = e.clientX - bounds.left, y = e.clientY - bounds.top;
        const nearest = (this.fleetAnchors || []).map(a => ({id: a.carrierId, p: this.project(a.position)})).filter(a => a.p.inViewport)
          .sort((a, b) => Math.hypot(a.p.x - x, a.p.y - y) - Math.hypot(b.p.x - x, b.p.y - y))[0];
        if (nearest && Math.hypot(nearest.p.x - x, nearest.p.y - y) < 45) this.focusRover(nearest.id);
      });
      canvas.addEventListener('wheel', e => { e.preventDefault(); this.zoom = Math.max(.55, Math.min(this.focusedRover || this.fleetFocused ? 1.6 : 2.3, this.zoom * Math.exp(-e.deltaY * .001))); this.schedule(); }, {passive: false});
      canvas.addEventListener('keydown', e => {
        if (e.key.toLowerCase() === 'r') this.reset();
        else if (e.key.toLowerCase() === 'f') this.focusRover(this.focusedRover || this.roverMotion.keys().next().value);
        else if (e.key === 'ArrowLeft') this.yaw = wrapAngle(this.yaw - .1);
        else if (e.key === 'ArrowRight') this.yaw = wrapAngle(this.yaw + .1);
        else if (e.key === 'ArrowUp') this.pitch = wrapAngle(this.pitch - .1);
        else if (e.key === 'ArrowDown') this.pitch = wrapAngle(this.pitch + .1);
        else if (e.key === '+' || e.key === '=') this.zoom = Math.min(this.focusedRover || this.fleetFocused ? 1.6 : 2.3, this.zoom * 1.1);
        else if (e.key === '-' || e.key === '_') this.zoom = Math.max(.55, this.zoom / 1.1);
        else return;
        e.preventDefault(); this.schedule();
      });
      canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); $('terrain-error').hidden = false; });
      canvas.addEventListener('webglcontextrestored', () => location.reload());
    }
    reset() { this.yaw = -.5; this.pitch = .8; this.zoom = 1; this.focusedRover = null; this.fleetFocused = false; this.needsInitialFocus = false; this.viewCenter = [0, 0, 0]; this.viewScale = 1; this.draw(); }
    focusRover(carrierId) {
      if (!this.roverMotion.has(carrierId)) return false;
      this.focusedRover = carrierId; this.fleetFocused = false; this.cameraFrameKey = null; this.zoom = 1; this.schedule(); return true;
    }
    focusFleet() {
      if (!this.roverMotion.size) return false;
      this.focusedRover = null; this.fleetFocused = true; this.cameraFrameKey = null; this.zoom = 1; this.schedule(); return true;
    }
    schedule() { if (!this.pending && !(typeof document !== 'undefined' && document.hidden)) this.pending = requestAnimationFrame(() => { this.pending = 0; this.draw(); }); }
    now() { return typeof performance !== 'undefined' ? performance.now() : Date.now(); }
    load(data) {
      const {rows, cols} = data.grid, points = data.points, gl = this.gl;
      if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows < 2 || cols < 2 || !Array.isArray(points) || points.length !== rows * cols || points.some(p => !Array.isArray(p) || p.length !== 3 || !p.every(Number.isFinite))) throw new Error('Invalid terrain grid.');
      // Each cell adds a centre vertex; every index must still fit in Uint16.
      if (rows * cols + (rows - 1) * (cols - 1) > 65536) throw new Error('Terrain grid exceeds the 3D renderer vertex limit.');
      const {lo, hi, east, south, stepX, stepZ} = terrainDimensions(data), extent = Math.max(east, south);
      if (!(stepX > 0 && stepZ > 0 && extent > 0)) throw new Error('Invalid terrain spacing.');
      this.data = data; this.center = lo.map((v, k) => (v + hi[k]) / 2); this.extent = extent;
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
      this.normalized = normalized;
      this.counts = {};
      for (const [name, indices] of Object.entries({triangles, minimal, polygonal: minimal.concat(diagonals)})) {
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[name]); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW); this.counts[name] = indices.length;
      }
      this.setFleet(this.fleetState);
    }
    normalize(point, lift = 0) { return point.map((v, k) => (v - this.center[k] + (k === 1 ? lift : 0)) * 2 / this.extent); }
    surface(x, z) {
      const {rows, cols} = this.data.grid, points = this.data.points;
      const sx = points[1][0] - points[0][0], sz = points[cols][2] - points[0][2];
      const c = Math.max(0, Math.min(cols - 1, (x - points[0][0]) / sx));
      const r = Math.max(0, Math.min(rows - 1, (z - points[0][2]) / sz));
      const c0 = Math.min(cols - 2, Math.floor(c)), r0 = Math.min(rows - 2, Math.floor(r)), dx = c - c0, dz = r - r0;
      const a = r0 * cols + c0, h00 = points[a][1], h10 = points[a + 1][1], h01 = points[a + cols][1], h11 = points[a + cols + 1][1];
      return {height: h00 * (1 - dx) * (1 - dz) + h10 * dx * (1 - dz) + h01 * (1 - dx) * dz + h11 * dx * dz,
        dx: ((h10 - h00) * (1 - dz) + (h11 - h01) * dz) / sx,
        dz: ((h01 - h00) * (1 - dx) + (h11 - h10) * dx) / sz};
    }
    validPoint(p) { return Array.isArray(p) && p.length === 3 && p.every(Number.isFinite); }
    roverScale() { return .5; } // Fixed map metres per model unit, including at archive edges.
    sampleMotion(motion, now) {
      const t = this.motionPreference?.matches ? 1 : Math.max(0, Math.min(1, (now - motion.started) / motion.duration));
      const distance = motion.length * t;
      let left = distance, segment = 0, position = motion.path[0], heading = motion.heading;
      for (let i = 1; i < motion.path.length; i++) {
        const a = motion.path[i - 1], b = motion.path[i], length = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
        if (length < 1e-8) continue;
        segment = i - 1; heading = Math.atan2(b[0] - a[0], b[2] - a[2]);
        if (left <= length) { const f = left / length; position = a.map((v, k) => v + (b[k] - v) * f); break; }
        left -= length; position = b;
      }
      const priorDistance = motion.spinDistance || 0, radius = 4.2 * this.roverScale(position);
      motion.spinAngle = (motion.spinAngle ?? motion.angle) + (radius > 1e-5 ? Math.max(0, distance - priorDistance) / radius : 0);
      motion.spinDistance = distance;
      const result = {position: [position[0], this.surface(position[0], position[2]).height, position[2]], heading,
        angle: motion.spinAngle, distance, segment,
        active: motion.length > 1e-8 && t < 1};
      motion.sample = result; return result;
    }
    setFleet(state) {
      const now = this.now(), previousElapsed = this.fleetElapsed;
      if (Number.isFinite(previousElapsed) && state?.elapsedS > previousElapsed && now > this.fleetReceivedAt) {
        this.snapshotCadence = Math.min(2000, Math.max(now - this.fleetReceivedAt, (this.snapshotCadence || 1000) * .9));
      }
      this.fleetState = state; this.fleetElapsed = state?.elapsedS; this.fleetGeometry = []; this.fleetAnchors = []; this.fleetStatic = [];
      // Fleet coordinates belong to the archived HiRISE frame, never MOLA or Quest local space.
      if (this.data?.source !== 'nasa-pds-hirise' || state?.terrainSource !== this.data.source || state?.simulation !== true) { this.roverMotion.clear(); this.roverAnimating = false; this.schedule(); return; }
      this.fleetReceivedAt = now;
      if (Number.isFinite(previousElapsed) && state.elapsedS < previousElapsed) this.roverMotion.clear();
      const {rows, cols} = this.data.grid;
      const coverage = [], seen = new Set(), retained = new Set();
      for (const cell of state.coverage?.cells || []) {
        if (!Array.isArray(cell)) continue;
        const [r, c] = cell, key = `${r}:${c}`;
        if (!Number.isInteger(r) || !Number.isInteger(c) || r < 0 || c < 0 || r >= rows - 1 || c >= cols - 1 || seen.has(key)) continue;
        seen.add(key);
        const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
        // Match all four triangles of the terrain depth pass, including its cell centre.
        const m = rows * cols + r * (cols - 1) + c;
        for (const i of [a, b, m, b, e, m, e, d, m, d, a, m]) coverage.push(this.normalized[i * 3], this.normalized[i * 3 + 1] + .00001, this.normalized[i * 3 + 2]);
      }
      if (coverage.length) this.fleetStatic.push({vertices: coverage, mode: this.gl.TRIANGLES, color: '#253f35', kind: 'coverage'});
      for (const [i, rover] of (state.rovers || []).slice(0, 6).entries()) {
        const trail = (rover.trail || []).filter(p => this.validPoint(p));
        if (trail.length >= 2) this.fleetStatic.push({vertices: trail.flatMap(p => this.normalize([p[0], this.surface(p[0], p[2]).height, p[2]], 1.2)), mode: this.gl.LINE_STRIP, color: fleetColors[i]});
        if (!this.validPoint(rover.position)) continue;
        retained.add(rover.carrierId);
        const old = this.roverMotion.get(rover.carrierId), last = old && this.sampleMotion(old, now);
        const same = (a, b) => a && b && Math.hypot(a[0] - b[0], a[2] - b[2]) < 1e-5;
        const travelStates = ['surveying', 'responding', 'en_route', 'approaching'];
        const finishingApproach = old && (travelStates.includes(old.rover.status) || old.length > 0) && ['assisting', 'repairing'].includes(rover.status);
        const moving = state.running === true && (travelStates.includes(rover.status) || finishingApproach) && (!rover.fault || rover.fault === 'nominal');
        if (moving && old && same(old.path.at(-1), rover.position)) { old.rover = rover; old.color = fleetColors[i]; continue; }
        let path = [rover.position.slice()];
        if (moving && old && last && !this.motionPreference?.matches) {
          // Follow every acknowledged corner, including an unfinished prior segment.
          // If its junction fell out of the server trail, settle at the snapshot;
          // drawing a shortcut could otherwise cross an obstacle or unobserved ground.
          let junction = -1;
          for (let n = trail.length - 1; n >= 0; n--) if (same(trail[n], old.path.at(-1))) { junction = n; break; }
          if (junction >= 0) path = [last.position, ...old.path.slice(last.segment + 1), ...trail.slice(junction + 1), rover.position.slice()];
        }
        path = path.filter((p, n) => n === 0 || !same(p, path[n - 1]));
        const length = path.slice(1).reduce((sum, p, n) => sum + Math.hypot(...p.map((v, k) => v - path[n][k])), 0);
        // Keep a small acknowledged-route buffer for variable request latency.
        // Every new route starts at the rendered position and retains its corners;
        // no position is ever extrapolated beyond the latest server endpoint.
        const duration = Math.min(2500, Math.max(1000, this.snapshotCadence || 1000) * 1.25 + 250);
        this.roverMotion.set(rover.carrierId, {rover, color: fleetColors[i], path, length, duration, started: now,
          angle: last?.angle || 0, toolTime: old?.toolTime || 0, toolUpdatedAt: now, heading: Number.isFinite(rover.headingDeg) ? rover.headingDeg * Math.PI / 180 : 0});
      }
      for (const id of this.roverMotion.keys()) if (!retained.has(id)) this.roverMotion.delete(id);
      this.updateRovers(now, true);
      if (this.needsInitialFocus && this.roverMotion.size) { this.focusRover(this.roverMotion.keys().next().value); this.needsInitialFocus = false; }
      this.schedule();
    }
    roverMesh(motion, sample, now) {
      const batches = [], markerScale = this.roverScale(sample.position), elevation = Math.max(.01, this.scale), heading = sample.heading;
      if (markerScale <= 1e-5) return {batches, active: sample.active};
      const add = (a, b) => a.map((v, k) => v + b[k]), sub = (a, b) => a.map((v, k) => v - b[k]);
      const mul = (a, s) => a.map(v => v * s), unit = a => mul(a, 1 / (Math.hypot(...a) || 1));
      const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
      const dot = (a, b) => a.reduce((sum, v, k) => sum + v * b[k], 0);
      const pack = p => this.normalize([p[0], p[1] / elevation, p[2]]);
      const triangle = (vertices, a, b, c) => { vertices.push(...pack(a), ...pack(b), ...pack(c)); };
      const byColor = new Map();
      const mesh = color => { if (!byColor.has(color)) byColor.set(color, []); return byColor.get(color); };
      const quad = (color, a, b, c, d) => { const vertices = mesh(color); triangle(vertices, a, b, c); triangle(vertices, a, c, d); };
      const contacts = [];
      for (const side of [-12.5, 12.5]) for (const forward of [-13, 0, 13]) {
        const x = sample.position[0] + (Math.cos(heading) * side + Math.sin(heading) * forward) * markerScale;
        const z = sample.position[2] + (-Math.sin(heading) * side + Math.cos(heading) * forward) * markerScale;
        const s = this.surface(x, z), up = unit([-s.dx * elevation, 1, -s.dz * elevation]);
        const right = unit(cross(up, [Math.sin(heading), 0, Math.cos(heading)])), forwardAxis = unit(cross(right, up));
        const contact = [x, s.height * elevation, z];
        contacts.push({side, forward, contact, up, right, forwardAxis, center: add(contact, mul(up, 4.2 * markerScale))});
      }
      const centre = mul(contacts.reduce((sum, w) => add(sum, w.contact), [0, 0, 0]), 1 / 6);
      // Fit the body to all six contact normals; each suspension leg still reaches
      // its own wheel, rather than lifting the whole vehicle to the highest corner.
      const up = unit(contacts.reduce((sum, w) => add(sum, w.up), [0, 0, 0]));
      const right = unit(cross(up, [Math.sin(heading), 0, Math.cos(heading)])), forwardAxis = unit(cross(right, up));
      const clearance = Math.max(0, ...contacts.map(w => dot(sub(w.contact, centre), up))) / markerScale;
      const local = (side, forward, height) => add(centre, mul(add(add(mul(right, side), mul(forwardAxis, forward)), mul(up, height + clearance)), markerScale));
      const tint = (hex, factor) => '#' + hex.match(/[a-f\d]{2}/gi).map(h => Math.min(255, Math.round(parseInt(h, 16) * factor)).toString(16).padStart(2, '0')).join('');
      const box = (x0, z0, y0, x1, z1, y1, color) => {
        const p = (x, z, y) => local(x, z, y);
        quad(color, p(x0, z1, y1), p(x1, z1, y1), p(x1, z0, y1), p(x0, z0, y1));
        quad(tint(color, .72), p(x0, z1, y0), p(x1, z1, y0), p(x1, z1, y1), p(x0, z1, y1));
        quad(tint(color, .54), p(x0, z0, y0), p(x0, z1, y0), p(x0, z1, y1), p(x0, z0, y1));
        quad(tint(color, .85), p(x1, z1, y0), p(x1, z0, y0), p(x1, z0, y1), p(x1, z1, y1));
        quad(tint(color, .65), p(x1, z0, y0), p(x0, z0, y0), p(x0, z0, y1), p(x1, z0, y1));
        quad(tint(color, .45), p(x0, z0, y0), p(x1, z0, y0), p(x1, z1, y0), p(x0, z1, y0));
      };
      const rod = (a, b, radius, color) => {
        const axis = unit(sub(b, a)), u = unit(cross(axis, Math.abs(axis[1]) < .9 ? [0, 1, 0] : [1, 0, 0])), v = cross(axis, u);
        for (let n = 0; n < 6; n++) {
          const radial = angle => mul(add(mul(u, Math.cos(angle)), mul(v, Math.sin(angle))), radius);
          const r0 = radial(n * Math.PI / 3), r1 = radial((n + 1) * Math.PI / 3);
          quad(n % 2 ? color : tint(color, .8), add(a, r0), add(a, r1), add(b, r1), add(b, r0));
          triangle(mesh(color), a, add(a, r1), add(a, r0)); triangle(mesh(color), b, add(b, r0), add(b, r1));
        }
      };
      // A low rectangular deck, exposed six-wheel suspension, mast and twin optics.
      // The model is enlarged for a kilometre-scale map; local part heights undo
      // terrain exaggeration so wheels stay circular while the suspension tilts.
      box(-9, -14, 6.8, 9, 13, 10.5, motion.color);
      box(-7.5, -11, 10.6, 7.5, 1, 11.4, '#58636a');
      box(-.3, -11, 11.45, .3, 1, 11.6, '#adb7b9');
      for (const z of [-7, -3]) box(-7.5, z, 11.45, 7.5, z + .4, 11.6, '#adb7b9');
      for (const w of contacts) {
        rod(local(w.side * .58, w.forward, 7.3), w.center, .8 * markerScale, '#9caaa9');
        const rim = w.side < 0 ? -1 : 1;
        const cylinder = (radius, width, color, spokes) => {
          const radial = angle => mul(add(mul(w.forwardAxis, Math.sin(angle)), mul(w.up, Math.cos(angle))), radius * markerScale);
          for (let n = 0; n < 12; n++) {
            const a = n * Math.PI / 6 + sample.angle, b = (n + 1) * Math.PI / 6 + sample.angle;
            const edge = (angle, side) => add(w.center, add(radial(angle), mul(w.right, side * width * markerScale)));
            quad(n % 3 ? color : tint(color, 1.18), edge(a, -1), edge(b, -1), edge(b, 1), edge(a, 1));
            for (const side of [-1, 1]) triangle(mesh(spokes && n % 3 === 0 ? '#e0e6e2' : color), add(w.center, mul(w.right, side * width * markerScale)), edge(a, side), edge(b, side));
          }
        };
        cylinder(4.2, 2.2, '#252c30', false); cylinder(2.8, 2.24, '#8b9999', true);
        rod(add(w.center, mul(w.right, rim * 2.2 * markerScale)), add(w.center, mul(w.right, rim * 2.45 * markerScale)), 1.1 * markerScale, motion.color);
      }
      box(-1, 7, 10.5, 1, 9, 20, '#d5dcd6');
      box(-5, 6.5, 19, 5, 10.5, 22.7, motion.color);
      box(-4, 10.55, 19.6, -1, 10.85, 22, '#202b31'); box(1, 10.55, 19.6, 4, 10.85, 22, '#202b31');
      const recovery = motion.rover.recovery || {}, target = this.roverMotion.get(motion.rover.targetId);
      const requestedRepair = motion.rover.status === 'repairing' || (recovery.phase === 'repairing' && Boolean(target));
      const live = this.fleetState.running === true && !this.motionPreference?.matches && now - this.fleetReceivedAt < 1600;
      const other = target?.sample?.position || target?.rover.position;
      const separation = other ? Math.hypot(other[0] - sample.position[0], other[2] - sample.position[2]) : Infinity;
      const inServiceZone = separation >= 22 - .01 && separation <= 26 + .01;
      const stationary = !sample.active && !target?.sample?.active;
      let repairing = Boolean(requestedRepair && target && inServiceZone && stationary), serviceContact = null, serviceReachable = false;
      // Time accumulates only while receiving fresh, running service snapshots.
      // Paused, stale and reduced-motion frames retain the exact last joint pose.
      if (repairing && live) motion.toolTime = (motion.toolTime || 0) + Math.max(0, Math.min(80, now - (motion.toolUpdatedAt ?? now)));
      motion.toolUpdatedAt = now;
      const phase = (motion.toolTime || 0) * .0038;
      let shoulder = local(0, 16, 10.8), elbow = local(2, 3, 18), wrist = local(5, 10, 12);
      let tool = add(wrist, mul(up, -1)), serviceNormal = up, jointSwivel = 0;
      if (repairing) {
        // Reconstruct the target's actual suspension frame. Tool coordinates use
        // the same exaggerated terrain / unexaggerated body convention as its mesh.
        const th = target.sample?.heading ?? (target.rover.headingDeg || 0) * Math.PI / 180, tc = [];
        for (const side of [-12.5, 12.5]) for (const forward of [-13, 0, 13]) {
          const x = other[0] + (Math.cos(th) * side + Math.sin(th) * forward) * markerScale;
          const z = other[2] + (-Math.sin(th) * side + Math.cos(th) * forward) * markerScale;
          const s = this.surface(x, z); tc.push({p: [x, s.height * elevation, z], up: unit([-s.dx * elevation, 1, -s.dz * elevation])});
        }
        const tu = unit(tc.reduce((sum, c) => add(sum, c.up), [0, 0, 0])), tr = unit(cross(tu, [Math.sin(th), 0, Math.cos(th)])), tf = unit(cross(tr, tu));
        const centre = mul(tc.reduce((sum, c) => add(sum, c.p), [0, 0, 0]), 1 / 6);
        const clearance = Math.max(0, ...tc.map(c => dot(sub(c.p, centre), tu)));
        const targetLocal = (x, z, y) => add(centre, add(add(mul(tr, x), mul(tf, z)), mul(tu, y + clearance)));
        const towardHelper = sub(shoulder, centre), dx = dot(towardHelper, tr), dz = dot(towardHelper, tf);
        const sweep = Math.sin(phase) * 1.25;
        // Service the nearest deck panel; wheel faults use the exposed wheel rim.
        const wheelFault = ['wheel_slip', 'wheel_jam', 'wheel_stuck', 'stuck_wheel'].includes(target.rover.fault);
        let sx, sz, sy;
        if (wheelFault) {
          sx = Math.sign(dx || 1) * 7.37; sz = Math.abs(dz) > 3 ? Math.sign(dz) * 6.5 : 0; sy = 2.1 + Math.sin(phase) * .7;
          serviceNormal = mul(tr, Math.sign(dx || 1));
        } else if (Math.abs(dx) / 4.5 > Math.abs(dz) / 6.5) {
          sx = Math.sign(dx || 1) * 4.5; sz = Math.max(-5.8, Math.min(5.8, dz * 4.5 / Math.abs(dx) + sweep)); sy = 4.3 + .75 * Math.cos(phase);
          serviceNormal = mul(tr, Math.sign(dx || 1));
        } else {
          sz = Math.sign(dz || 1) * (dz < 0 ? 7 : 6.5); sx = Math.max(-3.7, Math.min(3.7, dx * Math.abs(sz) / Math.abs(dz) + sweep)); sy = 4.3 + .75 * Math.cos(phase);
          serviceNormal = mul(tf, Math.sign(dz || 1));
        }
        serviceContact = targetLocal(sx, sz, sy); tool = serviceContact;
        // Two fixed-length links and a short tool: solve the elbow instead of
        // stretching an arbitrary beam toward a remote carrier.
        const desiredWrist = add(tool, mul(serviceNormal, .65)), delta = sub(desiredWrist, shoulder), distance = Math.hypot(...delta);
        const upper = 7.2, forearm = 6.15;
        serviceReachable = distance <= upper + forearm && distance >= Math.abs(upper - forearm);
        if (serviceReachable) {
          wrist = desiredWrist;
          const axis = unit(delta), bend = unit(sub(up, mul(axis, dot(up, axis)))), tangent = cross(axis, bend);
          const along = (upper * upper - forearm * forearm + distance * distance) / (2 * distance);
          const rise = Math.sqrt(Math.max(0, upper * upper - along * along));
          jointSwivel = Math.sin(phase * .83) * .3;
          elbow = add(shoulder, add(mul(axis, along), mul(add(mul(bend, Math.cos(jointSwivel)), mul(tangent, Math.sin(jointSwivel))), rise)));
        } else { repairing = false; serviceContact = null; tool = add(wrist, mul(up, -1)); }
      }
      rod(local(0, 12, 10.8), shoulder, 1.2 * markerScale, '#9caaa9');
      rod(shoulder, elbow, .95 * markerScale, '#d4ddd7'); rod(elbow, wrist, .7 * markerScale, motion.color);
      rod(wrist, tool, .65 * markerScale, '#d4ddd7');
      const grip = mul(unit(cross(serviceNormal, Math.abs(serviceNormal[1]) < .9 ? up : right)), .7);
      rod(sub(tool, grip), add(tool, grip), .5 * markerScale, '#d4ddd7');
      if (motion.rover.fault && motion.rover.fault !== 'nominal') box(-5.2, 6.3, 23, 5.2, 9.8, 23.7, recovery.requiresApproval ? '#e8aa62' : '#e2a58d');
      // A small, steady deck strip reports acknowledged recovery progress; the
      // animation never advances this value or clears a simulated fault itself.
      if (['repairing', 'validating', 'awaiting_approval'].includes(recovery.phase)) {
        const progress = Number.isFinite(recovery.progress) ? Math.max(0, Math.min(1, recovery.progress)) : 0;
        box(-7.5, -15.5, 11, 7.5, -13.5, 12, '#303d40');
        if (progress > 0) box(-7.5, -15.6, 12.05, -7.5 + 15 * progress, -13.4, 12.7, '#a7d9c1');
      }
      for (const [color, vertices] of byColor) batches.push({color, vertices, mode: this.gl.TRIANGLES});
      const grounded = contacts.every(w => Math.abs(w.contact[1] / elevation - this.surface(w.contact[0], w.contact[2]).height) < 1e-7);
      this.fleetAnchors.push({carrierId: motion.rover.carrierId, position: pack(local(0, 8, 23)), wheelAngle: sample.angle, wheelCount: contacts.length,
        groundContacts: contacts.map(w => [w.contact[0], w.contact[1] / elevation, w.contact[2]]), grounded, repairing,
        armJoints: Object.fromEntries(Object.entries({shoulder, elbow, wrist}).map(([k, p]) => [k, [p[0], p[1] / elevation, p[2]]])),
        toolTip: [tool[0], tool[1] / elevation, tool[2]], serviceContact: serviceContact && [serviceContact[0], serviceContact[1] / elevation, serviceContact[2]],
        serviceReachable, jointSwivel, serviceDistance: Number.isFinite(separation) ? separation : null,
        worldPosition: sample.position.slice(), visualScale: markerScale, recoveryPhase: recovery.phase || 'none'});
      return {batches, active: sample.active || (repairing && live)};
    }
    updateRovers(now, full = false) {
      this.fleetAnchors = []; const batches = []; let active = false;
      for (const motion of this.roverMotion.values()) this.sampleMotion(motion, now);
      for (const motion of this.roverMotion.values()) { const result = this.roverMesh(motion, motion.sample, now); batches.push(...result.batches); active ||= result.active; }
      const dynamic = batches.flatMap(b => b.vertices), staticCount = this.fleetStatic.reduce((sum, b) => sum + b.vertices.length, 0);
      this.fleetGeometry = []; let offset = 0;
      for (const batch of [...this.fleetStatic, ...batches]) { this.fleetGeometry.push({mode: batch.mode, color: batch.color, kind: batch.kind, first: offset / 3, count: batch.vertices.length / 3}); offset += batch.vertices.length; }
      this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.buffers.fleet);
      if (full || offset !== this.fleetBufferSize) {
        this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array([...this.fleetStatic.flatMap(b => b.vertices), ...dynamic]), this.gl.DYNAMIC_DRAW); this.fleetBufferSize = offset;
      } else if (dynamic.length) this.gl.bufferSubData(this.gl.ARRAY_BUFFER, staticCount * 4, new Float32Array(dynamic));
      this.roverGeometryScale = this.scale; this.roverAnimating = active;
      return active;
    }
    project(point) {
      const [x, y, z] = point.map((v, k) => (v - this.viewCenter[k]) * this.viewScale), cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
      const rx = cy * x + sy * z, rz = -sy * x + cy * z;
      const ry = cp * y * this.scale - sp * rz, depth = 3.8 / this.zoom - (sp * y * this.scale + cp * rz);
      const divisor = this.inspectionCamera ? 3.8 / this.zoom : depth;
      const nx = rx * 2.2 / (this.canvas.width / this.canvas.height) / divisor, ny = ry * 2.2 / divisor;
      const depthVisible = this.inspectionCamera ? Math.abs(3.8 / this.zoom - depth) < 256 : depth > .1 && depth < 100.1;
      return {x: (nx + 1) * this.canvas.clientWidth / 2, y: (1 - ny) * this.canvas.clientHeight / 2, depth, inViewport: depthVisible && Math.abs(nx) <= 1 && Math.abs(ny) <= 1};
    }
    draw() {
      this.canvas.dataset.pitch = String(this.pitch); this.canvas.dataset.yaw = String(this.yaw); this.canvas.dataset.zoom = String(this.zoom);
      if (!this.counts) return;
      if (this.roverMotion.size && (this.roverAnimating || this.roverGeometryScale !== this.scale)) this.updateRovers(this.now());
      const focused = this.roverMotion.get(this.focusedRover);
      const previousCenter = this.viewCenter.slice(), previousScale = this.viewScale;
      this.inspectionCamera = Boolean(focused || this.fleetFocused);
      this.zoom = Math.max(.55, Math.min(this.inspectionCamera ? 1.6 : 2.3, this.zoom));
      if (focused) {
        const position = focused.sample?.position || focused.rover.position;
        const partnerId = focused.rover.targetId || focused.rover.recovery?.helperId;
        const partner = ['approaching', 'repairing', 'validating'].includes(focused.rover.recovery?.phase) || ['approaching', 'assisting', 'repairing'].includes(focused.rover.status) ? this.roverMotion.get(partnerId) : null;
        if (partner) {
          const other = partner.sample?.position || partner.rover.position;
          const span = Math.max(75, Math.hypot(position[0] - other[0], position[2] - other[2], (position[1] - other[1]) * this.scale) + 40);
          this.viewCenter = this.normalize(position.map((v, k) => (v + other[k]) / 2), 5 / this.scale); this.viewScale = this.extent / span;
        } else { this.viewCenter = this.normalize(position, 5 / this.scale); this.viewScale = this.extent / 75; }
      } else if (this.fleetFocused && this.roverMotion.size) {
        const positions = [...this.roverMotion.values()].map(m => m.sample?.position || m.rover.position);
        const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
        for (const p of positions) { const padding = this.roverScale(p) * 32; p.forEach((v, k) => { lo[k] = Math.min(lo[k], v - padding); hi[k] = Math.max(hi[k], v + padding); }); }
        this.viewCenter = this.normalize(lo.map((v, k) => (v + hi[k]) / 2), 5 / this.scale);
        const span = Math.max(Math.hypot(hi[0] - lo[0], hi[2] - lo[2], (hi[1] - lo[1]) * this.scale), 75);
        this.viewScale = this.extent / span;
      } else { this.focusedRover = null; this.fleetFocused = false; this.viewCenter = [0, 0, 0]; this.viewScale = 1; }
      const now = this.now(), cameraKey = this.focusedRover || (this.fleetFocused ? 'fleet' : 'region');
      let cameraAnimating = false;
      if (this.inspectionCamera && this.cameraFrameKey === cameraKey && !this.motionPreference?.matches && this.fleetState?.running) {
        const alpha = 1 - Math.exp(-Math.max(0, now - (this.cameraFrameAt ?? now)) / 140);
        const targetCenter = this.viewCenter, targetScale = this.viewScale;
        this.viewCenter = previousCenter.map((v, k) => v + (targetCenter[k] - v) * alpha);
        this.viewScale = previousScale + (targetScale - previousScale) * alpha;
        cameraAnimating = Math.hypot(...targetCenter.map((v, k) => (v - this.viewCenter[k]) * this.viewScale)) > .0005 || Math.abs(this.viewScale / targetScale - 1) > .001;
        if (!cameraAnimating) { this.viewCenter = targetCenter; this.viewScale = targetScale; }
      }
      this.cameraFrameKey = cameraKey; this.cameraFrameAt = now;
      this.canvas.dataset.focusedRover = this.focusedRover || '';
      this.canvas.dataset.cameraMode = focused ? 'rover' : this.fleetFocused ? 'fleet' : 'region';
      const gl = this.gl, canvas = this.canvas, dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * dpr)); canvas.height = Math.max(1, Math.round(canvas.clientHeight * dpr));
      // Coordinates are CSS pixels relative to the canvas; depth testing still decides hill occlusion.
      canvas.dataset.fleetMarkers = JSON.stringify((this.fleetAnchors || []).map(anchor => ({...anchor, ...this.project(anchor.position)})));
      gl.viewport(0, 0, canvas.width, canvas.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.useProgram(this.program); gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
      const u = this.uniforms;
      for (const [key, value] of Object.entries({yaw: this.yaw, pitch: this.pitch, zoom: this.zoom, aspect: canvas.width / canvas.height, elevation: this.scale, viewScale: this.viewScale, orthographic: this.inspectionCamera ? 1 : 0})) gl.uniform1f(u[key], value);
      gl.uniform3f(u.viewCenter, ...this.viewCenter);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.points);
      const attr = gl.getAttribLocation(this.program, 'position'); gl.enableVertexAttribArray(attr); gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, 0, 0);
      // Filled terrain writes depth, so lines behind slopes stay occluded.
      gl.enable(gl.POLYGON_OFFSET_FILL); gl.polygonOffset(2, 2); gl.uniform3f(u.color, .075, .039, .025); gl.uniform1f(u.line, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers.triangles); gl.drawElements(gl.TRIANGLES, this.counts.triangles, gl.UNSIGNED_SHORT, 0); gl.disable(gl.POLYGON_OFFSET_FILL);
      // Coverage is a quiet surface tint beneath the terrain grid, rather than
      // an elevated slab that can hide the wheels of a small boundary rover.
      if (this.fleetGeometry?.some(b => b.kind === 'coverage')) {
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.fleet); gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, 0, 0);
        gl.uniform1f(u.line, 0);
        for (const batch of this.fleetGeometry.filter(b => b.kind === 'coverage')) {
          gl.uniform3f(u.color, ...batch.color.match(/[a-f\d]{2}/gi).map(h => parseInt(h, 16) / 255));
          gl.drawArrays(batch.mode, batch.first, batch.count);
        }
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.points); gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, 0, 0);
      }
      gl.uniform3f(u.color, .35, .18, .10); gl.uniform1f(u.line, 1);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[this.mode]); gl.drawElements(gl.LINES, this.counts[this.mode], gl.UNSIGNED_SHORT, 0);
      if (this.fleetGeometry?.length) {
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers.fleet); gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, 0, 0);
        for (const batch of this.fleetGeometry) {
          if (batch.kind === 'coverage') continue;
          gl.uniform3f(u.color, ...batch.color.match(/[a-f\d]{2}/gi).map(h => parseInt(h, 16) / 255));
          gl.drawArrays(batch.mode, batch.first, batch.count);
        }
      }
      canvas.dataset.ready = 'true';
      if (this.roverAnimating || cameraAnimating) this.schedule();
    }
  }
  function terrainDimensions(data) {
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const p of data.points) p.forEach((v, k) => { lo[k] = Math.min(lo[k], v); hi[k] = Math.max(hi[k], v); });
    return {lo, hi, east: hi[0] - lo[0], south: hi[2] - lo[2], stepX: data.points[1][0] - data.points[0][0], stepZ: data.points[data.grid.cols][2] - data.points[0][2]};
  }
  function terrainLabels(data) {
    const {east, south, stepX, stepZ} = terrainDimensions(data), hirise = data.source === 'nasa-pds-hirise';
    const name = hirise ? 'HiRISE' : 'MOLA', mission = hirise ? 'MRO' : 'MGS';
    const extent = `${(east / 1000).toFixed(2)} × ${(south / 1000).toFixed(2)} km`;
    const spacing = Math.abs(stepX - stepZ) < .00001 ? `${stepX.toFixed(1)} m` : `${stepX.toFixed(1)} × ${stepZ.toFixed(1)} m`;
    const samples = `${data.grid.rows} × ${data.grid.cols}`, native = data.metadata?.native_spacing_m;
    const nativeNote = Number.isFinite(native) && native > 0 ? ` Native spacing: ${native.toFixed(4)} m.` : '';
    return {
      count: `${samples} samples`,
      caption: `${name} archive · ${extent}`,
      source: `NASA ${mission} / ${name} · ${spacing} display step`,
      notes: `${name} display grid: ${samples} (rows × columns). Extent: ${extent}; display step: ${spacing} (east × south).${nativeNote}`,
      fleet: `Synthetic accelerated survey on the NASA ${name} archive: ${samples} samples, ${spacing} display step, ${extent} (east × south), ${(east * south / 1000000).toFixed(1)} km². Rover models are enlarged for visibility. Guardian flags risk; mission policy coordinates survey and simulated recovery.`
    };
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
      const labels = terrainLabels(data);
      $('grid-count').textContent = labels.count;
      $('terrain-caption').textContent = labels.caption;
      $('terrain-source').textContent = labels.source;
      $('source-notes').textContent = labels.notes;
      if (data.source === 'nasa-pds-hirise') $('fleet-description').textContent = labels.fleet;
      if (fleetState) renderFleet(fleetState);
    } catch (e) { $('terrain-error').hidden = false; $('terrain-caption').textContent = e.message; }
  }
  $('terrain-select').addEventListener('change', loadTerrain);
  $('retry-terrain').addEventListener('click', loadTerrain);
  $('grid-mode').addEventListener('change', () => { if (terrain) { terrain.mode = $('grid-mode').value; terrain.draw(); } });
  $('exaggeration').addEventListener('input', () => { $('exaggeration-value').textContent = `${Number($('exaggeration').value).toFixed(1)}×`; if (terrain) { terrain.scale = Number($('exaggeration').value); terrain.draw(); } });
  $('reset-view').addEventListener('click', () => terrain?.reset());
  loadTerrain();

  let token = '', socket = null, poll = null, reconnect = null, epoch = 0, activeScan = null;
  let guardianRequest = 0, guardianBusy = false, candidateReady = false, candidateVersion = null, incidentSnapshot = '';
  let fleetState = null, fleetPoll = null, fleetRequest = 0, fleetBusy = false, fleetAvailable = null, fleetSnapshot = '';
  const incidentDrafts = new Map();
  const rooms = new Map();
  async function api(path, options = {}, producer = null) {
    const auth = producer === null ? token : producer;
    if (!auth) throw new Error(producer === null ? 'Connect a viewer first.' : 'Enter a producer token in Guardian.');
    const response = await fetch(path, {...options, cache: 'no-store', headers: {...options.headers, Authorization: `Bearer ${auth}`}});
    if (!response.ok) {
      const error = new Error(response.status === 401 || response.status === 403 ? 'Token was not accepted for this action.' : response.status === 404 ? 'This item or service is not available.' : response.status === 409 ? 'Model state changed or validation is required. Refresh Guardian and review the candidate.' : 'Request could not be completed. Try again.');
      error.status = response.status; throw error;
    }
    return response;
  }
  async function download(path, name) {
    const generation = epoch, response = await api(path), blob = await response.blob(); if (generation !== epoch) return;
    const url = URL.createObjectURL(blob);
    const a = node('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function state(text, active = false) { $('connection-status').textContent = text; $('connection-dot').classList.toggle('active', active); }
  const number = value => typeof value === 'number' && Number.isFinite(value);
  const metric = (value, digits = 0, suffix = '') => number(value) ? `${value.toFixed(digits)}${suffix}` : '—';
  const causeNames = {nominal: 'Nominal', dust: 'Dust on camera', dust_or_occlusion: 'Dust or occlusion', low_texture: 'Low texture', glare: 'Glare or shadow', glare_or_shadow: 'Glare or shadow', wheel_slip: 'Wheel slip', wheel_jam: 'Wheel obstruction', hq_link_broken: 'HQ link broken', pose_jump: 'Pose jump', sensor_drop: 'Sensor dropout', sensor_dropout: 'Sensor dropout'};
  const causes = ['nominal', 'dust', 'low_texture', 'glare', 'wheel_slip', 'sensor_drop'];
  const fleetCauses = [...causes, 'wheel_jam', 'hq_link_broken'];
  const roverLabel = id => /^fleet-rover-\d+$/.test(id || '') ? `Rover ${id.split('-').at(-1)}` : id || 'Rover';
  function roverStatus(rover) {
    const phase = rover.recovery?.phase;
    if (phase === 'awaiting_approval') return rover.recovery.held ? 'Kept halted' : 'Approval needed';
    if (phase === 'repairing') return `Receiving service · ${Math.round((rover.recovery.progress || 0) * 100)}%`;
    if (phase === 'validating') return 'Checking recovery';
    if (phase === 'approaching') return 'Helper approaching';
    if (phase === 'failed') return 'Service approach blocked';
    return {surveying: 'Surveying', responding: 'On the way', approaching: 'Approaching for service', assisting: 'Inspecting', repairing: 'Servicing', halted: 'Halted', waiting: 'Standing by'}[rover.status] || 'Standing by';
  }
  const causeName = value => causeNames[value] || value || '—';
  const carrierName = frame => frame.carrierType === 'rover' ? 'Rover' : 'Mast testbed';
  const carrierKey = frame => frame.carrierId || frame.room;
  const archived = frame => String(frame.source || '').startsWith('archived-');
  const fleetFrame = frame => frame.room === 'gale-fleet-sim' || (frame.source === 'simulated-rover' && /^fleet-rover-/.test(carrierKey(frame) || ''));
  const riskLevel = g => ['nominal', 'warning', 'critical'].includes(g?.riskLevel) ? g.riskLevel : 'unknown';
  function updateFleetControls() {
    const permitted = Boolean(token && $('producer-token').value.trim()) && !fleetBusy && fleetAvailable !== false;
    document.querySelectorAll('[data-fleet-action]').forEach(b => { b.disabled = !permitted; });
    for (const id of ['fleet-count', 'fleet-speed', 'fleet-fault']) $(id).disabled = !token || fleetBusy || fleetAvailable === false;
    $('fleet-target').disabled = !token || fleetBusy || !fleetState?.rovers.length || fleetAvailable === false;
    $('fleet-inject').disabled = !permitted || !fleetState?.rovers.some(r => r.carrierId === $('fleet-target').value);
    $('refresh-fleet').disabled = !token || fleetBusy;
    $('fleet-auto-repair').disabled = !permitted;
    document.querySelectorAll('[data-fleet-decision]').forEach(b => { b.disabled = !permitted || (b.dataset.fleetDecision === 'hold_recovery' && b.dataset.held === 'true'); });
    const needsViewer = !token, needsProducer = !needsViewer && !$('producer-token').value.trim();
    const access = needsViewer ? 'Connect a viewer in Equipment and live to enable Start fleet.'
      : needsProducer ? 'Viewer connected. Enter a producer token in Operator access above to enable Start fleet.'
      : fleetBusy ? 'Applying fleet command. Please wait for the controls to become available.'
      : fleetAvailable === false ? 'Fleet service unavailable. Use Refresh fleet to check again.'
      : !fleetState ? 'Loading fleet state. Viewer connected and producer token entered.'
      : 'Viewer connected and producer token entered. Fleet controls are available.';
    if ($('fleet-access-status').textContent !== access) $('fleet-access-status').textContent = access;
    $('fleet-connect-viewer').hidden = !needsViewer;
    $('fleet-enter-producer').hidden = !needsProducer;
    $('fleet-access-steps').hidden = !needsViewer && !needsProducer;
  }
  function resetFleet() {
    clearTimeout(fleetPoll); fleetPoll = null; fleetRequest++; fleetState = null; fleetBusy = false; fleetAvailable = null; fleetSnapshot = '';
    terrain?.setFleet(null); $('fleet-map').hidden = true; delete $('stage').dataset.fleet;
    $('follow-rover').hidden = true;
    $('view-fleet').hidden = true;
    $('fleet-map-status').textContent = ''; $('fleet-map-rovers').replaceChildren();
    $('fleet-map-recovery').hidden = true; $('fleet-map-recovery').textContent = '';
    $('fleet-approvals').hidden = true; $('fleet-approval-list').replaceChildren(); delete $('fleet-approval-list').dataset.snapshot;
    $('fleet-summary').hidden = true; $('fleet-summary-rovers').replaceChildren();
    $('fleet-status').textContent = 'Connect a viewer to follow the fleet.';
    $('fleet-percent').textContent = '—'; $('fleet-coverage').value = 0; $('fleet-area').textContent = 'No survey loaded.';
    $('fleet-rovers').replaceChildren(node('p', 'No fleet state loaded.', 'muted'));
    $('fleet-events').replaceChildren(node('li', 'No fleet events loaded.', 'muted'));
    const option = node('option', 'Awaiting fleet'); option.value = ''; $('fleet-target').replaceChildren(option);
    $('fleet-count').value = '3'; $('fleet-speed').value = '60'; $('fleet-fault').value = 'dust';
    $('fleet-auto-repair').checked = true;
    $('fleet-message').textContent = 'Uses the viewer connection and the token in Operator access.'; updateFleetControls();
  }
  function renderFleet(state) {
    if (state?.simulation !== true || state.terrainSource !== 'nasa-pds-hirise' || !Array.isArray(state.rovers) || state.rovers.length > 6 || !state.coverage || !Array.isArray(state.coverage.cells)) throw new Error('Fleet state could not be read. Refresh to try again.');
    fleetState = state; fleetAvailable = true;
    const coverage = state.coverage, percent = number(coverage.percent) ? Math.max(0, Math.min(100, coverage.percent)) : 0;
    const summary = `${state.running ? 'Running' : 'Stopped'} · ${state.rovers.length} rovers · ${metric(state.speedMultiplier)}× · ${metric(state.elapsedS)} s simulated`;
    $('fleet-status').textContent = summary; $('fleet-percent').textContent = metric(percent, 1, '%'); $('fleet-coverage').value = percent;
    $('fleet-area').textContent = `${metric(coverage.scannedCells)} / ${metric(coverage.totalCells)} cells · ${metric(coverage.areaM2 / 1000000, 3)} / ${metric(coverage.totalAreaM2 / 1000000, 2)} km²`;
    $('fleet-summary').hidden = false;
    $('fleet-map').hidden = false; $('stage').dataset.fleet = 'true';
    $('fleet-map-status').textContent = `${state.running ? 'Running' : 'Stopped'} · ${metric(percent, 1, '%')} scanned · ${metric(state.speedMultiplier)}×`;
    const mapOnHiRISE = $('terrain-select').value === 'hirise';
    $('follow-rover').hidden = !mapOnHiRISE || !state.rovers.length;
    $('view-fleet').hidden = !mapOnHiRISE || !state.rovers.length;
    $('fleet-map-frame').textContent = mapOnHiRISE ? 'Simulation · NASA HiRISE terrain · Rovers enlarged' : 'Select HiRISE in View settings to see the fleet.';
    $('fleet-auto-repair').checked = state.autoRepair !== false;
    renderFleetRecovery(state);
    const previous = $('fleet-target').value, ids = state.rovers.map(r => r.carrierId);
    if (JSON.stringify(ids) !== JSON.stringify([...$('fleet-target').options].map(o => o.value))) {
      $('fleet-target').replaceChildren(...ids.map(id => { const option = node('option', id); option.value = id; return option; }));
      if (ids.includes(previous)) $('fleet-target').value = previous;
    }
    const snapshot = JSON.stringify([state.rovers, state.events, coverage.cells, state.running, state.elapsedS, state.autoRepair]);
    if (snapshot !== fleetSnapshot) {
      fleetSnapshot = snapshot; terrain?.setFleet(state); $('fleet-rovers').replaceChildren(); $('fleet-map-rovers').replaceChildren(); $('fleet-summary-rovers').replaceChildren();
      state.rovers.forEach((rover, i) => {
        const card = node('article', null, 'card fleet-rover'), color = fleetColors[i];
        card.style.setProperty('--rover-color', color); card.dataset.rover = rover.carrierId; card.dataset.status = rover.status;
        const title = node('h5'); title.append(node('span', null, 'rover-swatch'), document.createTextNode(roverLabel(rover.carrierId)));
        card.append(title, node('p', roverStatus(rover)));
        card.append(node('p', `${causeName(rover.fault)}${rover.targetId ? ` · Target ${rover.targetId}` : ''}`, rover.fault !== 'nominal' ? 'fleet-fault-note' : ''));
        if (rover.guardian) card.append(node('p', `${riskText(rover.guardian)} · ${causeName(rover.guardian.predictedCause)}`, 'carrier-risk'));
        $('fleet-rovers').append(card);
        const key = node('button'); key.type = 'button'; key.style.setProperty('--rover-color', color); key.dataset.rover = rover.carrierId; key.dataset.status = rover.status; key.title = `Follow ${roverLabel(rover.carrierId)}`; key.append(node('i', null, 'rover-swatch'), document.createTextNode(`${roverLabel(rover.carrierId)} · ${roverStatus(rover)}`));
        key.addEventListener('click', () => terrain?.focusRover?.(rover.carrierId)); $('fleet-map-rovers').append(key);
        const summary = node('div'); summary.style.setProperty('--rover-color', color);
        const name = node('span'); name.append(node('i', null, 'rover-swatch'), document.createTextNode(roverLabel(rover.carrierId)));
        summary.append(name, node('span', roverStatus(rover))); $('fleet-summary-rovers').append(summary);
      });
      if (!state.rovers.length) $('fleet-rovers').append(node('p', 'No rovers assigned.', 'muted'));
      const events = [...new Map((Array.isArray(state.events) ? state.events : []).map(e => [e.id, e])).values()].sort((a, b) => (b.ts || 0) - (a.ts || 0)).slice(0, 12);
      $('fleet-events').replaceChildren();
      for (const event of events) {
        const item = node('li'); item.dataset.event = String(event.id);
        item.append(node('span', `${event.roverId || 'Fleet'}${event.targetId ? ` → ${event.targetId}` : ''} · ${String(event.type || 'event').replaceAll('_', ' ')}`, 'mono'), node('p', event.message || ''));
        if (number(event.ts)) { const time = node('time', new Date(event.ts * 1000).toLocaleTimeString()); time.dateTime = new Date(event.ts * 1000).toISOString(); item.append(time); }
        $('fleet-events').append(item);
      }
      if (!events.length) $('fleet-events').append(node('li', 'No fleet events recorded.', 'muted'));
    }
    updateFleetControls();
  }
  function renderFleetRecovery(state) {
    const pending = state.rovers.filter(r => r.recovery?.phase === 'awaiting_approval');
    $('fleet-approvals').hidden = !pending.length;
    const list = $('fleet-approval-list'), snapshot = JSON.stringify(pending.map(r => [r.carrierId, r.fault, r.recovery]));
    if (list.dataset.snapshot !== snapshot) {
      list.dataset.snapshot = snapshot; list.replaceChildren();
      for (const rover of pending) {
        const card = node('article', null, 'fleet-decision'); card.dataset.rover = rover.carrierId;
        card.append(node('h5', roverLabel(rover.carrierId)), node('p', causeName(rover.fault)));
        if (rover.recovery.held) card.append(node('p', 'Kept halted by Mission Control.', 'field-help'));
        const controls = node('div', null, 'fleet-controls');
        for (const [action, label] of [['approve_recovery', 'Approve recovery'], ['hold_recovery', 'Keep halted']]) {
          const b = node('button', label); b.type = 'button'; b.dataset.fleetDecision = action; b.dataset.held = String(rover.recovery.held === true);
          b.addEventListener('click', () => fleetAction(action, {roverId: rover.carrierId, requestId: rover.recovery.requestId})); controls.append(b);
        }
        card.append(controls); list.append(card);
      }
    }
    $('fleet-map-recovery').hidden = !pending.length;
    $('fleet-map-recovery').textContent = pending.length ? `Mission Control · ${pending.length} ${pending.length === 1 ? 'decision' : 'decisions'} in Guardian` : '';
    $('fleet-map-recovery').dataset.attention = String(pending.length > 0);
  }
  function fleetError(error) {
    if (error.status === 404) {
      fleetAvailable = false; $('fleet-message').textContent = 'Fleet demo is awaiting server support. Refresh fleet after the server update.';
    } else $('fleet-message').textContent = `Fleet update paused. ${error.message}`;
    updateFleetControls();
  }
  async function refreshFleet(force = false) {
    if (!token || fleetBusy || (fleetAvailable === false && !force)) return;
    const generation = epoch, request = ++fleetRequest;
    try {
      const data = await (await api(endpoints.fleet)).json();
      if (generation !== epoch || request !== fleetRequest) return;
      renderFleet(data); $('fleet-message').textContent = 'Synthetic survey · Guardian ML and planning coordinate the fleet.';
    } catch (e) { if (generation === epoch && request === fleetRequest) fleetError(e); }
  }
  function startFleetPolling() {
    clearTimeout(fleetPoll); const generation = epoch;
    const tick = async () => {
      if (!token || generation !== epoch) return;
      const started = Date.now();
      await refreshFleet();
      if (token && generation === epoch) fleetPoll = setTimeout(tick, Math.max(50, 1000 - (Date.now() - started)));
    };
    tick();
  }
  async function fleetAction(action, decision) {
    if (fleetBusy) return;
    const producer = $('producer-token').value.trim(), generation = epoch;
    if (!token || !producer) { $('fleet-message').textContent = 'Connect a viewer and enter the producer token in Guardian.'; return; }
    const payload = {action};
    if (action === 'start' || action === 'reset') {
      if (!$('fleet-speed').reportValidity()) return;
      const count = Number($('fleet-count').value), speedMultiplier = Number($('fleet-speed').value);
      if (!Number.isInteger(count) || count < 1 || count > 6 || !Number.isInteger(speedMultiplier) || speedMultiplier < 1 || speedMultiplier > 120) return;
      if (action === 'start' && count !== fleetState?.count && (fleetState?.elapsedS > 0 || fleetState?.rovers.some(r => r.guardian))) {
        $('fleet-message').textContent = 'Use Reset fleet to change rover count after survey activity.'; return;
      }
      Object.assign(payload, {count, speedMultiplier, autoRepair: $('fleet-auto-repair').checked});
    }
    if (action === 'configure') payload.autoRepair = $('fleet-auto-repair').checked;
    if (action === 'approve_recovery' || action === 'hold_recovery') {
      const rover = fleetState?.rovers.find(r => r.carrierId === decision?.roverId);
      if (rover?.recovery?.phase !== 'awaiting_approval' || rover.recovery.requestId !== decision?.requestId) return;
      Object.assign(payload, decision);
    }
    if (action === 'fault') {
      const roverId = $('fleet-target').value, fault = $('fleet-fault').value;
      if (!fleetState?.rovers.some(r => r.carrierId === roverId) || !fleetCauses.includes(fault)) return;
      Object.assign(payload, {roverId, fault});
    }
    fleetBusy = true; fleetRequest++; updateFleetControls(); $('fleet-message').textContent = 'Applying fleet command.';
    try {
      const data = await (await api(endpoints.fleet, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}, producer)).json();
      if (generation !== epoch) return;
      if (data.ok !== true) throw new Error('Fleet command was not acknowledged.');
      renderFleet(data.fleetState); $('fleet-message').textContent = 'Fleet command applied to the synthetic survey.';
      if (action === 'start') {
        terrain?.focusRover?.($('fleet-target').value || data.fleetState.rovers[0]?.carrierId);
        $('close-overlay').click();
      }
      refreshGuardian();
    } catch (e) {
      if (generation === epoch) { $('fleet-auto-repair').checked = fleetState?.autoRepair !== false; fleetError(e); }
    }
    finally { if (generation === epoch) { fleetBusy = false; updateFleetControls(); } }
  }
  $('refresh-fleet').addEventListener('click', () => refreshFleet(true));
  document.querySelectorAll('[data-fleet-action]').forEach(b => b.addEventListener('click', () => fleetAction(b.dataset.fleetAction)));
  $('fleet-inject').addEventListener('click', () => fleetAction('fault'));
  $('fleet-target').addEventListener('change', updateFleetControls);
  $('fleet-auto-repair').addEventListener('change', () => fleetAction('configure'));
  $('follow-rover').addEventListener('click', () => terrain?.focusRover?.($('fleet-target').value || fleetState?.rovers[0]?.carrierId));
  $('view-fleet').addEventListener('click', () => terrain?.focusFleet?.());
  function focusFleetAccess(panel, input) {
    const navigation = document.querySelector(`[data-panel="${panel}"]`);
    if (navigation.getAttribute('aria-expanded') !== 'true') navigation.click();
    $(input).focus();
  }
  $('fleet-connect-viewer').addEventListener('click', () => focusFleetAccess('equipment', 'viewer-token'));
  $('fleet-enter-producer').addEventListener('click', () => focusFleetAccess('guardian', 'producer-token'));
  updateFleetControls();
  function telemetrySummary(frame) {
    const t = frame.telemetry || {};
    return `Points ${metric(t.pointCount ?? t.point_count ?? frame.pointCount ?? frame.points?.length)} · Slip ${number(t.slipRatio ?? t.slip_ratio) ? metric((t.slipRatio ?? t.slip_ratio) * 100, 0, '%') : '—'} · Contrast ${metric(t.lumaContrast ?? t.luma_contrast, 2)} · Pose jump ${metric(t.poseJumpM ?? t.pose_jump_m, 2, ' m')}`;
  }
  function riskText(guardian) {
    if (!guardian) return 'Guardian awaiting telemetry';
    const level = riskLevel(guardian);
    return `${level[0].toUpperCase() + level.slice(1)} · ${number(guardian.riskScore) ? metric(guardian.riskScore * 100, 0, '%') : '—'}`;
  }
  function renderCarriers() {
    $('carrier-stage').replaceChildren();
    for (const frame of rooms.values()) {
      const card = node('article', null, 'carrier-card');
      card.dataset.carrier = carrierKey(frame); card.dataset.lowConfidence = String(frame.guardian?.lowConfidence === true);
      card.dataset.risk = riskLevel(frame.guardian);
      const badge = node('h2', null, 'carrier-badge'); badge.append(window.LabShell.icon(frame.carrierType === 'rover' ? 'truck' : 'radio'), document.createTextNode(carrierName(frame)));
      const inspect = node('button', 'Inspect', 'carrier-inspect'); inspect.type = 'button'; inspect.addEventListener('click', () => showScan(frame));
      card.append(badge, node('p', carrierKey(frame), 'carrier-id mono'), node('p', telemetrySummary(frame), 'mono'), node('p', riskText(frame.guardian), 'carrier-risk'), inspect);
      if (frame.guardian?.lowConfidence === true) card.append(node('p', 'Low confidence · Verify before driving.', 'confidence-warning'));
      $('carrier-stage').append(card);
    }
    if (!rooms.size) $('carrier-stage').append(node('p', 'Awaiting rover or mast telemetry.', 'muted'));
    renderRisk();
  }
  function renderRisk() {
    const frames = [...rooms.values()].filter(f => f.guardian);
    frames.sort((a, b) => (b.guardian.riskScore ?? -1) - (a.guardian.riskScore ?? -1) || (b.receivedAt ?? 0) - (a.receivedAt ?? 0));
    const frame = frames[0], g = frame?.guardian;
    $('guardian-risk').dataset.risk = riskLevel(g);
    $('guardian-level').textContent = g ? riskText(g).split(' · ')[0] : 'Awaiting telemetry';
    $('guardian-score').textContent = g && number(g.riskScore) ? metric(g.riskScore * 100, 0, '%') : '—';
    $('guardian-meter').hidden = !g || !number(g.riskScore); $('guardian-meter').value = number(g?.riskScore) ? Math.max(0, Math.min(1, g.riskScore)) : 0;
    $('guardian-carrier').textContent = frame ? `${carrierName(frame)} · ${carrierKey(frame)} · Highest live risk` : 'No current Guardian telemetry.';
    $('guardian-cause').textContent = causeName(g?.predictedCause); $('guardian-lead').textContent = metric(g?.leadTimeS, 1, ' s');
    $('guardian-frame-model').textContent = g?.modelVersion || '—';
    $('guardian-recovery').textContent = g?.recoveryAction || 'Recovery guidance appears with telemetry.';
    $('guardian-confidence').hidden = g?.lowConfidence !== true;
  }
  function resetValidation() {
    for (const id of ['guardian-model', 'guardian-caught', 'guardian-validation-lead', 'guardian-false-alarms', 'guardian-baseline-f1', 'guardian-retrained-f1', 'guardian-candidate']) $(id).textContent = '—';
    $('guardian-validation-note').textContent = 'No hold-out results loaded.';
    $('guardian-deploy-note').textContent = 'A validated candidate must be reviewed before deployment.';
  }
  function updateGuardianControls() {
    const permitted = Boolean(token && $('producer-token').value.trim()) && !guardianBusy;
    document.querySelectorAll('[data-sim-action], [data-sim-fault], #guardian-retrain, #incident-list button').forEach(b => { b.disabled = !permitted; });
    document.querySelectorAll('#incident-list select').forEach(select => { select.disabled = guardianBusy; });
    $('guardian-deploy').disabled = !permitted || !candidateReady;
    $('refresh-guardian').disabled = !token || guardianBusy;
    $('guardian-export').disabled = !token;
    updateFleetControls();
  }
  function renderValidation(status) {
    const current = status.currentMetrics;
    const baseline = status.baselineMetrics;
    const candidate = status.candidateMetrics;
    candidateVersion = status.candidateVersion || null;
    candidateReady = status.candidateReady === true && Boolean(candidateVersion && candidate && number(candidate.F1));
    $('guardian-model').textContent = status.modelVersion || '—';
    $('guardian-caught').textContent = current ? `${metric(current.caughtFailures)} / ${metric(current.totalFailures)}` : '—';
    $('guardian-validation-lead').textContent = metric(current?.meanLeadTimeS, 1, ' s');
    $('guardian-false-alarms').textContent = metric(current?.falseAlarms);
    $('guardian-baseline-f1').textContent = number(baseline?.F1) ? metric(baseline.F1 * 100, 1, '%') : '—';
    $('guardian-retrained-f1').textContent = number(candidate?.F1) ? metric(candidate.F1 * 100, 1, '%') : '—';
    $('guardian-candidate').textContent = candidate ? candidateVersion || (candidateReady ? 'Ready for review' : 'Validation gate not met') : '—';
    $('guardian-validation-note').textContent = current ? `Synthetic chassis and optics on disjoint HiRISE hold-out trajectories. False alarms count nominal windows. ${metric(current.evaluatedWindows)} windows evaluated.` : 'No hold-out results loaded.';
    $('guardian-deploy-note').textContent = candidate ? `Review ${candidateVersion || 'candidate'}: ${metric(candidate.caughtFailures)} / ${metric(candidate.totalFailures)} faults caught, ${metric(candidate.meanLeadTimeS, 1, ' s')} mean lead, ${metric(candidate.falseAlarms)} false alarms. ${candidateReady ? 'Approve only after reviewing the hold-out results.' : 'Validation gate not met; deployment is blocked.'}` : 'A validated candidate must be reviewed before deployment.';
    updateGuardianControls();
  }
  function renderSimulator(sim) {
    if (!sim) return;
    $('sim-status').textContent = `${sim.running ? 'Running' : 'Stopped'} · ${causeName(sim.fault)} · ${metric(sim.steps)} steps${sim.error ? ' · Simulator interrupted; check server diagnostics.' : ''}`;
    document.querySelectorAll('[data-sim-fault]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.simFault === sim.fault)));
  }
  function renderIncidents(incidents) {
    const snapshot = JSON.stringify(incidents);
    if (snapshot === incidentSnapshot) { updateGuardianControls(); return; }
    incidentSnapshot = snapshot;
    const present = new Set(incidents.map(i => i.id));
    for (const id of incidentDrafts.keys()) if (!present.has(id)) incidentDrafts.delete(id);
    $('incident-list').replaceChildren();
    for (const incident of incidents) {
      const card = node('article', null, 'card incident-card');
      card.append(node('h3', `${incident.carrierId || incident.room || 'Carrier'} · Incident ${incident.id}`), node('p', `${causeName(incident.predictedCause)} · ${date(incident.createdAt)}`), node('p', incident.status || 'pending', 'incident-status'));
      const select = node('select'); select.id = `incident-cause-${incident.id}`;
      const label = node('label', 'Verified cause'); label.htmlFor = select.id;
      const empty = node('option', 'Select a verified cause'); empty.value = ''; select.append(empty);
      for (const cause of causes) { const option = node('option', causeName(cause)); option.value = cause; select.append(option); }
      select.value = incidentDrafts.get(incident.id) ?? (causes.includes(incident.trueCause) ? incident.trueCause : '');
      const save = button('Save label', 'shield-check', () => {
        if (!select.value) { select.setCustomValidity('Select the observed cause first.'); select.reportValidity(); return; }
        return guardianAction(endpoints.label(incident.id), {trueCause: select.value}, incident.id);
      });
      select.addEventListener('change', () => { select.setCustomValidity(''); incidentDrafts.set(incident.id, select.value); });
      // Keep unverified predictions separate from an operator's label.
      card.append(label, select, save); $('incident-list').append(card);
    }
    if (!incidents.length) $('incident-list').append(node('p', 'No incidents recorded.', 'muted'));
    updateGuardianControls();
  }
  async function refreshGuardian() {
    if (!token) return;
    const generation = epoch, request = ++guardianRequest;
    try {
      const [status, incidents] = await Promise.all([
        api(endpoints.guardianStatus).then(r => r.json()), api(endpoints.incidents).then(r => r.json())
      ]);
      if (generation !== epoch || request !== guardianRequest) return;
      renderValidation(status); renderIncidents(incidents.incidents); renderSimulator(status.simState);
      $('guardian-message').textContent = 'Guardian updated. Review incident labels and hold-out results.';
    } catch (e) {
      if (generation !== epoch || request !== guardianRequest) return;
      candidateReady = false; updateGuardianControls(); $('guardian-message').textContent = e.message;
    }
  }
  async function guardianAction(path, payload, incidentId = null) {
    if (guardianBusy) return;
    const producer = $('producer-token').value.trim(), generation = epoch;
    if (!token || !producer) { $('guardian-message').textContent = 'Connect a viewer and enter a producer token in Guardian.'; return; }
    guardianBusy = true; guardianRequest++; updateGuardianControls();
    $('guardian-message').textContent = 'Processing operator request.';
    try {
      const result = await (await api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}, producer)).json();
      if (generation !== epoch) return;
      if (incidentId !== null) incidentDrafts.delete(incidentId);
      if (result.candidateVersion) candidateVersion = result.candidateVersion;
      if (result.latestFrame) accept(result.latestFrame);
      if (result.simState) renderSimulator(result.simState);
      await refreshGuardian();
    } catch (e) {
      if (generation === epoch) { candidateReady = false; $('guardian-message').textContent = e.message; }
    } finally {
      if (generation === epoch) { guardianBusy = false; updateGuardianControls(); }
    }
  }
  $('producer-token').addEventListener('input', updateGuardianControls);
  $('refresh-guardian').addEventListener('click', refreshGuardian);
  $('guardian-export').addEventListener('click', async () => {
    const generation = epoch;
    try { await download(endpoints.guardianModel, 'arescope-guardian-model.json'); }
    catch (e) { if (generation === epoch) $('guardian-message').textContent = e.message; }
  });
  $('guardian-retrain').addEventListener('click', () => guardianAction(endpoints.retrain, {}));
  $('guardian-deploy').addEventListener('click', () => { if (candidateReady) guardianAction(endpoints.deploy, {approved: true, candidateVersion}); });
  document.querySelectorAll('[data-sim-action]').forEach(b => b.addEventListener('click', () => guardianAction(endpoints.simulator, {action: b.dataset.simAction})));
  document.querySelectorAll('[data-sim-fault]').forEach(b => {
    b.setAttribute('aria-pressed', 'false');
    b.addEventListener('click', () => guardianAction(endpoints.simulator, {action: 'fault', fault: b.dataset.simFault}));
  });
  updateGuardianControls();
  function renderRooms() {
    $('rooms').replaceChildren();
    for (const [room, frame] of rooms) {
      const card = node('article', null, 'card'); card.append(node('h3', `${carrierName(frame)} · ${room}`), node('p', telemetrySummary(frame)), node('p', date(frame.receivedAt)), button('Inspect scan', 'eye', () => showScan(frame))); $('rooms').append(card);
    }
    if (!rooms.size) $('rooms').append(node('p', 'Awaiting a carrier scan.', 'muted'));
    renderCarriers();
  }
  function accept(message) {
    if (message.type === 'guardian_update') { if (!guardianBusy) refreshGuardian(); return; }
    if (Array.isArray(message.rooms)) {
      rooms.clear(); message.rooms.forEach(f => rooms.set(carrierKey(f), f));
      // Keep an explicitly inspected fleet rover current; new fleet frames never open a scan window.
      const inspected = activeScan && fleetFrame(activeScan) ? message.rooms.find(f => carrierKey(f) === carrierKey(activeScan)) : null;
      const automatic = inspected || [...message.rooms].reverse().find(f => !fleetFrame(f));
      if (automatic && !archived(activeScan || {})) showScan(automatic);
      else if (!message.rooms.length && activeScan && !archived(activeScan)) { activeScan = null; $('live-overlay').hidden = true; }
    }
    else if (Array.isArray(message.points) && !archived(message)) {
      rooms.set(carrierKey(message), message);
      if (!archived(activeScan || {}) && (!fleetFrame(message) || (activeScan && carrierKey(activeScan) === carrierKey(message)))) showScan(message);
      $('live-message').textContent = `Receiving scans from ${carrierKey(message)}.`;
    } else return;
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
      clearInterval(poll); poll = null; state('Viewer connected', true); $('live-message').textContent = 'Live feed connected. Waiting for carrier scans.';
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
    resetFleet();
    rooms.clear(); activeScan = null; renderRooms(); $('live-overlay').hidden = true;
    guardianRequest++; guardianBusy = false; candidateReady = false; candidateVersion = null; incidentSnapshot = ''; incidentDrafts.clear(); resetValidation();
    $('incident-list').replaceChildren(node('p', 'Connect a viewer to load incidents.', 'muted'));
    $('guardian-message').textContent = 'Awaiting viewer connection.'; $('sim-status').textContent = 'Simulator state unknown.';
    $('viewer-token').value = ''; $('producer-token').value = ''; $('disconnect').hidden = true;
    document.querySelectorAll('[data-sim-fault]').forEach(b => b.setAttribute('aria-pressed', 'false')); updateGuardianControls();
    $('session-list').replaceChildren(node('p', 'Connect a viewer to load sessions.', 'muted'));
    $('log-list').replaceChildren(node('p', 'Connect a viewer to load logs.', 'muted')); $('log-preview').hidden = true; $('log-preview').textContent = '';
    $('session-message').textContent = ''; $('log-message').textContent = '';
    $('storage-stats').replaceChildren(node('p', 'Connect to inspect storage.', 'muted'));
    state('Ready to connect'); $('live-message').textContent = 'Viewer disconnected.';
  }
  $('connect-form').addEventListener('submit', async e => {
    e.preventDefault(); const value = $('viewer-token').value.trim(); if (!value) return;
    disconnect(); token = value; const generation = epoch; $('live-message').textContent = 'Checking viewer access.';
    try {
      const r = await api(endpoints.latest), data = await r.json(); if (generation !== epoch) return;
      accept(data); $('disconnect').hidden = false; updateGuardianControls(); openSocket(generation); startFleetPolling();
      await Promise.allSettled([refreshSessions(), refreshLogs(), refreshStats(), refreshGuardian()]);
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
        actions.append(button('Inspect', 'eye', async () => { const data = await (await api(endpoints.session(s.id))).json(); if (generation !== epoch) return; if (data.frame) showScan(data.frame); else $('session-message').textContent = 'This session has no stored frames.'; }),
          button('Merged PLY', 'download', () => download(endpoints.ply(s.id, 'merged'), `arescope-${s.id}-merged.ply`)),
          button('Last PLY', 'download', () => download(endpoints.ply(s.id, 'last'), `arescope-${s.id}-last.ply`)));
        if (s.hasMesh) actions.append(button('ARSM mesh', 'download', () => download(endpoints.mesh(s.id), `${s.id}.arsm`)));
        const remove = button('Delete', 'trash', async () => {
          if (remove.dataset.confirm !== 'yes') { remove.dataset.confirm = 'yes'; remove.lastChild.textContent = 'Confirm delete'; $('session-message').textContent = 'Enter a producer token in Guardian, then select Confirm delete to remove this session.'; return; }
          const producer = $('producer-token').value.trim(); $('producer-token').value = ''; updateGuardianControls();
          if (!producer) { $('session-message').textContent = 'Enter a producer token in Guardian to remove a session.'; document.querySelector('[data-panel="guardian"]').click(); $('producer-token').focus(); return; }
          await api(endpoints.session(s.id), {method: 'DELETE'}, producer); if (generation !== epoch) return; await refreshSessions(); await refreshStats();
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
        actions.append(button('Read log', 'eye', async () => { const text = await (await api(endpoints.log(log.file))).text(); if (generation !== epoch) return; $('log-preview').textContent = text; $('log-preview').hidden = false; }), button('Download', 'download', () => download(endpoints.log(log.file), log.file)));
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
  document.addEventListener('panelchange', e => { if (token) { if (e.detail === 'sessions') refreshSessions(); if (e.detail === 'logs') refreshLogs(); if (e.detail === 'equipment') refreshStats(); if (e.detail === 'guardian') refreshGuardian(); } });

  function drawScan() {
    if (!activeScan) return;
    const canvas = $('scan'), ctx = canvas.getContext('2d'), dpr = Math.min(devicePixelRatio || 1, 2);
    const w = canvas.clientWidth, h = canvas.clientHeight; canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
    const pts = activeScan.points; if (!pts.length) return;
    const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
    for (const p of pts) p.forEach((v, k) => { low[k] = Math.min(low[k], v); high[k] = Math.max(high[k], v); });
    const center = low.map((v, k) => (v + high[k]) / 2), extent = Math.max(1, ...low.map((v, k) => high[k] - v)), scale = Math.min(w, h) / extent * .58;
    ctx.fillStyle = activeScan.guardian?.lowConfidence === true ? '#f0a39a' : '#ee8a5b';
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
    $('overlay-title').textContent = `${carrierName(frame)} ${archived(frame) ? 'archive' : frame.source === 'simulated-rover' ? 'simulation' : 'live'}`;
    $('live-overlay').dataset.lowConfidence = String(frame.guardian?.lowConfidence === true); $('live-overlay').dataset.risk = riskLevel(frame.guardian);
    $('scan-confidence').hidden = frame.guardian?.lowConfidence !== true;
    $('scan-caption').textContent = `${carrierKey(frame)} · ${frame.points.length} points · Local metres${frame.points.length ? '' : ' · No scan points'}${frame.source === 'simulated-rover' ? ' · Synthetic rover on HiRISE archive' : ''}`;
    $('scan-telemetry').textContent = telemetrySummary(frame);
    $('scan-guardian').textContent = `${riskText(frame.guardian)}${frame.guardian ? ` · ${causeName(frame.guardian.predictedCause)} · ${metric(frame.guardian.leadTimeS, 1, ' s')} lead · ${frame.guardian.recoveryAction || 'Awaiting recovery guidance'}` : ''}`;
    drawScan();
  }
  $('close-overlay').addEventListener('click', () => { $('show-live').checked = false; $('live-overlay').hidden = true; });
  $('show-live').addEventListener('change', () => { $('live-overlay').hidden = !$('show-live').checked || !activeScan; drawScan(); });
  new ResizeObserver(drawScan).observe($('scan'));
  setInterval(() => {
    const now = Date.now() / 1000;
    let changed = false;
    for (const [room, frame] of rooms) if (now - frame.receivedAt > 30) { rooms.delete(room); changed = true; }
    if (activeScan && !archived(activeScan) && now - activeScan.receivedAt > 30) { activeScan = null; $('live-overlay').hidden = true; }
    if (changed) renderRooms();
  }, 2000);
  setInterval(() => { if (token) { refreshStats(); if (!guardianBusy && !$('guardian').hidden) refreshGuardian(); } }, 15000);
})();
