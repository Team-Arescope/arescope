# 21 · Инвентаризация конфигурации сервера

Значения секретов не записываются. Поле «default» ниже — значение, указанное в исходнике, и не доказывает фактическое production значение. [ПРОВЕРЕНО: extraction rule]

## Arescope LAB environment

| Variable | Default / required | Meaning | Status |
|---|---|---|---|
| `ARESCOPE_LIVE_PRODUCER_TOKEN` | required for write endpoints; no safe value in code | Quest producer authorization | [ПРОВЕРЕНО: `app.py`; secret value excluded] |
| `ARESCOPE_LIVE_VIEWER_TOKEN` | required for viewer endpoints | Browser/viewer authorization | [ПРОВЕРЕНО] |
| `ARESCOPE_LIVE_DB` | `/var/lib/arescope-lab/live.sqlite3` | SQLite history file | [ПРОВЕРЕНО] |
| `ARESCOPE_SESSION_GAP` | `60` seconds | split session after idle gap | [ПРОВЕРЕНО] |
| `ARESCOPE_RETENTION_DAYS` | `7` | session expiration | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_DB_BYTES` | `209715200` bytes (200 MiB) | cap on sum of compressed frame payloads | [ПРОВЕРЕНО] |
| `ARESCOPE_MIN_HISTORY_INTERVAL` | `0.25` seconds | minimum persist interval | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_FRAMES_PER_SESSION` | `2000` | per-session frame cap | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_EXPORT_POINTS` | `400000` | PLY export point cap | [ПРОВЕРЕНО] |
| `ARESCOPE_MESH_DIR` | `/var/lib/arescope-lab/meshes` | ARSM file directory | [ПРОВЕРЕНО] |
| `ARESCOPE_LOG_DIR` | `/var/lib/arescope-lab/logs` | device log directory | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_LOG_BYTES` | `8388608` bytes (8 MiB) | log upload cap | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_MESH_BYTES` | `33554432` bytes (32 MiB) | mesh upload cap | [ПРОВЕРЕНО] |

## Copilot environment

| Variable | Default/required | Purpose | Status |
|---|---|---|---|
| `ARESCOPE_COPILOT_TOKEN` | required | panel authorization | [ПРОВЕРЕНО: source] |
| `ARESCOPE_DEVICE_TOKEN` | required and distinct from panel token | headset authorization | [ПРОВЕРЕНО] |
| `OMNIROUTE_API_KEY` | required for upstream calls | server-side router credential | [ПРОВЕРЕНО] |
| `ARESCOPE_ROUTER_URL` | `http://127.0.0.1:20128/v1` | provider router base | [ПРОВЕРЕНО] |
| `ARESCOPE_SETTINGS_DB` | `~/.local/share/arescope-copilot/settings.sqlite3` | settings DB | [ПРОВЕРЕНО] |
| `ARESCOPE_ALLOWED_ORIGINS` | empty set in code | origin allowlist when Origin header present | [ПРОВЕРЕНО] |

## Android packaged non-secret configuration

- `Resources/arescope-endpoint.txt` or the endpoint resource referenced by connection configuration selects endpoint; exact staging/prod deployment mechanism needs scene/resource capture. [ПРОВЕРЕНО: helper diagnostic mentions resource; [ТРЕБУЕТ ПРОВЕРКИ] exact file contents]
- `Resources/arescope-live-token.txt` contains producer token in current client source path. The archive intentionally omits its value; regenerate a limited-purpose credential for each independent deployment. [ПРОВЕРЕНО: client source/comment]
- Base endpoint strings in source include `https://arescope.mrfenek.eu.cc/api/live/frame`, `/api/live/mesh`, and `/api/live/log`. [ПРОВЕРЕНО]

## Service unit snapshot

- LAB service file: `/etc/systemd/system/arescope-lab.service`; user `root`; working directory `/root/Developer/arescope-lab`; command Uvicorn at `127.0.0.1:18965`; env file `/etc/arescope-lab.env`. [ПРОВЕРЕНО: systemd output]
- Running as root is current configuration, not a recommended target. Least-privilege user requires ownership and file access migration. [ПРОВЕРЕНО/ПРЕДПОЛОЖЕНИЕ]
- Copilot service unit and exact runtime package lock not inventoried in this archive. [ТРЕБУЕТСЯ]

## Required config validation order

1. Fail startup if producer/viewer tokens missing or identical; verify panel/device Copilot tokens distinct. [ПРОВЕРЕНО: Copilot code validates panel/device; LAB auth fails closed for empty expected token]
2. Verify DB/mesh/log directories are writable by service account. [ПРЕДПОЛОЖЕНИЕ: deployment checklist]
3. Keep all env files out of git and set restrictive filesystem permissions. [ПРЕДПОЛОЖЕНИЕ: security requirement]
4. Use a reverse proxy with TLS; do not bind API publicly from Uvicorn. [ПРОВЕРЕНО: LAB unit binds loopback; public proxy configuration needs inventory]
5. Perform authorized smoke tests and read back exact resources. [ПРЕДПОЛОЖЕНИЕ]
