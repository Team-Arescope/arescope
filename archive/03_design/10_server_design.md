# 10 · Серверная часть

## Сервисы и порты

| Сервис | Локальный bind | Процесс/конфигурация | Назначение | Статус |
|---|---|---|---|---|
| Arescope LAB | `127.0.0.1:18965` | systemd `arescope-lab.service`; `/usr/bin/python3 -m uvicorn app:app`; `/etc/arescope-lab.env` | ingest сканов, SQLite history, PLY/mesh/log API | [ПРОВЕРЕНО: текущий systemd unit]
| Arescope Copilot | исторически `127.0.0.1:18975` | FastAPI/Uvicorn; source path `/opt/arescope-copilot` | ASR/LLM/TTS/settings | [ПРОВЕРЕНО: ранее опрошенный endpoint]; [ТРЕБУЕТ ПРОВЕРКИ: unit/port сейчас]
| OmniRoute | `127.0.0.1:20128/v1` | provider router | upstream models/audio | [ПРОВЕРЕНО: default URL Copilot]; health сервиса сейчас не проверен |
| nginx/TLS | ожидаемый public 443 | reverse proxy | публичные домены и API | [ТРЕБУЕТ ПРОВЕРКИ: активный server block и certificate]

## Хранение Arescope LAB

- SQLite schema `sessions` + `frames`, foreign-key cascade, два индекса. [ПРОВЕРЕНО: `app.py`]
- Payload кадра хранится как gzip(level 6) компактного JSON. [ПРОВЕРЕНО]
- Defaults: `ARESCOPE_SESSION_GAP=60`, `ARESCOPE_RETENTION_DAYS=7`, `ARESCOPE_MAX_DB_BYTES=209715200`, `ARESCOPE_MIN_HISTORY_INTERVAL=0.25`, `ARESCOPE_MAX_FRAMES_PER_SESSION=2000`, `ARESCOPE_MAX_EXPORT_POINTS=400000`, `ARESCOPE_MAX_LOG_BYTES=8388608`, `ARESCOPE_MAX_MESH_BYTES=33554432`. [ПРОВЕРЕНО: source defaults]
- Live frame state, WebSocket subscriber queues, session continuity cache and counters live in process memory; service restart clears them. [ПРОВЕРЕНО: global data structures]
- Live frame TTL is 30 s; cleanup runs during requests. [ПРОВЕРЕНО: `LIVE_TTL_SECONDS=30` and `_cleanup`]
- Default paths: DB `/var/lib/arescope-lab/live.sqlite3`, mesh directory `/var/lib/arescope-lab/meshes`, logs `/var/lib/arescope-lab/logs`. [ПРОВЕРЕНО: source defaults; production overrides should be checked]

## Переменные окружения (значения секретов не включены)

