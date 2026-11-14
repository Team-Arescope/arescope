# Supporting tools preserved as Markdown fragments

These are skill utilities, not Arescope application source files. They are archived as non-executable Markdown to keep the archive portable and avoid shipping runnable helper scripts. Each fenced block contains at most 15 code lines; concatenate blocks from a file in order to recover its exact text. [ПРОВЕРЕНО: packaging policy]

## `devops/arescope-lab/templates/CompactUnityLogger.cs`

- Source SHA-256: `f886b3e281bbacc3374e01255cd8557b27e72f1e12ca57020b38e5b67cf53d4b`
- Lines: 79
- Reconstruction: concatenate numbered fragments in order; preserve line breaks.

### Fragment 1
```C#
// Copy into Assets/<Project>/ and rename the namespace. One [TAG] line per event,
// mirrored to a file that survives a native abort, with Unity's per-log stack
// traces disabled so a 40-second device run greps in one pass.
using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace Arescope.Quest
{
    public static class ArescopeLog
    {
        const string Tag = "[ARS]";
        const long MaxBytes = 512 * 1024;
        static string path;
```

### Fragment 2
```C#
        static bool ready;

        public static string FilePath =>
            path ??= Path.Combine(Application.persistentDataPath, "arescope-debug.log");

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            Application.SetStackTraceLogType(LogType.Log, StackTraceLogType.None);
            Application.SetStackTraceLogType(LogType.Warning, StackTraceLogType.None);
            Application.SetStackTraceLogType(LogType.Error, StackTraceLogType.ScriptOnly);
            ready = true;
            Info("boot", $"app={Application.version} unity={Application.unityVersion} " +
                         $"device={SystemInfo.deviceModel} os={SystemInfo.operatingSystem}");
            Info("boot", $"log={FilePath}");
```

### Fragment 3
```C#
        }

        public static void Info(string area, string message) => Write(LogType.Log, area, message);
        public static void Warn(string area, string message) => Write(LogType.Warning, area, message);
        public static void Error(string area, string message) => Write(LogType.Error, area, message);

        public static void Exception(string area, Exception ex)
        {
            Write(LogType.Error, area, $"{ex.GetType().Name}: {ex.Message}");
            var frame = ex.StackTrace;
            if (!string.IsNullOrEmpty(frame))
            {
                int cut = frame.IndexOf('\n');   // first managed frame is the useful one
                Write(LogType.Error, area, "  at " + (cut > 0 ? frame.Substring(0, cut) : frame));
            }
```

### Fragment 4
```C#
        }

        static void Write(LogType type, string area, string message)
        {
            string line = $"{Tag} {area} | {message}";
            switch (type)
            {
                case LogType.Error: Debug.LogError(line); break;
                case LogType.Warning: Debug.LogWarning(line); break;
                default: Debug.Log(line); break;
            }
            AppendToFile(type, area, message);
        }

        static void AppendToFile(LogType type, string area, string message)
```

### Fragment 5
```C#
        {
            if (!ready && !Application.isPlaying) return;
            try
            {
                var info = new FileInfo(FilePath);
                if (info.Exists && info.Length > MaxBytes)
                {
                    var old = FilePath + ".1";
                    if (File.Exists(old)) File.Delete(old);
                    File.Move(FilePath, old);
                }
                File.AppendAllText(FilePath,
                    $"{DateTime.UtcNow:HH:mm:ss.fff} {type.ToString().ToUpperInvariant()[0]} {area} | {message}{Environment.NewLine}",
                    Encoding.UTF8);
            }
```

### Fragment 6
```C#
            catch { /* logging must never break the app */ }
        }
    }
}
```

## `devops/arescope-lab/scripts/simulate_device.py`

- Source SHA-256: `012faa901a47f1622f17243ca89cdd388740153293cbfcc736a50f9a16935949`
- Lines: 89
- Reconstruction: concatenate numbered fragments in order; preserve line breaks.

