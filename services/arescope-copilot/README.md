# Arescope Copilot

Python 3.11+ FastAPI service for a Russian-language Mars Rover Mission Control
operator and field test engineer assistant: ASR, streamed chat, speech, and
persistent mast testbed headset settings. The application runs on `127.0.0.1:18975`; OmniRoute defaults to
`http://127.0.0.1:20128/v1`. No decision/SDM route exists.

## Run locally

From this directory, create a virtual environment and install `requirements.txt`.
Set the variables documented in `.env.example` in the process environment, then run:

```console
python app.py
```

The service does not automatically load `.env` files. Both Bearer tokens must be
distinct, printable ASCII secrets of at least 24 characters. Invalid token
configuration refuses startup before creating a database. Generate each token
independently with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
Keep `OMNIROUTE_API_KEY` exclusively on the server. A missing router key leaves
health and settings available; ASR/TTS return 502 and chat emits an SSE error.

`ARESCOPE_ALLOWED_ORIGINS` is a comma-separated list of exact HTTP(S) origins
such as `https://panel.example.com,http://localhost:3000`. Paths, wildcard origins,
and credentials are invalid. Default ports and hostname case are normalized.
Every request with an `Origin` header must match; requests without that header
still require the appropriate Bearer token on protected routes. Allowed browser
preflights accept GET/PUT/POST and Authorization/Content-Type headers.

## API

All protected routes use `Authorization: Bearer <token>`. Invalid credentials or
the wrong role return 401. Origin rejection returns 403. Responses are not cached.

| Method and path | Role | Contract |
| --- | --- | --- |
| GET `/healthz` | Public | `{ "ok": true }`; local liveness only |
| GET `/api/copilot/status` | Panel | `router_configured`, `voice_profiles` mapping, features `llm/asr/tts`; no live router probe |
| GET `/api/copilot/settings` | Either | Version, full settings, `device_applied`, `acked_at` |
| PUT `/api/copilot/settings` | Panel | `{version,settings}` with all four settings fields; increments version; stale version returns 409 |
| POST `/api/copilot/settings/ack` | Device | `{version}`; stale version returns 409 |
| POST `/api/copilot/transcribe` | Either | Raw WAV/x-WAV/MP3/WebM/MP4, at most 8 MiB; returns `{text,model}` |
| POST `/api/copilot/chat` | Either | `{text,context?}` JSON, at most 32 KiB; SSE `text`, `complete`, or `error` data objects |
| POST `/api/copilot/speech` | Either | `{text,voice}` JSON, at most 32 KiB; returns MP3 bytes |

Settings start at version 1 with voice `male`, volume `1.0`, HUD enabled, and
follow mode `smooth`. PUT requires a complete settings object: `voice` is
`male`/`female`, volume is a finite number from 0 to 1, `hud_enabled` is a JSON
boolean, and `hud_follow_mode` is `hard`/`smooth`. Unknown fields and coercions
are rejected with 422. `acked_at` is a nullable Unix timestamp in seconds;
`device_applied` is true through 30 seconds after an acknowledgement of the
current version. Updating settings clears the acknowledgement. Writes and
acknowledgements use SQLite transactions and a 5-second lock timeout.

The default database is `~/.local/share/arescope-copilot/settings.sqlite3`.
On POSIX the database is created/restricted to 0600, and newly created state
directories use 0700. On Windows use an appropriately restricted account/ACL;
POSIX permission bits do not provide Windows ACL enforcement.

Text must be nonblank and at most 12,000 characters; optional chat context may
be at most 12,000 characters. Invalid JSON/fields return 422. Request byte limits
are enforced while reading, including chunked uploads. ASR rejects empty audio
with 400 and unsupported media types with 415. ASR and TTS upstream failures
return 502 without exposing provider bodies, keys, or exception details.

