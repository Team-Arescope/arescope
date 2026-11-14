# Testing Quest builds without the headset

## Hardware facts that decide the plan

- Meta **Depth API is supported on Quest 3, Quest 3S and Meta VR Glasses**. Do not describe the 3S as lacking depth.
- Quest 3S sensor cluster (each side): passthrough RGB camera, tracking camera, IR illuminator. Depth comes from the stereo RGB pair, so the realistic risk is depth quality, latency and scan cost, not a missing sensor.
- The IR illuminators explain the 3S tracking better in the dark than Quest 3; that says nothing about scan quality.

## Meta XR Simulator

An OpenXR runtime for the desktop that presents a Quest device profile to the app. No Android layer, so it runs the Unity app or a PC build — never an APK.

- Device profiles: Quest 2, Quest Pro, Quest 3, Quest 3S, VR Glasses.
- Synthetic environments stand in for a physical room and supply passthrough imagery, scene data (walls, floor, ceiling, furniture, doors, windows), spatial anchors, and environment depth. Without a synthetic environment an MR app has no "physical world".
- Environment depth in the simulator is **Windows only**, on the Quest 3 / 3S / VR Glasses profiles.
- Input: keyboard, mouse, physical controllers via data forwarding, Xbox controller on Windows. Tracking can be toggled independently.
- Session capture: record to VRS and replay, which makes a bug tied to head or hand motion repeatable.
- Requirements: OpenXR 1.0–1.1, Vulkan (Windows/macOS), D3D11/D3D12 (Windows) or Metal (macOS); OpenGL/ES unsupported. Old Meta Core SDK versions may not work — if the package misbehaves, remove `com.meta.xr.simulator` and select the simulator as the active OpenXR runtime instead.
- Docs: `https://developers.meta.com/vr/documentation/unity/xrsim-intro/`, inputs `…/xrsim-input-keyboard/`, synthetic rooms `…/xrsim-heroscenes/`, depth `…/unity-depthapi-overview/`.

## What the desk setup buys and what it does not

Covered without a headset: HUD layout and clipping, controller edge detection, PTT state machine, streaming client wiring, server round trips, scene logic against synthetic depth and room data, repeatable motion replays.

Still needs the headset: APK install and launcher, AppCompat/manifest behaviour, lens legibility and IPD, real depth noise and scan performance, XR2 thermals and framerate, microphone and audio path, tracking loss and comfort.

Hardware floor: a GTX 1650 laptop is enough because the simulator renders one window, not two eyes at 90 Hz. Kepler-era laptop GPUs (GT 750M class) are not usable. Simulator framerate says nothing about headset framerate.

## Producing the PC build on the Linux InstaBox

1. Install the Windows build module once: `/data/home/.local/bin/unity install-modules -e 6000.2.9f1 -m windows-mono --accept-eula -y` (the editor shipped with only `AndroidPlayer`; without `WindowsStandaloneSupport` the Standalone target is unsupported and the batch run aborts before `-executeMethod`).
2. Free disk first: kill orphan Unity/Licensing/ILPP processes, clear `Library/Bee|Artifacts|BurstCache|ShaderCache|ScriptAssemblies` + gradle caches, check `df -h /data`.
3. Build: `DISPLAY=:1 Unity -batchmode -projectPath /data/home/unity/arescope-beta02 -executeMethod BuildSimPc.Build -logFile …` (script: `Assets/Editor/BuildSimPc.cs`, output `Build/SimPC/`, Mono2x, no `SetArchitecture` call — not in 6000.2).
4. Pack `tar -czf arescope-sim-pc.tar.gz -C Build SimPC`, publish with `publish-shared`, verify SHA-256 by re-downloading.
5. On the Windows laptop: install Meta XR Simulator, pick the Quest 3S profile in the tray, unpack, run `ArescopeBeta03.exe`. Synthetic rooms (with environment depth) are selected inside the simulator; input via keyboard/mouse/gamepad.

## Unity-only alternatives

- **XR Device Simulator** (XR Interaction Toolkit) — drives head and hands in Play Mode, appropriate when the project uses XRI rather than Meta XR SDK.
- **XR Simulation** (AR Foundation) — editor AR environments; useful for AR Foundation scenes only.