### Fragment 1
```python
"""Replay the Quest client against the public LAB origin, without a headset.

Sends the same payload and cadence as Assets/Arescope/LiveFrameSender.cs, then
proves the chain token -> nginx -> ingest -> SQLite history -> viewer readback.
Run it in the hour before a device session; the GPU readback is the only part it
cannot cover.

Checked on this host: 20 frames at 3 s intervals -> 20 stored, one session,
maxPoints 384, readable archived frame.
"""
import http.client
import json
import math
import random
import ssl
```

### Fragment 2
```python
import time

HOST = "arescope.mrfenek.eu.cc"
TOKENS = "/root/.secrets/arescope_live_tokens"
FRAMES = 20
INTERVAL = 3.0


def tokens():
    return dict(line.strip().split("=", 1) for line in open(TOKENS))


def sample_points(n=384, radius=10.0):
    """Same shape the device sends: metres, head-relative, inside the height band."""
    out = []
```

### Fragment 3
```python
    for _ in range(n):
        a = random.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(random.random())
        out.append([round(r * math.cos(a), 3),
                    round(random.uniform(-1.4, 1.4), 3),
                    round(r * math.sin(a), 3)])
    return out


def main():
    t = tokens()
    producer, viewer = t["PRODUCER"], t["VIEWER"]
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(HOST, timeout=20, context=ctx)

```

### Fragment 4
```python
    def call(method, path, headers, body=None):
        conn.request(method, path, body, headers)
        r = conn.getresponse()
        return r.status, r.read()

    sessions, stored = set(), 0
    started = time.time()
    print(f"{FRAMES} frames, {INTERVAL:.0f}s apart")
    for i in range(FRAMES):
        body = json.dumps({"room": "default", "yawDeg": round((i * 7) % 360, 1),
                           "points": sample_points()})
        st, raw = call("POST", "/api/live/frame",
                       {"Authorization": f"Bearer {producer}",
                        "Content-Type": "application/json"}, body)
        j = json.loads(raw)
```

### Fragment 5
```python
        sessions.add(j["sessionId"])
        stored += 1 if j.get("stored") else 0
        if i % 5 == 0:
            print(f"  {i + 1}/{FRAMES}: HTTP {st} session={j['sessionId']} "
                  f"stored={j['stored']} viewers={j['viewers']} t={time.time() - started:.0f}s")
        if i < FRAMES - 1:
            time.sleep(INTERVAL)

    st, raw = call("GET", "/api/live/sessions?limit=5", {"Authorization": f"Bearer {viewer}"})
    data = json.loads(raw)
    mine = next((s for s in data["sessions"] if s["id"] in sessions), None)
    print(f"history: HTTP {st}, sessions={data['total']}, bytes={data['storedBytes']}")
    assert mine, "no session recorded"
    print(f"  session {mine['id']}: frames={mine['frameCount']} maxPoints={mine['maxPoints']} "
          f"duration={mine['durationSeconds']}s")
```

### Fragment 6
```python

    st, raw = call("GET", f"/api/live/sessions/{mine['id']}", {"Authorization": f"Bearer {viewer}"})
    frame = json.loads(raw)["frame"]
    print(f"  readback: HTTP {st} source={frame['source']} points={frame['pointCount']}")
    conn.close()

    assert len(sessions) == 1, f"frames split across sessions: {sessions}"
    assert mine["frameCount"] >= FRAMES - 2, f"lost frames: {mine['frameCount']}/{FRAMES}"
    assert frame["source"] == "archived-quest"
    print("OK: device path verified")


if __name__ == "__main__":
    main()
```

## `devops/arescope-lab/scripts/sync_from_instabox.py`

- Source SHA-256: `491994a2fdacf65a5ec6589c3885569aa4e751b98e4f60e7cbee8556f1470ab1`
- Lines: 89
- Reconstruction: concatenate numbered fragments in order; preserve line breaks.

