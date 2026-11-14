# Verification results

Executed on 2026-11-14 with Windows, Python 3.12.16, Node 24.18.0 and installed
Chrome. All implementation, dependency, test storage and generated artifacts
used by this work are beneath `services/arescope-lab/`.

| Check | Result |
| --- | --- |
| `python -m pytest services/arescope-lab/tests/test_lab_api.py -q` from repository root | **65 passed**, 80.02 s |
| `node --test tests/mission_control.test.cjs` | **8 passed**, no failures |
| `node tests/mission_control.browser.cjs` | **Passed** |
| `python tools/verify_terrain.py` | **20,866 heights verified** against primary PDS byte ranges and SHA-256 checksums |

Pytest reports one third-party deprecation warning: Starlette TestClient refers
to `anyio.abc.BlockingPortal`, which has moved to `anyio.from_thread` in the
installed AnyIO version. There are no test failures.

Python coverage includes the actual 2000-frame cap, session splitting and
revalidation, age/size pruning and foreign-key cascade, ARSM v1/v2 malformed
headers/counts/lengths/tail indices/PNG limit, PLY deduplication and caps, UTF-8
logs/path traversal/collisions, every role boundary, empty/equal token configs,
queue overflow and pings, simulated storage errors, an actual exclusive SQLite
lock, streamed upload caps and served static references.

The browser checks real WebSocket push and the unauthorized **4401** close,
auth-header Blob downloads for PLY and ARSM, log reading, font/static loads,
both terrain sources, visibly different grid modes and a zero WebGL error state.
It recorded no page errors or failed static requests.

| Width | Pane | Horizontal overflow (px) | Overflowing children |
| --- | --- | ---: | ---: |
| 1440 | Equipment/live | 0 | 0 |
| 1440 | Sessions | 0 | 0 |
| 1440 | Logs | 0 | 0 |
| 1440 | Settings | 0 | 0 |
| 390 | Equipment/live | 0 | 0 |
| 390 | Sessions | 0 | 0 |
| 390 | Logs | 0 | 0 |
| 390 | Settings | 0 | 0 |

The mobile equipment pane also has `scrollHeight > clientHeight`, so its lower
controls are reachable by vertical scrolling. Raw measurements are saved in
`tests/artifacts/browser-report.json`; screenshots are saved as
`mission-1440.png`, `mission-390.png` and `mission-terrain.png` in that directory.
All browser fixtures use dummy tokens and isolated local storage.

Deployment units were prepared as Linux templates. A target-host systemd/nginx
configuration check and public TLS deployment remain operations tasks outside
this local implementation and test run.
