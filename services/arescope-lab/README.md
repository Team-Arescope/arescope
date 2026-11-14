# Arescope LAB

FastAPI live ingest, SQLite scan history and a static Mission Control UI.
Run **one worker** on **127.0.0.1:18965**: live rooms, subscriber queues and
session continuity belong to that process. No external frontend build or CDN is
needed. Python 3.10+ and Node 18+ are required; this implementation was verified
with Python 3.12 and Node 24.

## Run locally

From this directory on Windows:

```powershell
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`: supply two independently generated, distinct tokens, and choose
writable paths for the database, meshes and logs. For a local checkout, keep all
three beneath `.runtime/`; for the Linux service use the template's `/var/lib`
paths. The example deliberately contains empty token values. Never commit `.env`.

```powershell
.venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port 18965 --workers 1 --env-file .env --no-access-log
```

Open [Mission Control](http://127.0.0.1:18965/). Open Equipment and live, paste
the **viewer** token and connect. Viewer credentials stay in page memory.
The producer token is needed only by the device and for a session deletion.
The deletion field is cleared after each use, including its confirmation step.
Disconnect clears room, session and log views and closes the stream.

`python app.py --check-config` validates exported environment variables without
printing token values. Startup performs the same validation; missing, blank or
identical tokens fail startup. Auth handlers also fail closed independently.

## Contract

All HTTP live endpoints require `Authorization: Bearer <role token>`.
**P** means producer; **V** means viewer. Tokens are compared with
`hmac.compare_digest`. The public surface is limited to `/healthz`, `/` and
the static assets. Framework documentation UIs are disabled.

| Method | Route | Role | Behavior |
| --- | --- | --- | --- |
| GET | `/healthz` | Public | Process liveness; does not claim storage health |
| GET | `/` | Public | Static Mission Control |
| POST | `/api/live/frame` | P | Up to 4096 finite xyz points; optional room/yaw |
| GET | `/api/live/latest` | V | Latest frame per room, 30-second TTL |
| WS | `/api/live/stream?token=…` | V | Snapshot, frames, 20-second idle pings |
| GET | `/api/live/sessions?limit=20` | V | Newest sessions; limit 1–100 |
| GET | `/api/live/sessions/{id}` | V | Summary and last archived frame |
| DELETE | `/api/live/sessions/{id}` | P | Remove session, cascaded frames and its mesh |
| GET | `/api/live/stats` | V | Storage, counts, limits, counters and active rooms |
| GET | `/api/live/sessions/{id}/export.ply?frame=merged\|last` | V | ASCII PLY, at most 400,000 points |
| POST | `/api/live/mesh?session={id}` | P | Strict ARSM v1/v2 validation; 32 MiB default |
| GET | `/api/live/sessions/{id}/mesh` | V | Original ARSM bytes |
| POST | `/api/live/log?source=device` | P | Nonempty UTF-8 log; 8 MiB default |
| GET | `/api/live/logs?limit=20` | V | Newest log files; limit 1–200 |
| GET | `/api/live/logs/{filename}` | V | Basename-validated text; no-store |

Browser WebSockets use the query token required by the contract; browsers cannot
set their own Authorization header on that handshake. Downloads use authenticated
fetch plus Blob URLs, and never include credentials in URLs. The application
redacts stream queries from Uvicorn logs; the nginx template suppresses stream
access/error request logging. Unauthorized sockets close with **4401**, including
real browser connections. No scan snapshot is sent to an unauthorized socket.

The live frame is published **before** history persistence. SQLite lock, disk and
schema errors increment `storage_errors` and return `stored:false`; live delivery
continues. Read-side storage failures return a generic 503. `/healthz` remains a
liveness check. `sessionId` is null when persistence could not establish an ID.

History splits after a 60-second ingest gap. The 0.25-second guard throttles
persistence; it does not throttle live delivery. A session stops growing at
2000 stored frames while accepted frames keep its in-memory identity alive.
Each append rechecks the referenced session row, including after pruning or
external deletion. A process restart starts new continuity caches.

Frame arrays are compact JSON compressed with gzip level 6. Foreign-key cascade
is enabled on every connection. Pruning runs on frame writes at most hourly:
remove sessions started more than 7 days ago, then remove oldest sessions until
compressed payload bytes are at most 209,715,200. These limits are configurable
in `.env.example`. The payload cap is distinct from physical SQLite allocation
and does not include mesh/log storage. Logs use sanitized UTC filenames;
same-second uploads get successive unused timestamps to prevent overwrites.

ARSM parsing checks exact lengths, versions, counts, every triangle index and
the 24 MiB v2 PNG cap. Upload bodies are bounded while streaming, even without
Content-Length. PLY merged exports deduplicate rounded xyz coordinates at 1 cm.

## Mission Control

The stage is an HTML5 Canvas WebGL renderer with a filled depth pass and
Polygonal Grid / Minimal Grid modes. Drag to orbit, scroll to zoom, or use arrow
keys and R when the canvas is focused. Local HiRISE detail is the initial view;
Settings also offers the MOLA regional view and elevation scale.

The NASA terrain fixtures retain their product metadata and source coordinates.
Quest live and archived room frames render in a separate local-metre point-cloud
overlay. An archived inspection remains selected until another scan is selected.
Live rooms expire after 30 seconds. See
[terrain provenance](static/docs/terrain-sources.md).

The four drawer panes are 350 px wide on desktop and become a scrollable sheet
on phones. Both fonts are local WOFF2 files. Icons are inline Lucide SVGs.

## Deployment templates

These files are deployment templates. The current production layout and verified
rollout are recorded in [V2 deployment](../../docs/V2_DEPLOYMENT.md).

1. On a Linux host, create a system account named `arescope-lab`. Install this
   service directory at `/opt/arescope-lab` and create its `.venv` there.
2. Install dependencies and create `/etc/arescope-lab.env` with ownership and
   permissions allowing only the service administrator to read it (0600).
   Use the default `/var/lib/arescope-lab` storage paths. systemd creates that
   directory with mode 0700 for the service account.
3. Install `deploy/arescope-lab.service` under `/etc/systemd/system/`, reload
   systemd and start the service. Its config check rejects missing or equal tokens.
4. Customize the domain and TLS certificate paths in
   `deploy/nginx-arescope.conf.example`, include it in nginx's HTTP context,
   validate with `nginx -t`, and reload nginx. Uvicorn stays on loopback.
5. Verify health, producer ingest, viewer latest/history, an actual WebSocket
   upgrade, and PLY/mesh/log downloads through TLS using separately supplied
   credentials. Retain the one-worker configuration.

Back up SQLite through its online backup API or while the service is stopped;
include meshes and logs separately. Protect any environment-file backup and
test restoration. Set an operator-controlled retention policy for logs and
orphaned mesh files: automatic session pruning governs point history only.
Changing storage paths in production also requires updating the service's
`ReadWritePaths` allowance.

## Verification

See [recorded test results](tests/QA.md) for the completed implementation run.

All automated fixtures use dummy credentials and isolated storage beneath this
directory. No test contacts a deployed API. The optional terrain source audit
only reads public NASA PDS products.

```powershell
.venv/Scripts/python.exe -B -m pytest -q
node --test tests/mission_control.test.cjs
npm ci --ignore-scripts --no-audit --no-fund --cache .npm-cache
npm run test:browser
.venv/Scripts/python.exe -B tools/verify_terrain.py
```

The browser runner launches a temporary loopback QA service at port 18965 and
uses installed Chrome by default on Windows. Set `ARESCOPE_BROWSER_PATH` to a
Chromium executable on another installation, and `ARESCOPE_PYTHON` if needed.
Use a free port 18965 before running it. Profiles, downloads, databases and
screenshots remain in `.runtime/` and `tests/artifacts/` under this directory.
On Linux, install Playwright Chromium inside this directory by setting
`PLAYWRIGHT_BROWSERS_PATH` to a local `.runtime/browsers` path before installation
and running the browser test.

- Python: UT-04 ARSM; UT-05 retention/cascade and the actual 2000-frame cap;
  IT-01–IT-06; role isolation; empty config; latest TTL; stream snapshots,
  real 4401 closes, queue overflow and idle pings; simulated failures and an
  actual SQLite exclusive lock; streamed size limits and served assets.
- Node: static references, route parity, stale-copy audit, script parsing,
  fixture shape/coordinates, layout constraints and download authentication.
- Browser: real live push, 4401 denial, font/asset loads, PLY/ARSM downloads,
  log inspection, both terrain sources and grid modes, and numeric overflow
  checks across all panes at 1440 × 900 and 390 × 844.
- Terrain audit: all 4225 MOLA and 16,641 HiRISE heights matched the primary
  source ranges and their SHA-256 checksums during implementation.

## Created file manifest

Every path below is relative to this directory,
`C:\Users\Timur\Desktop\arescope-project\services\arescope-lab\`.

```text
app.py
arsm.py
requirements.txt
.env.example
.gitignore
README.md
pytest.ini
package.json
package-lock.json
deploy/arescope-lab.service
deploy/nginx-arescope.conf.example
static/index.html
static/shell.js
static/app.js
static/style.css
static/mission.css
static/favicon.svg
static/data/mola-gale.json
static/data/hirise-gale.json
static/docs/terrain-sources.md
static/docs/lucide-license.txt
static/fonts/manrope.woff2
static/fonts/dm-mono.woff2
static/fonts/Manrope-OFL.txt
static/fonts/DMMono-OFL.txt
tests/test_lab_api.py
tests/conftest.py
tests/QA.md
tests/mission_control.test.cjs
tests/mission_control.browser.cjs
tools/browser_server.py
tools/verify_terrain.py
```

Generated, ignored QA artifacts include `tests/artifacts/browser-report.json`,
`tests/artifacts/mission-1440.png`, `tests/artifacts/mission-390.png`,
`tests/artifacts/mission-terrain.png`, plus the fixture PLY/ARSM downloads.
Local dependency and runtime directories are ignored as well.
