# Headless Unity editor traps

Failures where the build method never runs, or runs but renders something misleading.

## The method never runs

Check the log for the method's own `Debug.Log` marker. No marker means Unity exited before `-executeMethod`.

- **Stale lock.** A leftover editor process holds `Temp/UnityLockfile`; the next run exits in ~2 s with a log ending at `SDL leaked N allocations`. Kill Unity processes, delete `Temp/UnityLockfile`, rerun.
- **First run after installing a package.** The invocation resolves and imports packages, then quits. The log has no marker. Run the same command again before suspecting the code.
- **Malformed `.meta`.** A hand-written GUID containing any character outside `0-9a-f` makes Unity skip the asset, and the method may never be reachable. Generate with `uuid.uuid4().hex` (32 chars).
- **Deleted package cache.** Removing `/data/home/.gradle` wholesale is safe and forces a rebuild; deleting `~/.gradle/caches` selectively can leave a broken `jdkImage` transform. Prefer the whole directory.

## It runs but the picture lies

- **World-space UI rendered into a `RenderTexture` needs `camera.aspect`.** Without setting `camera.aspect = width / height` (and rebuilding the projection matrix) before `Render()`, a world-space canvas is squeezed and panels overlap. Symptom: proportions differ from the same UI in an on-screen preview while the layout code is unchanged.
- **`FindFirstObjectByType<Light>()` is not "the sun".** It returns whichever light is first in scene order, including a spot light added moments earlier in the same method. Filter explicitly:

```csharp
Light sun = null;
foreach (var l in Object.FindObjectsByType<Light>(FindObjectsSortMode.None))
    if (l.type == LightType.Directional) { sun = l; break; }
```

- **Terrain silhouette instead of a surface.** Heightmap meshes at eye height read as black wedges when the sun is behind the ridge. For a composition/UI review frame, swap the terrain material to an unlit material carrying the same `_BaseMap`, render, then restore — and say in the report that lighting was bypassed.
- **Edit-mode previews need an explicit lifecycle.** Batch renders ignore components that initialise in play mode; invoke `Awake` through reflection before driving such a component.
