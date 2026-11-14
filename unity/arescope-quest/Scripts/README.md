Use Unity 6000.2.9f1 (e0c4e791ab71). Project settings target Android ARM64,
IL2CPP, API 29, Linear color, version 0.5.13 / code 34.

Run standalone algorithm tests on Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Scripts/run-core-tests.ps1
```

This compiles Assets/Arescope/Math/CoreMath.cs and the exact Unity test methods
with .NET Framework csc.exe. The tiny NUnit attribute shim is enabled only under
ARESCOPE_STANDALONE. In Unity, use Arescope.Tests in the EditMode Test Runner.

After package resolution, install the three internal API adapters:

```text
py Scripts/patch_roomscan_editor.py Library/PackageCache/com.genesis.roomscan@HASH
py Scripts/patch_roomscan_editor.py Library/PackageCache/com.genesis.roomscan@HASH --check
py Scripts/patch_meta_sdk_linux.py
py Scripts/triage_logcat.py captured-logcat.txt
```

The first script validates the pinned GPU layout, copies all bridge .cs/.meta
files into the vendor assembly, adds its Arescope.Core assembly reference and
supplies Unity 6000.2's required FindObjectsSortMode argument in vendor lookups.
It never grants InternalsVisibleTo to Assembly-CSharp. Repeat after re-resolution.
The Linux patcher reports unknown layouts; it preserves architecture validation.
The shell triage wrapper uses the same UTF-8/UTF-16 decoder as the Python command.

The required archive package manifest and lock are byte-identical snapshots.
They do NOT include com.unity.xr.meta-openxr or compositionlayers, despite the
requested serialized features. Those feature subassets reference their official
package script GUIDs and remain unresolved until the integration owner deliberately
adds the Meta provider (archived recommendation 2.4.1; it upgrades AR Foundation
to 6.4 and adds compositionlayers 2.2). No silent dependency upgrade is performed.
Copy native libraries as described in Assets/Plugins/Android/arm64-v8a/README.md.
Refresh Android features and revalidate the imported assets before building.

Create actual Resources/arescope-endpoint.txt and arescope-live-token.txt only via
deployment provisioning. The .example resources are never loaded by the runtime.
Endpoint accepts a plain HTTPS origin or JSON with baseUrl/origin/endpoint.
The producer token is distinct from Copilot and viewer credentials.

The serialized build scene is owned by the scene agent. Its wiring must reference
the public fields in Assets/Arescope; call Configure and apply the actual starting
mode. Finalization snapshots GPU/refined data before StopScanning, then uploads
the CPU snapshot. ArescopeFrame assumes exported capture-world coordinates and
applies A_now * inverse(A_capture) once; scale is forced to one. Validate that
coordinate contract on the headset across relocalization.

No Unity editor or Quest device was present for authoring. Standalone tests and
static checks do not establish XR startup, shader import, performance, scene wiring,
camera projection accuracy, native packaging or headset acceptance.
