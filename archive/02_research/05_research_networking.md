# 05 · Сетевые каналы и бюджеты

## Каналы

| Поток | Транспорт | Инициатор → адрес | Payload/частота | Авторизация | Статус |
|---|---|---|---|---|---|
| Live point frame | HTTPS POST JSON | Quest → `https://arescope.mrfenek.eu.cc/api/live/frame` | период 3 s; ≤384 отправленных points/frame; X/Y/Z с 3 десятичными знаками; yawDeg | `Authorization: Bearer <producer>` | [ПРОВЕРЕНО: client/server source] |
| Final mesh | HTTPS POST octet-stream | Quest → `/api/live/mesh?session=<id>` | ARSM v1/v2; client body cap 32 MiB; client timeout 60 s | producer Bearer | [ПРОВЕРЕНО: client/server source] |
| Device diagnostics | HTTPS POST text | Quest → `/api/live/log?source=<source>` | ≤8 MiB server-side; client snapshot cap 2,000,000 .NET characters (UTF-8 byte count may differ) | producer Bearer | [ПРОВЕРЕНО: client/server source] |
| Viewer live read | HTTPS GET | Browser → `/api/live/latest` | latest frame by room; live cache in process | viewer Bearer | [ПРОВЕРЕНО: server source] |
| Live browser stream | WebSocket `GET /api/live/stream?token=<viewer>` | Browser ↔ LAB | initial snapshot; subsequent live frame JSON; 20 s idle ping; queue max 32, drops oldest | viewer token in query; unauthorized close 4401 | [ПРОВЕРЕНО: `app.py`; reverse proxy WebSocket forwarding still requires nginx check] |
| Copilot ASR | HTTPS POST audio | Quest → `/api/copilot/transcribe` | WAV/MP3/WebM/MP4; max audio 8 MiB; upstream Whisper model | device/either bearer | [ПРОВЕРЕНО: client/server source] |
| Copilot LLM | HTTPS POST SSE | Quest → `/api/copilot/chat` | SSE deltas/completion; request text ≤12,000 chars | device/either bearer | [ПРОВЕРЕНО: client/server source] |
| Copilot TTS | HTTPS POST → audio response | Quest → `/api/copilot/speech` | response capped 8 MiB; MP3 expected | device/either bearer | [ПРОВЕРЕНО: client/server source] |

[ПРОВЕРЕНО: `LiveFrameSender.cs`, `MeshUploader.cs`, `LogUploader.cs`, `app.py`; WebSocket public path and auth detail not fully retrieved]

## Frame coordinates and JSON contract

Example schema (illustrative, not a working source file):

```json
{"room":"default","yawDeg":42.1,"points":[[0.123,0.420,1.200]]}
```

- `room`: client default `default`, server truncates to 64 characters. [ПРОВЕРЕНО]
- `yawDeg`: headset yaw in degrees, one decimal in client JSON. [ПРОВЕРЕНО]
- `points`: local/headset-relative metres; client filters by `|y| ≤ 1.4 m`, Euclidean distance ≤10 m, sends at most 384. [ПРОВЕРЕНО: sender defaults]
- Server accepts list length ≤4096; 0..4096 points. [ПРОВЕРЕНО: `app.py`]
- Server frame response includes `ok`, room, pointCount, viewers, sessionId, stored and throttled. [ПРОВЕРЕНО: `post_frame`]

## Rate, compression and storage

- Client point frame interval: 3.0 seconds; send timeout 8 seconds. [ПРОВЕРЕНО]
- Server persistence interval lower bound: 0.25 seconds per room; faster incoming frames may update live state without persistence. [ПРОВЕРЕНО]
- Client creates sample array sized `max(8, 384*4)=1536` points, then sends at most 384 after spatial filters. [ПРОВЕРЕНО]
- SQLite point payload is JSON compressed with gzip level 6 before insertion. [ПРОВЕРЕНО]
- Server frame cap 2000/session; retention 7 days; payload sum cap 200 MiB; export cap 400,000 points. [ПРОВЕРЕНО: defaults]
- Frame client currently sends point positions only; vertex colours and triangle indices travel only in final mesh ARSM, not live JSON. [ПРОВЕРЕНО]

## Disconnection behavior

- Live frame sender logs HTTP status; network/TLS exception sets status code 0 and does not show a synthetic HTTP code. [ПРОВЕРЕНО]
- No persistent offline queue or guaranteed replay after reconnect is evident in `LiveFrameSender.cs`. [ПРОВЕРЕНО: inspected current source]; recommended behaviour is queue only latest snapshot or explicitly report dropped frames. [ПРЕДПОЛОЖЕНИЕ]
- Logs are uploaded on pause/quit and X+Y; crash recovery uses `.running` marker on next start. [ПРОВЕРЕНО: `LogUploader.cs`]
- Copilot voice requests use HTTP timeouts and fail to `Error`; no fully offline ASR/LLM/TTS path is specified. [ПРОВЕРЕНО: source]

## Data volume formulas (estimates)

- Live JSON point payload upper bound from configured cap: `384 points × 3 coordinates × 8 chars + separators ≈ 10–20 KiB` before HTTP overhead, depending on value widths. [ПРЕДПОЛОЖЕНИЕ: conservative serialization estimate; no packet capture]
- Maximum regular cadence: `1/3 s = 0.333 frame/s`, approximately 20 frames/minute, if scanner and network remain active. [ПРОВЕРЕНО: arithmetic from configured interval]
- Approximate upper-volume rate at 20 KiB/frame: 400 KiB/minute, ~6.7 KiB/s, before TLS/IP overhead. [ПРЕДПОЛОЖЕНИЕ]
- Actual measured wire bytes, Wi-Fi loss and LTE/hotspot performance: данных нет. [ТРЕБУЕТ ПРОВЕРКИ]

## Security boundaries

- Producer and viewer use separate bearer roles in LAB API; the actual token values must not appear in archive. [ПРОВЕРЕНО: environment/config pattern; values excluded]
- A producer token embedded in an APK can be extracted; code comments call it limited-purpose/revocable. [ПРОВЕРЕНО: `LiveFrameSender.cs`]
- Transport is HTTPS to public domain names in configured clients. [ПРОВЕРЕНО: endpoint strings]
- Rotation process, token expiry, rate limiting by producer identity, and TLS pinning are not established here. [ТРЕБУЕТ ПРОВЕРКИ]
