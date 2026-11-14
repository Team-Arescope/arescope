# Quest device diagnostics (adb/logcat)

## Capture a run

```sh
adb logcat -c
adb shell am start -n <pkg>/com.unity3d.player.UnityPlayerGameActivity
adb logcat -v time > run.txt          # Ctrl+C after the repro
```

Pulling only the app's process avoids drowning in system noise:

```sh
adb logcat -d -v time --pid=$(adb shell pidof -s <pkg>) > run.txt
```

## The encoding trap

Windows PowerShell's `>` redirection writes UTF-16LE. The file then contains
null bytes, every `grep` misses, and the log "looks empty" even though it is
hundreds of kilobytes. Either convert (`iconv -f UTF-16LE -t UTF-8 run.txt`)
or write with `Out-File -Encoding utf8`.

Binary captures have the same problem from the other direction:
`adb exec-out screencap -p > shot.png` corrupts the PNG through PowerShell
redirection. Take the screenshot on the device and pull it:

```sh
adb shell screencap -p /sdcard/shot.png
adb pull /sdcard/shot.png
```

## Permission truth

```sh
/opt/.../aapt2 dump permissions Build/App.apk      # what the APK declares
adb shell dumpsys package <pkg> | grep -A3 "runtime permissions"
```

On Horizon OS the scene and anchor permissions are `com.oculus.permission.*`;
only the camera one is `horizonos.permission.HEADSET_CAMERA`. `pm grant`
legitimately refuses some of them (`not a changeable permission type`) — those
are granted through an in-app prompt at first launch, so a refusal there is not
evidence of a broken build.

## Reading the run

- SDK lines carry a package prefix (for example `[RoomScan]`). Zero prefixed
  lines means the app never reached managed code.
- Depth provider signature: `DepthCapture: frames=N, depthAvail=..., sub=null`.
  `sub=null` means no XR depth subsystem registered — the provider package or
  its feature is missing, not a permission problem.
- A managed `NullReferenceException` at finalize while `frames=0` is downstream
  of the absent depth, not an independent bug; fix the provider first.
- SIGABRT in `UnityMain` with `libc++abi: terminating` immediately after
  `xrCreateInstance` and no game log is a native OpenXR feature failure. Bisect
  the enabled features; app-side logging cannot observe this class of crash.
- When the user retries inside one capture, several launches appear. Filter by
  PID and compare whether every process dies at the same offset from start —
  identical offsets mean a deterministic startup failure, not flakiness.

## Reviewing screenshots the user sends

A headset report usually arrives as several photos in one message, and the
model only sees the last attachment named in the prompt. Enumerate the cache
directory (`~/.hermes/cache/images`), dedupe by `md5sum`, and look at every
unique frame before answering — quoting one frame as "the" behaviour while
ten others sit unread is a visible miss to the user.

Per frame, record the same handful of HUD facts (status line, mode, point
counters, any warning) plus the geometry verdict. Cross-image agreement is what
turns an impression into a diagnosis: the same defect in every frame is a
systemic bug in the pipeline, while one odd frame is a bad scan. When the
counters disagree with what is drawn (a few hundred points reported over
thousands of visible quads), say which counter the HUD actually shows — often
it is the minimap, not the scene.

## Logging in the app that stays readable

- `Application.SetStackTraceLogType(LogType.Log, StackTraceLogType.None)` and
  the same for `Warning`; otherwise every single `Debug.Log` drags ~30 stack
  lines into logcat and the useful line is lost. Keep stacks for errors.
- One tag for everything (`[ARS] area | key=value`) so a single grep returns
  the whole run.
- Mirror each line into a file under `Application.persistentDataPath`, written
  synchronously and appended: a buffer never flushes when the process is killed
  by a native abort, so the file is the only trail that survives that crash.
- Emit a heartbeat (elapsed, phase, progress, network status) once a second and
  a one-shot snapshot of subsystem presence at startup — not a line per frame.
