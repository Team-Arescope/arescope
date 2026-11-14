Verified 2026-11-14 inside `unity/arescope-quest/`.

Executed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Scripts/run-core-tests.ps1
py -B Scripts/Verification/verify_project.py
```

- **22 C# tests passed, 0 failed.** Compiled the dependency-free
  `Assets/Arescope/Math/CoreMath.cs` and the same test methods used by NUnit with
  Windows .NET Framework `csc.exe`, then executed the console runner. Coverage:
  UT-01 mode availability/cycling; UT-02 median-edge filtering, rejection counts,
  non-finite coordinates and hostile topology; UT-03 inclusive height band,
  head-relative projection/range and signed voxel keys; UT-04 exact little-endian
  v1/v2 packing, every truncation, malformed headers/counts/indices and body cap;
  capture-frame translation/yaw, matrix inversion and delta threshold.
- **9 Python checks passed.** Byte equality for four archived configs, six icons
  and three license payloads; PNG dimensions and manifest parsing; project fields;
  serialized XR links/start flags/lifecycle priority; GUID uniqueness; Python/JSON
  syntax; repeatable RoomScan bridge installation, assembly dependency and Unity
  6000.2 API patch; Linux patch idempotency while preserving ARM64 validation;
  UTF-8/BOM/UTF-16LE/UTF-16BE logcat decoding and XR failure classification.
- XR script GUIDs/layouts were inspected in official Unity package tarballs;
  RoomScan APIs/layouts were inspected at the manifest's pinned Git commit.
  The source inventory includes SHA-256 values for all byte-preserved payloads.

Only the requested project subtree was written by this task. The separate
`Assets/ArescopeClient/`, `Assets/ArescopeHud/`, `Assets/Editor/`, root README,
HUD-PREVIEW, repository `archive/`, `.agents/` and `services/` were not edited.
The expressly requested nested README files are included.

Unity import, shader compilation, Android build and Quest hardware acceptance
were **not run**: no Unity editor or headset was available locally.

The exact archived manifest/lock omit `com.unity.xr.meta-openxr` and its
composition-layers dependency. Required feature subassets are serialized and
enabled with the official package GUIDs, but those Meta classes cannot resolve
until the integration owner deliberately installs the provider and revalidates
package compatibility. The archive's 2.4.1 provider recipe upgrades AR Foundation;
the copied files were kept byte-identical as requested. Native binaries and font
binaries are not present in the evidence and were not fabricated. See the scoped
README files for provisioning and packaging requirements.