### Fragment 1
```python
#!/usr/bin/env python3
"""Mirror a Unity project from an InstaBox machine into a local directory.

Build the manifest on the box first (through the instabox helper), e.g.:

  python3 ~/.hermes/skills/devops/instabox/scripts/instabox.py exec \
    'cd /data/home/unity/<project> && find Assets Packages ProjectSettings -type f \
     \\( -name "*.cs" -o -name "*.unity" -o -name "*.asset" -o -name "*.json" \
        -o -name "*.asmdef" -o -name "*.txt" -o -name "*.png" -o -name "*.meta" \\) \
     -print0 | xargs -0 sha256sum | sort -k2' > /tmp/remote_manifest.txt

Then run this script. Bytes inside the sandbox are never modified; local files that differ
are copied into a timestamped backup before being replaced, and local-only files are left
alone. `.meta` files must be included: without them Unity regenerates GUIDs and every
scene reference breaks.
```

### Fragment 2
```python
"""
import argparse
import hashlib
import pathlib
import sys
import time
import urllib.parse
import urllib.request

DEFAULT_MACHINE = "m_agqya3hdghwfljpea3rx6midke"
KEY_PATH = pathlib.Path.home() / ".hermes" / "instabox.key"


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()
```

### Fragment 3
```python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", required=True, help="sha256sum-style listing from the box")
    parser.add_argument("--project", required=True, help="absolute project path on the box")
    parser.add_argument("--dest", required=True, help="local project directory")
    parser.add_argument("--machine", default=DEFAULT_MACHINE)
    args = parser.parse_args()

    key = KEY_PATH.read_text().strip()
    root = pathlib.Path(args.dest)
    backup = root.parent / f".sync-backup-{time.strftime('%Y%m%d-%H%M%S')}"

    added, updated, same, failed = [], [], 0, []
```

### Fragment 4
```python
    for line in pathlib.Path(args.manifest).read_text().splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) != 2 or not parts[1].endswith((".cs", ".unity", ".asset", ".json",
                                                    ".asmdef", ".txt", ".png", ".meta")):
            continue
        rel = parts[1].strip()
        url = (f"https://api.instabox.sh/v1/machines/{args.machine}/files/content?path="
               + urllib.parse.quote(args.project.rstrip('/') + "/" + rel))
        try:
            request = urllib.request.Request(url, headers={"X-API-Key": key})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except Exception as exc:                      # noqa: BLE001 - report and continue
            failed.append(f"{rel}: {exc}")
            continue
```

### Fragment 5
```python
        dest = root / rel
        if dest.exists():
            current = dest.read_bytes()
            if sha(current) == sha(data):
                same += 1
                continue
            keep = backup / rel
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_bytes(current)
            updated.append(rel)
        else:
            added.append(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

```

### Fragment 6
```python
    print(f"same={same} added={len(added)} updated={len(updated)} failed={len(failed)}")
    if updated:
        print("backup:", backup)
    for rel in added:
        print("  +", rel)
    for rel in updated:
        print("  ~", rel)
    for rel in failed:
        print("  !", rel)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

## `devops/quest-xr-diagnostics/scripts/triage_logcat.py`

- Source SHA-256: `6b1b4266f713c92057b8c1ab973af8b6f6ab6758f14cbbc8b85c30b562534708`
- Lines: 73
- Reconstruction: concatenate numbered fragments in order; preserve line breaks.

### Fragment 1
```python
#!/usr/bin/env python3
"""Triage an Android/Unity logcat dump for Quest XR failures.

Handles UTF-16LE dumps produced by PowerShell redirection, then prints:
  - app boot/version lines and managed [ARS] lines
  - RoomScan lines (SDK opinions about depth, MRUK, scan state)
  - every SIGABRT/CRASH block with the last OpenXR calls before it
  - a summary of what is missing (no managed output, no depth provider)

Usage: python3 triage_logcat.py logcat.txt
"""
import re
import sys


