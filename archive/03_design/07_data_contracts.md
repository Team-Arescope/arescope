# 07 · Контракты данных и API

Сокращения: `P` = producer bearer token, `V` = viewer bearer token, `C` = Copilot device/panel bearer according to service route. Точные секреты не включены. Каждая строка таблицы ниже описывает локальный source contract и считается `[ПРОВЕРЕНО]`, кроме строк, где статус помечен отдельно; production drift выделен явно. [ПРОВЕРЕНО: server source patterns]

| HTTP-метод/путь | Авторизация | Запрос | Успех | Ошибки/лимиты |
|---|---|---|---|---|
| `POST /api/live/frame` | P | JSON `{room?,yawDeg?,points:[[x,y,z],...]}` | `{ok,room,pointCount,viewers,sessionId,stored,throttled}` | 401; 422 invalid JSON/points >4096; history storage errors are caught and live feed still updates |
| `GET /api/live/latest` | V | none | `{source:"live-quest",rooms:[latest frame per room]}` | 401 |
| `WS /api/live/stream?token=<viewer>` | V query token | no JSON handshake body | sends latest snapshot on connect, then frame JSON; sends ping JSON after 20 s idle; queue max 32 drops oldest item on overflow | closes 4401 unauthorized; [ПРОВЕРЕНО: `app.py` WebSocket route] |
| `GET /api/live/sessions?limit=20` | V | limit clamped 1..100 | `{sessions,total,storedBytes,retentionDays,maxBytes}` | 401 |
| `GET /api/live/sessions/{id}` | V | integer id | `{session:summary,frame:last or null}`; frame source `archived-quest` | 401, 404 |
| `DELETE /api/live/sessions/{id}` | P | integer id | `{ok:true,deleted:id}` | 401, 404 |
| `GET /api/live/stats` | V | none | counts, payload bytes, retention/rate limits, counters, rooms | 401 |
| `GET /api/live/sessions/{id}/export.ply?frame=merged\|last` | V | frame enum | ASCII PLY body, octet-stream, max 400,000 points; merged dedup at 1 cm rounded cell | 401, 404, 422 invalid frame |
| `POST /api/live/mesh?session={id}` | P | ARSM binary body | JSON response (exact success fields require rereading tail of handler) | 401, 413 >32 MiB, 422 malformed header/count/size; 404 session absent |
| `GET /api/live/sessions/{id}/mesh` | V | integer id | ARSM body, octet-stream | 401, 404 |
| `POST /api/live/log?source=device\|pause\|combo\|crash-recovery` | P | UTF-8 text body | `{ok,file,bytes}` | 401, 413 >8 MiB, 422 empty |
| `GET /api/live/logs?limit=20` | V | limit clamped 1..200 | `{logs:[{file,bytes,at}]}` | 401 |
| `GET /api/live/logs/{filename}` | V | filename basename | text/plain; no-store | 401, 404 |
| `GET /api/copilot/settings` | C | none | version + settings + persistence/device applied | auth error; exact schema in Copilot source |
| `PUT /api/copilot/settings` | panel bearer | `{version,settings}` | incremented version/settings | 401/422/409 version conflict |
| `POST /api/copilot/settings/ack` | device bearer | `{version}` | ack status | 401/422/409 |
| `GET /api/copilot/status` | panel bearer | none | router configured, voice profiles, features `llm/asr/tts` in post-SDM state | 401; live status response must be hash-verified against current deployment |
| `POST /api/copilot/transcribe` | device/either | raw audio | `{text,model}` | 415 unsupported media; 413 >8 MiB; 400 empty; 502 upstream failure |
| `POST /api/copilot/chat` | device/either | `{text,context?}` | `text` SSE deltas then `complete` | 413 >32 KiB body; text max 12,000 chars; 401/402/403 provider failures mapped to stream error |
| `POST /api/copilot/speech` | device/either | `{text,voice}` | audio/mpeg | 422 invalid; response cap 8 MiB; 502 upstream failure |
| `/api/copilot/decision` | none | none | expected 404 in post-SDM deployment | [ПРОВЕРЕНО: previous live probe returned 404; deployment drift must be checked]

