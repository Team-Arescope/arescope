# 20 · Спецификация runtime-компонентов и интерфейсов

Данный документ задаёт внешний контракт каждого компонента. Он намеренно не содержит исходных файлов, рабочих классов или полной реализации. [ПРОВЕРЕНО: архивная политика]

## Runtime component inventory

Все параметры в таблице извлечены из исходников; это значения по умолчанию, пока scene override не проверен. [ПРОВЕРЕНО: source inspection]; runtime outcome remains [ТРЕБУЕТ ПРОВЕРКИ]

| Компонент | Входы | Выходы/эффект | Точные параметры | Ошибки/логирование |
|---|---|---|---|---|
| `ARSessionBootstrap` | Unity start, XR device active, ARSession/AROcclusionManager | ждёт XR, при отсутствующем subsystem пересоздаёт ARSession | settle delay 0.6 s; wait до 15 s; after restart settle ещё 0.6 s | `[ARS] xr-boot` сообщает состояния manager/subsystem |
| `ScanModeBridge` | LeftHand primary/secondary button | scan start/finalize, passthrough/view cycle, reset | Y hold 1.2 s; read max 200,000 vertices, default max indices 600,000 | HUD errors; `[ARS] scan`, `[ARS] view` |
| `ArescopeFrame` | RoomAnchorManager matrix | capture/current relocation matrix; updates visual root | matrix element delta threshold 0.0005; relocation `A_now * inverse(A_capture)` | `[ARS] frame` capture/relocated |
| `ArescopeMeshExport` | GPU buffers + counters | managed positions/colours/indices | stride 48; offsets 0/24/36; caller max vertices/index; median edge multiplier 4; clamp 0.06..0.30 m | LastReason, kept/rejected triangle counters |
| `LiveScanPoints` | ArescopeLiveCloud sample + camera | accumulated point mesh | 6000 sample array; 0.2 s interval; voxel 0.035 m; cache 60,000; render cap 16,000; point size 0.0045 m; range 9 m | logs empty readback, anchor moves; culls based on camera if assigned |
| `LiveScanMinimap` | Live cloud or finalized mesh, headset transform | 2D map point list to HUD | height ±0.03 m; range 10 m; interval 1.5 s; 768 sample array; max display 96; mesh sample budget 20,000 | empty mesh result currently only yields no new point set; explicit stale-map policy needs definition |
| `ScanWireframe` | finalized Mesh | line-list renderer + billboard point renderer | 200,000 triangles budget; 12,000 point budget; 6 mm point diameter; line alpha .25, point alpha .55 | missing/empty mesh or missing shader warnings |
| `LiveFrameSender` | sampled GPU vertices, head pose, room label | HTTPS POST point frame | 3 s interval; 384 point max; 10 m range; vertical ±1.4 m; timeout 8 s | static status: HTTP code, success, stored, throttled, session ID |
| `MeshUploader` | RoomReady, GPU/refined mesh, last session ID | ARSM v2 textured mesh preferred, v1 vertex-colour fallback | collect delay 1.2 s; max vertices 400,000; body ≤32 MiB; HTTP timeout 60 s | `LastResult`: token missing/no session/empty/HTTP/etc. |
| `ArescopeLog` | runtime event | Unity logcat + rolling file | `[ARS]`; file rotates after 512 KiB to `.1`; Snapshot concatenates rotated/current files and keeps at most 2,000,000 .NET string characters | [ПРОВЕРЕНО: source; UTF-8 byte count differs; Log/Warning stacks suppressed, Error keeps script stack] |
| `LogUploader` | application pause, X+Y, crash marker on startup | POST text logs | X+Y 2 s; snapshot at most 2,000,000 chars; HTTP timeout 25 s; server cap 8 MiB | [ПРОВЕРЕНО: source; pause/combo/crash-recovery labels; OnApplicationQuit only removes marker, no upload] |
| `HudContrast` | passthrough provider current frame + per-panel viewport rect | panel backdrop alpha | sample 32×32; nominal 1 s; luma 0.62; bright fraction 0.70; alpha normal 0.25/dark 0.48 | no-frame warning once; async readback errors silent beyond return |
| `ArescopeHudController` | target camera, HUD events, map points, settings | overlay display/status/map/voice | follow distance 0.62 m; smoothing 14; panel x offsets ±150; fonts sizes 12/14/16/20 | exact canvas dimensions and colors need resource-level capture |
| `CopilotClient` | microphone, PTT input, settings | ASR→LLM SSE→TTS, state events | sample 16 kHz; default max recording 60 s (clamp to 120); request timeout 45 s default; max response 2 MiB | `CopilotState` event, transcript and error events |

[ПРОВЕРЕНО: serialized defaults/current source fields; runtime/prefab overrides must be enumerated before exact reproduction]

## Interface definitions (signatures only; illustrative)

- Scan flow: `StartOrFinishScan()` receives no external data; reads singleton scan session and controller edge. [ПРОВЕРЕНО: behavior spec]
- Mesh export: `ReadAsync(maxVertices,maxIndices,maxEdge) → {Positions,Colors,Indices,VertexCount,IndexCount}` or null + failure reason. [ПРОВЕРЕНО: interface contract]
- Live cloud: `SampleAsync(positionBuffer,colorBuffer,maxPoints) → count`. [ПРОВЕРЕНО]
- View control: `Switch(Passthrough|Mixed|Scan)` shall not report success if required camera/layer/mesh unavailable. [ПРОВЕРЕНО: `ViewModeController` behavior]
- Minimap: `SetMesh(mesh|null)` selects finalized mesh input or returns to live sample source. [ПРОВЕРЕНО: 0.5.12 spec]
- Mesh upload: `UploadAsync()` uses last session id from frame sender and suppresses duplicate session upload. [ПРОВЕРЕНО: source]
- Log upload: `UploadAsync(source)` supports `pause`, `combo`, `crash-recovery` and device source values. [ПРОВЕРЕНО]

## HUD visual layout details

- Camera-follow surface follows head at 0.62 m, Hard or Smooth; smoothing factor 14. [ПРОВЕРЕНО: ArescopeHudController source defaults]
- Panel horizontal offsets: map/assistant at -150; voice/status/event at +150 (local canvas layout units). [ПРОВЕРЕНО: source]
- Text font sizes: assistant 20, map 14, general panel 16, compass labels 12. [ПРОВЕРЕНО: source]
- Font asset names, exact font files, canvas scale factor, canvas dimensions, per-panel widths/heights, icon GUIDs: данных нет в spec; inspect scene/assets to recover. [ТРЕБУЕТСЯ]

## Startup dependency order

```text
Unity scene load
  → Meta XR/OpenXR instance activation
  → ARSessionBootstrap waits for XR up to 15 s
  → ARSession/AROcclusionManager subsystem check
  → RoomScanSession + VolumeIntegrator + MeshExtractor initialize
  → Arescope scene object references bind
  → user starts scan
```

- The sequence is a dependency model inferred from components; exact Unity script execution order and lifecycle callback order are not fully configured/documented here. [ПРЕДПОЛОЖЕНИЕ]