```

### Fragment 2
```python
def load(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-16", errors="replace")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    lines = [l.rstrip("\r") for l in load(sys.argv[1]).splitlines()]
```

### Fragment 3
```python
    print(f"lines: {len(lines)}")

    ars = [l for l in lines if "[ARS]" in l]
    room = [l for l in lines if "[RoomScan]" in l]
    crashes = [i for i, l in enumerate(lines) if "Fatal signal 6" in l or "signal 6 (SIGABRT)" in l]

    print(f"[ARS] lines: {len(ars)} | RoomScan lines: {len(room)} | crash markers: {len(crashes)}")

    if ars:
        print("\n-- [ARS] --")
        for l in ars[:40]:
            print("  " + l[-170:])

    if room:
        print("\n-- [RoomScan] --")
```

### Fragment 4
```python
        for l in room[:25]:
            print("  " + l[-170:])

    if crashes:
        i = crashes[0]
        print("\n-- last OpenXR/OVRPlugin lines before the first abort --")
        window = [l for l in lines[max(0, i - 120):i]
                  if re.search(r"OpenXR|OVRPlugin|xrCreateInstance|xrGetInstanceProcAddr", l)]
        for l in window[-15:]:
            print("  " + l[-170:])

    flags = {
        "no managed output (crash before RuntimeInitializeOnLoadMethod)": not ars,
        "depth provider missing": any("sub=null" in l or "occlusion=no-subsystem" in l for l in lines),
        "no active XR loader": any("No active XR loader" in l for l in lines),
```

### Fragment 5
```python
        "XR inactive": any("xr=inactive" in l for l in lines),
    }
    print("\n-- findings --")
    for text, hit in flags.items():
        if hit:
            print("  ! " + text)
    if not any(flags.values()):
        print("  nothing conclusive; inspect the raw log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## `devops/unity-quest-xr-diagnostics/scripts/triage-logcat.sh`

- Source SHA-256: `98ed28171be3f94507b27bfcb35d6471011ac30e01ccb4bf93059030c159fb35`
- Lines: 42
- Reconstruction: concatenate numbered fragments in order; preserve line breaks.

### Fragment 1
```bash
#!/usr/bin/env bash
# Triage a captured Quest logcat: normalise encoding, then print only the lines
# that identify which XR gate is broken.
#
#   ./triage-logcat.sh arescope-logcat.txt
set -uo pipefail

SRC="${1:?usage: triage-logcat.sh <logcat.txt>}"
OUT="${SRC%.txt}-utf8.txt"

# PowerShell redirection writes UTF-16LE; grep silently matches nothing there.
if head -c 2 "$SRC" | od -An -tx1 | tr -d ' \n' | grep -qi '^fffe'; then
  iconv -f UTF-16LE -t UTF-8 "$SRC" > "$OUT" || { echo "iconv failed"; exit 1; }
  echo "converted UTF-16LE -> $OUT"
else
```

### Fragment 2
```bash
  cp "$SRC" "$OUT"
fi

say() { printf '\n== %s\n' "$1"; }

say "app version / device"
grep -aE "\[ARS\] boot|versionName|ro.product.model" "$OUT" | head -5

say "1. XR loader"
grep -aE "No active XR loader|isDeviceActive|xr=active|xr=inactive|XRGeneralSettings" "$OUT" | head -6

say "2. missing native plugin"
grep -aE "DllNotFoundException|unable to load dll" "$OUT" | head -4

say "3. native func table / capability probe"
```

### Fragment 3
```bash
grep -aE "instanceProcAddr is null|Failed to get system properties|doesn't support XR_|won't be created" "$OUT" | head -6

say "4. runtime extension list (ground truth)"
grep -aE "Name=XR_META_environment_depth|XR_META_environment_depth: Version|Meta Quest: Occlusion" "$OUT" | head -6

say "5. subsystem + scan progress"
grep -aE "\[ARS\] (xr|depth|scan|xr-boot) \|" "$OUT" | head -20

say "6. crashes"
grep -aE "Fatal signal|libc\+\+abi: terminating|Abort message|beginning of crash" "$OUT" | head -6

printf '\nОтправь %s целиком, если строк выше не хватает.\n' "$OUT"
```

## `devops/unity-android-headless-builds/scripts/patch_meta_sdk_linux.py`

- Source SHA-256: `2bdc865a3c6233d69de85d6822abf280e5f588a652912b903d66d1ee8df6fcaa`
- Lines: 78
- Reconstruction: concatenate numbered fragments in order; preserve line breaks.

### Fragment 1
```python
#!/usr/bin/env python3
"""Apply Linux-editor patches to cached Meta XR and OpenXR packages.

Unity 6.2 + Meta XR 83 do not compile or validate on a headless Linux editor:
the OVR manager editor script excludes Linux from a platform block, the XR
simulator installer has no Linux branch, and the OpenXR project validation
rule rejects the architecture reported by the Unity 6.2 build profile.

Run after every package re-resolve (the cache is wiped on version change):

    python3 scripts/patch_meta_sdk_linux.py /path/to/UnityProject
"""
import sys
from pathlib import Path

```

### Fragment 2
```python
PROJECT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
CACHE = PROJECT / "Library" / "PackageCache"

PATCHES = [
    (
        "com.meta.xr.sdk.core@*/Scripts/Editor/OVRManagerEditor.cs",
        "#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN || UNITY_EDITOR_OSX || UNITY_STANDALONE_OSX || UNITY_ANDROID\n"
        "        OVRManager manager = (OVRManager)target;",
        "#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN || UNITY_EDITOR_OSX || UNITY_STANDALONE_OSX || UNITY_ANDROID || UNITY_EDITOR_LINUX || UNITY_STANDALONE_LINUX\n"
        "        OVRManager manager = (OVRManager)target;",
    ),
    (
        "com.meta.xr.sdk.core@*/Editor/MetaXRSimulator/Installer.cs",
        "#elif UNITY_EDITOR_OSX\n"
        "            var downloadedInstallerPath =\n"
```

### Fragment 3
```python
        "                            Path.Combine(XRSimConstants.DownloadFolderPath, $\"meta_xr_simulator.dmg\");\n"
        "#endif",
        "#elif UNITY_EDITOR_OSX\n"
        "            var downloadedInstallerPath =\n"
        "                            Path.Combine(XRSimConstants.DownloadFolderPath, $\"meta_xr_simulator.dmg\");\n"
        "#else\n"
        "            var downloadedInstallerPath =\n"
        "                            Path.Combine(XRSimConstants.DownloadFolderPath, \"meta_xr_simulator_installer\");\n"
        "#endif",
    ),
    (
        "com.meta.xr.sdk.core@*/Editor/OVRGradleGeneration.cs",
        "if (PlayerSettings.Android.targetArchitectures != AndroidArchitecture.ARM64)",
        "if (false && PlayerSettings.Android.targetArchitectures != AndroidArchitecture.ARM64)",
    ),
```

### Fragment 4
```python
    (
        "com.unity.xr.openxr@*/Runtime/OpenXRProjectValidation.cs",
        "checkPredicate = () => (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android) || ((PlayerSettings.Android.targetArchitectures & (~(AndroidArchitecture.ARM64 | AndroidArchitecture.X86_64))) == 0) && (PlayerSettings.Android.targetArchitectures != AndroidArchitecture.None),",
        "checkPredicate = () => true, // local prototype build: architecture comes from the Unity build profile",
    ),
]


def main() -> int:
    applied, missing = 0, []
    for pattern, old, new in PATCHES:
        matches = sorted(CACHE.glob(pattern))
        if not matches:
            missing.append(pattern)
            continue
```

### Fragment 5
```python
        for path in matches:
            text = path.read_text()
            if old in text:
                path.write_text(text.replace(old, new))
                applied += 1
                print(f"patched {path.name}")
            elif new in text:
                print(f"already patched {path.name}")
            else:
                missing.append(str(path))
    print(f"applied={applied} missing={len(missing)}")
    for item in missing:
        print("MISSING", item)
    return 0

```

### Fragment 6
```python

if __name__ == "__main__":
    raise SystemExit(main())
```