| Переменная | Назначение / default | Статус |
|---|---|---|
| `ARESCOPE_LIVE_PRODUCER_TOKEN` | producer authorization; empty by default, write routes fail closed | [ПРОВЕРЕНО] |
| `ARESCOPE_LIVE_VIEWER_TOKEN` | viewer authorization; empty by default | [ПРОВЕРЕНО] |
| `ARESCOPE_LIVE_DB` | SQLite path; default `/var/lib/arescope-lab/live.sqlite3` | [ПРОВЕРЕНО] |
| `ARESCOPE_SESSION_GAP` | session split gap; `60` seconds | [ПРОВЕРЕНО] |
| `ARESCOPE_RETENTION_DAYS` | history age; `7` days | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_DB_BYTES` | payload cap; `209715200` bytes | [ПРОВЕРЕНО] |
| `ARESCOPE_MIN_HISTORY_INTERVAL` | `0.25` seconds | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_FRAMES_PER_SESSION` | `2000` | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_EXPORT_POINTS` | `400000` | [ПРОВЕРЕНО] |
| `ARESCOPE_MESH_DIR` | `/var/lib/arescope-lab/meshes` | [ПРОВЕРЕНО] |
| `ARESCOPE_LOG_DIR` | `/var/lib/arescope-lab/logs` | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_LOG_BYTES` | `8388608` bytes | [ПРОВЕРЕНО] |
| `ARESCOPE_MAX_MESH_BYTES` | `33554432` bytes | [ПРОВЕРЕНО] |
| `ARESCOPE_COPILOT_TOKEN`, `ARESCOPE_DEVICE_TOKEN` | panel and headset auth tokens, must be different | [ПРОВЕРЕНО: Copilot source] |
| `OMNIROUTE_API_KEY` | server-only provider credential | [ПРОВЕРЕНО] |
| `ARESCOPE_ROUTER_URL` | default `http://127.0.0.1:20128/v1` | [ПРОВЕРЕНО] |
| `ARESCOPE_SETTINGS_DB` | default `~/.local/share/arescope-copilot/settings.sqlite3` | [ПРОВЕРЕНО] |
| `ARESCOPE_ALLOWED_ORIGINS` | allowlist for Origin header; defaults empty | [ПРОВЕРЕНО] |

- JEV/SDM environment values were removed in a prior production change. Current production env should be rechecked for deprecated names without printing values. [ПРОВЕРЕНО: change report]; [ТРЕБУЕТ ПРОВЕРКИ: current state]
- Env variable values, bearer tokens, passwords and private keys are not archived. [ПРОВЕРЕНО: archive policy]

## Очистка и фоновые операции

- `_prune()` запускается на ingest, не чаще одного раза в 3600 s без принудительного вызова; удаляет sessions старше retention и затем oldest sessions, пока сумма payload не станет ≤ DB cap. [ПРОВЕРЕНО]
- Для session используется 60 s gap; session capped at 2000 frames. При достижении лимита live feed продолжает обновляться, история дальше не растёт. [ПРОВЕРЕНО]
- Live latest frame cleanup после 30 s бездействия выполняется при обработке API/WebSocket-side cleanup triggers. [ПРОВЕРЕНО: `_cleanup`; конкретный набор вызовов — source]
- Ротация/retention логов и mesh файлов не задаётся endpoint-кодом; отдельная ops policy обязательна. [ПРОВЕРЕНО: source inspection]

## Резервное копирование

- Для SQLite использовать online backup API либо согласованный snapshot при остановленном сервисе; обычная копия во время активной записи не подтверждена как безопасная процедура. [ПРЕДПОЛОЖЕНИЕ: эксплуатационная рекомендация]
- Отдельно сохранять mesh/log directories и `/etc/arescope-lab.env`; secret-bearing backup должен быть зашифрован и ограничен по доступу. [ПРЕДПОЛОЖЕНИЕ]
- В доступных источниках нет подтверждённого restore-теста. [ТРЕБУЕТ ПРОВЕРКИ]

## Развертывание: контрольный список

1. Создать непривилегированного systemd user. Текущий unit использует root; смена пользователя требует проверки permissions. [ПРОВЕРЕНО: `User=root`]; [ПРЕДПОЛОЖЕНИЕ: hardening]
2. Установить restrictive permissions на env file (например 0600); не выводить секреты в терминал/логи. [ПРЕДПОЛОЖЕНИЕ: security procedure]
3. Оставить Uvicorn bind только на loopback. [ПРОВЕРЕНО: текущий unit]
4. Настроить nginx TLS и WebSocket Upgrade/timeouts для `/api/live/stream`; точный production server block ещё не сохранён в архиве. [ТРЕБУЕТ ПРОВЕРКИ]
5. Выполнить live health и authenticated producer/viewer smoke tests. [ТРЕБУЕТ ПРОВЕРКИ: endpoint зависит от deployment]
6. Проверить ownership DB/mesh/log directories и восстановление backup. [ТРЕБУЕТ ПРОВЕРКИ]
