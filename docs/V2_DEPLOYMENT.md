# V2 production deployment

Target: [Arescope LAB](https://arescope.mrfenek.eu.cc). Deployed on 2026-11-15
(operator local date), from `ee18cb0` plus the deployment compatibility fixes in
the commit containing this document. No Unity/Android build is part of this rollout.

## Server layout

- SSH account: `ubuntu`, port 22. Deployment credentials remain outside Git.
- Copilot release: `/opt/arescope-releases/v2-20261115-002532/services/arescope-copilot`.
- LAB terrain release: `/opt/arescope-releases/v2-terrain-20261115/services/arescope-lab`.
  Its virtual environment links to the previous LAB release; keep that release
  available while this environment is in use.
- LAB: `arescope-lab.service`, system user `arescope-lab`, Python 3.12 virtual
  environment, one Uvicorn worker on `127.0.0.1:18965`.
- Copilot: `arescope-copilot.service`, system user `arescope-copilot`, separate
  Python 3.12 environment, one worker on `127.0.0.1:18975`.
- Existing state retained under `/var/lib/arescope-lab/` and
  `/var/lib/arescope-copilot/`; directories 0700, Copilot SQLite file 0600.
- Credentials remain in root-owned, 0600 `/etc/arescope-lab.env` and
  `/etc/arescope-copilot.env`. Existing producer, viewer, panel and device
  credentials are retained. The supplied producer/device credentials matched
  the existing service credentials before cutover.
- Copilot uses the configured HTTPS OmniRoute endpoint. Provider keys remain
  server-side. The allowed browser origin is the production site.

nginx preserves the existing certificate, domain and listener. It routes
`/api/copilot/` to Copilot and other application paths to LAB. The exact live
WebSocket location forwards Upgrade headers and suppresses access/error request
logging; Copilot disables buffering, caching and gzip. LAB accepts mesh uploads
up to the application limit of 32 MiB. Public `/healthz` belongs to LAB; check
Copilot health separately on its loopback port.

## Compatibility changes

The original server's LAB schema had no `frames.metadata`; V2 adds that nullable
column without rewriting compressed point payloads. The original database
contained three sessions and 106 frames before deployment.

The original Copilot database used `settings(id, version, payload)` with version
zero. `SettingsStore.initialize()` now migrates that recognized schema in an
explicit transaction, validates every setting, preserves the settings, and maps
version zero to one. Positive versions remain unchanged; acknowledgement starts
unset. Unsupported or malformed legacy data fails without resetting the database.
Repeated initialization is idempotent.

At rollout, OmniRoute listed the fallback chat models but no longer listed
`agy/gemini-4-hydrogen-low`; selecting that provider returned HTTP 401 with the
specific `provider_not_configured` code. Chat now recognizes only that bounded
error as provider unavailability and can continue to the next model before
emitting text. General 401/402/403 authentication/account failures remain terminal;
an interrupted answer never switches models. The available `cx/gpt-6-luna` route
was verified directly before enabling the fallback fix.

## Verification and evidence

The migration was first exercised against an SQLite backup of the actual server
database. The saved voice, volume, HUD visibility and follow mode were preserved.
Both services passed their Python suites on the target Python 3.12 environments:
139 LAB tests and 260 Copilot tests, including the provider fix. The initial
cutover followed successful LAB tests and the 239-test Copilot migration suite;
the expanded Copilot suite passed before restarting with the provider fix.

The reusable checker reads existing protected environment files without printing
their contents:

```sh
sudo /opt/arescope-releases/v2-20261115-002532/services/arescope-lab/.venv/bin/python \
  /opt/arescope-releases/v2-20261115-002532/scripts/verify_v2_deployment.py \
  --source-dir /opt/arescope-releases/v2-20261115-002532/services/arescope-lab \
  --exercise --ai
```

The installed checker matches [the repository script](../scripts/verify_v2_deployment.py).
The default checks cover static asset hashes, role separation, Guardian
reads, Copilot status/settings, authenticated WSS snapshot, rejected credentials
and storage errors. `--exercise` adds a uniquely named synthetic carrier, verifies
push/history/PLY, and deletes only that test session. `--ai` makes paid router
requests for chat, speech and transcription of the generated speech. It never
labels incidents, retrains or activates a Guardian model, changes operator
settings, or acknowledges on behalf of a device.

All **108 production checks passed**, including a complete streamed answer,
163,572 bytes of MP3 speech, and a nonempty ASR transcript of that speech. The
checker removed its own synthetic test session and observed no increase in storage
errors. Sanitized evidence: [production checks](qa/v2-production-checks.json).

Cache-disabled Chrome verification of the production site passed: no page errors
or missing assets; all five drawer panes had zero horizontal overflow at
1440 × 900 and 390 × 844. Starting the synthetic rover and injecting dust produced
a Guardian warning with a dust/occlusion cause. The simulator was stopped and its
fault selection restored to nominal afterwards. The active Guardian model remains
`v1`; no candidate was approved during deployment.

Screenshot: [production Guardian](qa/v2-production-1440.png). It shows synthetic
rover data on archived HiRISE terrain. This is not physical rover or Quest runtime
validation; benchmark metrics remain synthetic hold-out results.

## Backups and rollback

Root-only backups are under `/var/backups/arescope/v2-20261115-002532/`:
original unit/environment files, nginx configuration, original Copilot code,
online SQLite snapshots, stopped-state `*.cutover.sqlite3` snapshots taken
immediately before migration, and LAB meshes/logs. The former LAB checkout remains
untouched at `/root/Developer/arescope-lab`.

For rollback, stop both services before restoring files. Restore both original
unit and environment files and `nginx-arescope-lab`. The old Copilot requires its
pre-migration database schema: restore `arescope-copilot.cutover.sqlite3` to
`/var/lib/arescope-copilot/settings.sqlite3` while stopped, handling any SQLite
sidecar files only for that stopped database. Restore the LAB database from its
cutover snapshot only if required; this discards all writes after cutover.
Restore appropriate file ownership, run `systemctl daemon-reload`, validate
`nginx -t`, start both services, then reload nginx and repeat endpoint checks.
The old units point to the preserved original code directories.

Never restore environment backups into the repository or print them. Backend and
static assets must roll back together. Returning to older code does not itself
restore Guardian model state; database restoration is a separate, data-losing
operator decision.

## Fleet and camera update

The follow-up release adds full vertical/horizontal camera orbit and a synthetic
fleet survey with 1–6 rovers, coverage, trails and inspection assistance. It keeps
the original single-rover simulator and Guardian benchmark fixtures unchanged.
The mission coordinator uses Guardian ML outputs with explicit allocation policies
and bounded A* routing. It does not use an LLM to drive motors or claim physical
repair. See [fleet demonstration](FLEET_DEMO_RUNBOOK.md).

Before cutover, the current LAB unit and an online database backup were saved under
`/var/backups/arescope/v2-fleet-20261115/`. Only LAB's unit paths change; Copilot,
credentials, storage paths and nginx remain in place. To revert this update, stop
LAB, restore that directory's `arescope-lab.service`, reload systemd and start LAB.
No database restoration is required for this code rollback. Avoid deleting the
earlier release because the fleet environment still uses it.

The complete fleet release passed **200 Python tests** on the target host and
**17 Node tests** locally. A follow-up public HTTPS check passed **97 checks**,
including static hashes, auth roles, WSS push, persistence and export. The change
also fixes scoped cancellation during WebSocket disconnect cleanup: child tasks
are drained under a cancellation shield, while genuine worker errors still
propagate. Regression tests cover both behavior paths.

Production Chrome passed **20 browser checks**, including positive/negative
vertical orbit, camera reset, three projected markers, helper assignment and
arrival, continued survey, WebGL status and ten desktop/mobile drawer bounds.
The default view now looks down onto the terrain; fleet markers and coverage
remain depth-tested. Legacy floating carrier cards hide in fleet view, and fleet
frames do not automatically open an inspection window.
[Browser evidence](qa/fleet-production-checks.json) and
[production screenshot](qa/fleet-production-1440.png).

## Expanded terrain update

The active HiRISE display now uses exact source samples across **4.05 × 9.97 km**:
129 rows × 53 columns, stride 77, 77.90 m display spacing, about 40.4 km². Its
native source spacing remains 1.0117 m. MOLA now uses the native **64 ppd** product
`MEGT00N000GB.IMG`, a 65 × 65 crop spanning about 59 × 59 km, with 922.82 m east
and 926.12 m south spacing. No coordinates are stretched to enlarge either view.

The former HiRISE crop is frozen byte-for-byte in
`static/data/hirise-gale-benchmark.json`. Guardian explicitly uses it for training
and hold-out evaluation. Dataset hash checks and the adapted 30/30, 14.8 s and
98.6% F1 metrics remain unchanged. Fleet coordinates, coverage areas and routes
now derive from rectangular grid dimensions and actual east/south spacing.

The target host independently verified **11,062 displayed heights** against
NASA PDS byte ranges/checksums and passed **224 Python tests**. The frontend passed
**19 Node tests** for physical extents, rectangular rendering and fleet behavior.
The public HTTPS check passed **97 checks** after cutover.
Production Chrome passed **23 checks**, including both terrain extents/steps,
full camera orbit, three rover markers, inspection assistance and desktop/mobile
drawer bounds. [Expanded-region browser evidence](qa/terrain-production-checks.json).

The previous LAB unit and an online SQLite backup are in
`/var/backups/arescope/v2-terrain-20261115/`. Roll back code by restoring that
directory's `arescope-lab.service`, reloading systemd and restarting LAB. The
database schema did not change; existing credentials and state paths are retained.
The virtual environment still links to the original LAB release. Keep it available.

## Fleet access guidance

Start fleet requires a successful viewer connection in **Equipment and live**
and a producer token entered in **Guardian → Operator access**. The fleet panel
now explains the missing step beside Start and offers a button to focus the
corresponding field. Polling preserves that guidance. Authorization rules are
unchanged; a producer token cannot establish viewer access, and a viewer token
cannot issue simulator commands.

The update passed **224 Python tests**, **21 Node tests** and the local Chromium
workflow, including authorized fleet Start/Stop and wrong-role rejection.
[Public Chromium verification](qa/fleet-access-production-checks.json) passed
**30 checks** with caching disabled, including all referenced static assets and
desktop/mobile drawer bounds. This public check issued no simulator mutations.
Static files were replaced without restarting LAB or resetting its mission.
Previous files are backed up in `/var/backups/arescope/v2-fleet-access-20261115/`.

## Animated rovers and recovery policy

LAB now runs from `/opt/arescope-releases/v2-recovery-20261115/services/arescope-lab`.
The prior unit, an online SQLite backup and the previous simulation snapshot are
in `/var/backups/arescope/v2-recovery-20261115/`. Restarting the process begins a
new fleet mission; stored scan history and incident records are retained.
Restore the backed-up unit, reload systemd and restart LAB to roll back code.
The virtual environment still resolves to the original LAB release.

The map uses six-wheel rover geometry with terrain contacts, suspension, camera
mast and an articulated service tool. Acknowledged route corners drive motion
interpolation and wheel rotation. No movement is extrapolated beyond a received
snapshot. Pause, stale updates and reduced-motion preference stop animation.
Models are enlarged for visibility and shrink at archive edges. Follow, fleet
and region camera modes use the same projection and depth test as the terrain.

Minor dust, wheel slip and wheel obstruction can receive a timed synthetic
procedure from a healthy helper when Auto-repair is enabled. Sensor dropout,
HQ link loss, glare and low texture require a producer-authenticated Mission
Control decision tied to the current recovery request. Stale decisions fail
without mutation. A procedure never resumes movement until three consecutive
fresh nominal Guardian observations confirm recovery. The coarse archive
assistance zone and tool animation do not model a physical mechanical repair.

The isolated target release passed **281 Python tests**, including **57 recovery
tests**. **32 Node/Chromium checks** passed with the real geometry browser test
enabled. The integrated browser workflow also exercised real fleet recovery,
operator hold/approval, access roles and all ten desktop/mobile drawer bounds.

The deployed HTTPS browser run passed **41 checks** with caching disabled:
automatic wheel-obstruction service, sensor-drop approval/hold, stale-request
rejection, validated recovery, rolling/pause, camera modes, all assets and ten
drawer bounds. The fleet is paused after QA with Auto-repair enabled.
[Production check report](qa/rover-recovery-production-checks.json),
[survey view](qa/rover-survey-production.png),
[helper service](qa/rover-repair-production.png) and
[operator decision](qa/rover-approval-production.png).