[ПРОВЕРЕНО: local source `/root/Developer/arescope-lab/app.py`, `/root/Developer/arescope-beta02-core/app.py`; endpoint-specific production snapshot is not version-hashed]

## SQLite schema

```text
sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room TEXT NOT NULL,
  started_at REAL NOT NULL,
  ended_at REAL NOT NULL,
  frame_count INTEGER NOT NULL DEFAULT 0,
  max_points INTEGER NOT NULL DEFAULT 0,
  has_mesh INTEGER NOT NULL DEFAULT 0,
  mesh_bytes INTEGER NOT NULL DEFAULT 0
)
frames(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  received_at REAL NOT NULL,
  yaw REAL,
  point_count INTEGER NOT NULL,
  payload BLOB NOT NULL
)
```

- Indexes: `(session_id, received_at)` and `sessions.started_at DESC`. [ПРОВЕРЕНО: `_ensure_schema`]
- Point payload stored as gzip(level 6) of compact JSON arrays. [ПРОВЕРЕНО]
- Foreign key cascade enabled on DB connections. [ПРОВЕРЕНО]
- DB default location: `/var/lib/arescope-lab/live.sqlite3` via service configuration/context; code env `ARESCOPE_LIVE_DB` should be verified against current source. [ПРЕДПОЛОЖЕНИЕ: historical deployment path]; [ТРЕБУЕТ ПРОВЕРКИ]

## ARSM binary mesh format

Header is little-endian, 16 bytes: `magic[4]="ARSM"`, `uint32 version`, `uint32 vertexCount`, `uint32 indexCount`. [ПРОВЕРЕНО: `MeshUploader.cs`, server parser]

### Version 1

```text
offset 0      4 bytes  magic "ARSM"
offset 4      u32      version = 1
offset 8      u32      vertexCount
offset 12     u32      indexCount
offset 16     vertexCount * 12 bytes  float32 xyz
then          vertexCount * 4 bytes   RGBA uint8
then          indexCount * 4 bytes    uint32 indices
```

Expected bytes: `16 + vertexCount*16 + indexCount*4`. [ПРОВЕРЕНО]

### Version 2

```text
v1 header + positions + RGBA + indices
then vertexCount * 8 bytes float32 UV pairs
then u32 atlasWidth, u32 atlasHeight, u32 pngLength
then pngLength PNG bytes
```

Expected bytes: `16 + v*16 + i*4 + v*8 + 12 + pngLength`; PNG max 24 MiB, total request max 32 MiB. [ПРОВЕРЕНО]

- Server allows 1 ≤ vertexCount ≤ 2,000,000 and requires `indexCount % 3 == 0`; full index range validation and all mesh file error branches must be audited before reimplementation. [ПРОВЕРЕНО/ТРЕБУЕТ ПРОВЕРКИ]

## PLY export

- ASCII PLY 1.0 with float x/y/z, one vertex per point. [ПРОВЕРЕНО]
- `frame=last` exports most recent frame; `frame=merged` merges frames, deduplicating coordinates rounded to 0.01 m; max 400,000 points. [ПРОВЕРЕНО]

## File naming and retention

- Device logs: UTC name `YYYYMMDD-HHMMSS-<sanitized-source>.log`, source chars `[A-Za-z0-9_-]` up to 40. [ПРОВЕРЕНО]
- Retention is session based: delete sessions older than 7 days; prune oldest while compressed point payload sum exceeds 200 MiB; pruning checks at most every 3600 s. [ПРОВЕРЕНО: server defaults/code]
- Max frames/session 2000; session gap 60 seconds; min persistence interval 0.25 seconds. [ПРОВЕРЕНО]
- Mesh files named by session id with `.arsm` suffix in mesh directory; actual absolute directory path requires environment inspection. [ПРОВЕРЕНО: filename pattern]; [ТРЕБУЕТ ПРОВЕРКИ: storage path]
