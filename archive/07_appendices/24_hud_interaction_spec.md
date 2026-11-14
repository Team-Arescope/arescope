# 24 · HUD, взаимодействие и визуальные состояния

## HUD panels

Шесть логических панелей, создаваемых `ArescopeHudPanel`: `status`, `event`, `map`, `assistant`, `compass`, `voice`. [ПРОВЕРЕНО: key list]

| Panel | Size (canvas units) | Position offsets | Font | Purpose/state |
|---|---:|---:|---|---|
| status | 300×146 | x +150, y -36 | Sans 16, header 14 | scan status, progress, uplink, power; status rows |
| event | 260×64 | x +150, y +140 | Sans 16 | transient event; hidden when empty |
| map | 240×240 circle | x -150, y -36 | Sans 14 | local map ±10 m; max 64 standard points or 192 when scanCloud mode enabled |
| assistant | 420×155 | x -150, y +84 | Sans 20 | Copilot response |
| compass | 360×86 | centered top | Mono 12 labels/ticks | 8-point compass and 5° ticks |
| voice | 240×46 | x +150, y +84 | Mono 16 | voice capture state/level |

[ПРОВЕРЕНО: `ArescopeHudController.cs` fields/layout. Canvas units are implementation units, not physical mm]

## Color and typography

- Ink `#100B09`, Paper `#F5E8DF`, Muted `#A2948C`, Rule `#513026`, Copper `#EE8A5B`. [ПРОВЕРЕНО: color constants]
- Font resource IDs: `ArescopeFonts/Manrope-SemiBold`, `ArescopeFonts/DMMono-Medium`; fallback to Unity `LegacyRuntime.ttf` then Sans. [ПРОВЕРЕНО: resource loads]
- Card alpha starts at 0.25; copper top rule height 2 canvas units; shadow black alpha 0.72 with offset `(1,-1)`. [ПРОВЕРЕНО: defaults]
- Panel sizes/offsets are screen-canvas design units; physical rendered angular extent must be measured in headset. [ТРЕБУЕТ ПРОВЕРКИ]

## HUD follow transform

- HUD code default follow distance is 0.62 m, but serialized current scene overrides it to 1.15 m; for recreating the inspected scene, 1.15 m is the effective setting unless the build-time wiring helper rewrites it (no such rewrite was found). [ПРОВЕРЕНО: controller default + scene YAML + helper inspection]
- Panel horizontal offsets: map/assistant at -150; voice/status/event at +150; compass centered. [ПРОВЕРЕНО: source layout]
- Follow smoothing default is 14; mode default Smooth; Hard mode sets blend factor 1. [ПРОВЕРЕНО: controller default; effective scene enum value 0 needs enum map check]
- HUD FOV bounds use current camera vertical field of view to compute visible half-height. [ПРОВЕРЕНО: source helper]
- Behaviour when user turns sharply, re-centers, or enters passthrough Mixed mode needs headset QA. [ТРЕБУЕТ ПРОВЕРКИ]

## Status data strings and uplink

- Status refresh interval `0.5 s`. [ПРОВЕРЕНО]
- Frame sender exposes `LastStatusCode`, `LastSuccessAt`, `LastStored`, `LastThrottled`, `LastSuccess`, `LastSessionId`. [ПРОВЕРЕНО]
- Historical UX string forms include `UPLINK WAITING`, HTTP age, `UPLINK TIMEOUT`, `UPLINK 401 AUTH`; exact current label mapping must be verified against current HUD source and screenshot. [ПРОВЕРЕНО: previous UI behavior; [ТРЕБУЕТ ПРОВЕРКИ] exact current wording]
- Battery row currently reads from Unity/SystemInfo or HUD data source; exact calculation/source must be audited. [ТРЕБУЕТ ПРОВЕРКИ]

## Minimap coordinate conversion

```text
origin = current headset position
forward = normalize(project(headset.forward, horizontal plane))
right = cross(worldUp, forward)
delta = point - origin
accept if |delta.y| <= 0.03 m
mapX = dot(delta,right)
mapY = dot(delta,forward)
accept if mapX² + mapY² <= 10² m²
```

[ПРОВЕРЕНО: `LiveScanMinimap.cs` logic; screen projection scale in HUD uses `74 canvas units / 10 m` and map center y=-20.]

## Backdrop adaptation

- Per-panel sampling uses each panel RectTransform projected into viewport; samples a 32×32 downsampled passthrough frame. [ПРОВЕРЕНО]
- Luminance weights: 0.2126 red, 0.7152 green, 0.0722 blue, normalized by 255. [ПРОВЕРЕНО]
- Panel darkens when ≥70% of sample pixels have luminance ≥0.62; alpha changes from 0.25 to 0.48. [ПРОВЕРЕНО]
- Update interval nominally 1 s; readback uses async GPU request. [ПРОВЕРЕНО]
- Threshold/hysteresis only changes state when boolean flips; no separate hysteresis band is present. [ПРОВЕРЕНО]
- Camera/viewport mismatch, texture rotation, panel projection and luminance under actual passthrough need testing. [ТРЕБУЕТ ПРОВЕРКИ]
