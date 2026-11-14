# Live ingest server (LAB): contract, history, guards, verification

The web side of the Quest live feed. The HUD/minimap half lives in
`references/live-scan-feed.md`; this file is the FastAPI service in
`/root/Developer/arescope-lab/app.py` and how to prove each part works.

## Endpoint contract

| Route | Token | Purpose |
|---|---|---|
| `POST /api/live/frame` | producer | one decimated frame, `{room, yawDeg, points}`, ≤4096 points |
| `GET /api/live/latest` | viewer | newest frame per room |
| `WS /api/live/stream?token=` | viewer | snapshot on connect, then every new frame, 20 s ping |
| `GET /api/live/sessions?limit=` | viewer | session list, newest first |
| `GET /api/live/sessions/{id}` | viewer | metadata + **last** frame, `source: archived-quest` |
| `DELETE /api/live/sessions/{id}` | producer | drop one session |
| `GET /api/live/sessions/{id}/export.ply?frame=merged\|last` | viewer | ASCII PLY download |
| `GET /api/live/stats` | viewer | DB size, session/frame counts, ingest counters, active limits |

`POST` answers with `{ok, pointCount, viewers, sessionId, stored, throttled}` so a
device can tell "accepted" from "accepted but not persisted".

## Design rules that keep it honest

- **A storage failure must never break the live path.** Wrap the DB write in
  `try/except`, increment a `storage_errors` counter, and still broadcast the frame.
  A full disk or a locked DB should degrade the archive, not blank the viewer.
- **Throttle the history write, not the frame.** Frames arriving faster than
  `ARESCOPE_MIN_HISTORY_INTERVAL` are still broadcast and still update
  `LIVE_FRAMES`; only the append is skipped and the response says `throttled: true`.
- **Cap the session, keep the identity.** Past `ARESCOPE_MAX_FRAMES_PER_SESSION`
  stop appending but keep returning the same `sessionId` and keep refreshing the
  in-memory `(sessionId, last_frame_at)` entry, otherwise a 60 s gap opens a new
  session that immediately hits the cap again and the panel shows a stream of
  empty ones.
- **Session continuity is in-memory state with a DB check.** Re-validate that the
  row still exists before appending: a `DELETE` leaves the pointer dangling and
  the next insert fails on the foreign key.
- **Prune on write, at most hourly, on both axes.** Age
  (`ARESCOPE_RETENTION_DAYS`) and total payload bytes (`ARESCOPE_MAX_DB_BYTES`),
  deleting oldest sessions until it fits. Keep the frame payload gzipped — a
  3-minute scan at 384 points every 3 s is ~0.2 MB compressed, so size is never
  the reason to skip history.
- **Export deduplicates.** `frame=merged` collapses identical vertices across all
  frames at 1 cm and caps the total; snapshots repeat every point, so a naive
  merge produces the same cloud several times over.
- **Never put a bearer token in a download URL.** The panel fetches the PLY with
  the `Authorization` header and turns the response into a Blob download, so the
  credential stays out of the URL, the access log and browser history.
- Point clouds of a real room are personal data: state the retention window in the
  reply, keep the DB outside the repo and outside `static/`, and give the producer
  a delete route.

## Verifying

- **Unit (`pytest`)**: reload the app module under `mock.patch.dict(os.environ)`
  with a temp `ARESCOPE_LIVE_DB` so tests never touch production history; set
  `ARESCOPE_MIN_HISTORY_INTERVAL=0` for tests about session joining and a large
  value for tests about throttling. Cover: frames joining one session, gap opening
  a new one, cap, stats, PLY header/body, 401 for the wrong token, 404 for an
  unknown id.
- **Public origin, throttle**: send the burst on ONE keep-alive connection
  (`http.client.HTTPSConnection`, reuse the socket). A fresh TLS handshake per
  request takes longer than a 0.25 s window, so three sequential `urllib` calls all
  come back `stored: true` and a perfectly good guard looks broken.
- **Public origin, PLY**: assert `ply\nformat ascii 1.0\n`, `element vertex N`, a
  `Content-Disposition` attachment, and that the body after `end_header` has N
  lines with the expected coordinates.
- **Browser**: open the panel in a cache-disabled session and check the history
  block renders inside the drawer with `scrollWidth - clientWidth == 0`.
