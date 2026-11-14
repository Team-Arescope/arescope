# Stale-content audit (Arescope web + Unity)

Run after a feature ships or a branch merges, and before telling the user the project is consistent. The goal is to find text, code and assets that contradict the current build.

## Scope
- Scan source only: `.js .html .css .py .cs .md .json .txt`. Skip `.git`, `node_modules`, `Library`, `Temp`, `Build` and minified vendor bundles — `static/three.min.js` alone floods a grep with ~600 kB and hides every real hit.
- Repos to cover: `/root/Developer/arescope-lab` (public site), `arescope-beta02-core` (Copilot service), `arescope-beta02-questroom/Assets` (Unity).

## What to grep
- Version drift: `\b0\.\d\b`, `BETA 0\.\d`, old artifact names (`AppCompat-fix`, `Beta-0.2`).
- Claims the build contradicts: `не поддерживается`, `не является live`, `Ни один режим`, `нет live`, `без live-связи`, `интеграция отсутствует`, `не подключена` (check each hit — “гарнитура не подключена” is usually still true).
- `TODO|FIXME|XXX|HACK`.
- Dead addresses: old ports and hosts (`127.0.0.1:18964` vs the real `18965`), placeholder `host.example`.

## Cross-check the API surface in both directions
```python
routes = re.findall(r"@app\.(?:get|post|put|delete|websocket)\(['\"]([^'\"]+)", app_py)
called = re.findall(r"['\"`](/api/[a-z0-9_/\-]+)", static_js_and_html)
print(sorted(called - routes))   # callers with no route -> bug
print(sorted(routes - called))   # routes with no caller -> often fine (producer-only)
```
Do the same for the Unity client: collect `/api/copilot/...` string literals from `Assets/**/*.cs` and diff against the service decorators.

## Dead code: candidates vs verdicts
- A class that appears only in its own file is a candidate, not a verdict. Editor scripts are invoked by `-executeMethod` string, DTOs are materialised by `JsonUtility`, and nested `MaskableGraphic` classes are constructed by type inside the same file — all look “unreferenced”.
- What settles it: no `.meta`, no GUID in any `.unity`, and an already-wired replacement with the same purpose (here `FinalizedScanMinimap` was superseded by `LiveScanMinimap`).
- Remove with `git rm` so it stays recoverable, and tell the user it is in history.

## Assets and binaries
- List `Assets/SimData/Models/*` and `Textures/*_diff.jpg`, then grep the scene builder for each name; an unused CC0 download is repository weight.
- Regenerable binaries (raw PDS crops, caches) belong outside `Assets/` — the editor imports them and git carries them forever. Keep them in a scratch dir and gitignore the pattern.

## Secrets
Grep code and config only (not the secrets directory) for `sk-[A-Za-z0-9]{16,}`, `Bearer [A-Za-z0-9_\-]{24,}`, `api[_-]?key\s*[:=]\s*['"][^'"]{16,}`. Legitimate tokens live in `/etc/<unit>.env` (0600) and `~/.secrets`.

## Deployed page
- Fetch the served HTML, extract every `/static/...` `src`/`href`, and require 200 on each. A referenced-but-uncommitted file ships as 404 while the markup looks correct; the panel renders and every handler is dead.
- Confirm the repo actually carries each file: `git ls-files static/`. After a branch merge, untracked files from the worktree do not travel with it.
- Verify the deployed module against the source with `sha256sum` when the service has a deployed copy (`/opt/...` vs source repo).