Chat uses the Russian rover-operator system prompt in `copilot_core.py` and tries
`agy/gemini-4-hydrogen-low`, `cx/gpt-6-luna`, `th/muse-ember`, then
`th/glm-5.3-flash`, in that order. Fallback stops at the first emitted text delta.
A subsequent interruption emits `error` without `complete` or another model.
Upstream 401/402/403 terminate immediately with an SSE error, except an exact
`provider_not_configured` code on a bounded 401 chat error: that means the selected
provider is unavailable and permits fallback before any text. General credential
and account failures remain terminal. A successful stream
requires `[DONE]` or `finish_reason=stop`; an unexpected EOF is an interruption.
Upstream SSE frames are decoded after byte framing so split UTF-8 characters
survive. Limits are 4 MiB upstream bytes, 1 MiB per pending SSE frame, 12,000
output characters, and one overall 90-second deadline across chat attempts.
Connection timeout is 10 seconds. ASR has a 60-second deadline; TTS has a
90-second deadline and an 8 MiB output limit. Timeouts cover the whole operation
as well as HTTP transport inactivity. HTTP redirects are not followed.

Replies stay within 1–3 Russian sentences. Supply Guardian risk, predicted cause,
lead time, confidence, and rover telemetry in `context`; the assistant has no
independent telemetry access and must never invent readings or completed actions.
It explains dust/occlusion, glare/shadows, low texture, wheel slip, sensor dropout,
pose jumps, and link loss without exaggerated claims about Martian wind. Recovery
guidance prioritizes stopping and checking sensors/landmarks; reversing requires
a verified traversable path. Synthetic rover data, NASA archives, and live mast
testbed captures remain distinct. For Slow Loop updates it helps review incident
labels and independent hold-out metrics before/after training; deployment requires
explicit operator approval, and improvement is never assumed without results.

Speech uses `minimax/speech-2.8-hd`, MP3 output, speed 0.95, volume 1, pitch 0,
and normalization `basic`. Voices map to `Deep_Voice_Man` and `Calm_Woman`.

## Deployment templates

The files in `deploy/` are templates; nothing is installed automatically. See
[V2 deployment](../../docs/V2_DEPLOYMENT.md) for the current production layout,
legacy settings migration and rollback procedure.

1. Create an unprivileged `arescope-copilot` system user/group and install this
   service under `/opt/arescope-copilot`, with its virtual environment at `.venv`.
2. Create `/etc/arescope-copilot.env`, owned by root with mode 0600. Set both
   tokens, the router key, and the panel origin. For this unit set
   `ARESCOPE_SETTINGS_DB=/var/lib/arescope-copilot/settings.sqlite3` (or omit it);
   do not copy the example's home-directory path into the hardened unit.
   `EnvironmentFile` values override the unit's environment defaults.
3. Install `deploy/arescope-copilot.service`, reload systemd, and enable/start
   the service. `StateDirectory` creates its writable private database directory;
   the rest of the filesystem is read-only to the service. Use one worker.
4. Include `deploy/nginx-copilot.conf.example` in the site's TLS server block,
   configure the domain/certificates, validate with `nginx -t`, and reload nginx.
   The template preserves Bearer/Origin headers, disables SSE buffering/cache/
   gzip, and allows the 8 MiB audio upload. JSON routes enforce 32 KiB in-app.
5. Check `/healthz`, authenticated status/settings, a device acknowledgement,
   and staging audio → chat → speech. Keep Uvicorn on loopback.

Back up SQLite using its online backup API or while the service is stopped.

## Automated checks

Install `requirements-dev.txt` in the virtual environment, then run from this
directory (the temp/cache/coverage outputs stay here):

```console
python -m pytest --basetemp=.tmp/pytest --cov=app --cov=copilot_core --cov-report=term-missing
```

The suite uses `httpx.MockTransport`; it requires no live router, tokens, or
credentials. It covers every route, role enforcement, invalid startup config,
origins/CORS, persistent settings, concurrent updates, acknowledgement expiry,
UTF-8/CRLF streaming, fallback/abort behavior, provider failures, timeouts, and
request/output limits. The POSIX permission assertion is skipped on Windows.
