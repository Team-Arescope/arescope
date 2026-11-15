# Thirty-second fleet demonstration

`Arescope-Fleet-Demo-30s.mp4` is a silent 1920 × 1080 H.264 video, exactly
30 seconds / 900 frames, with English captions. It shows surveying, a simulated
wheel obstruction, autonomous assistance, Guardian validation and resumed work.

This replaces the earlier uneven real-time screen recording. Every frame is
rendered independently from its presentation timestamp, using the LAB's actual
Terrain class, rover geometry, depth passes and service contact solver. Models,
camera, wheel rotation, tool motion and captions use that same clock. Rendering
and H.264 encoding run on the cloud computer, with no wall-clock video capture.

FleetSimManager and GuardianEngine generate the source states on archived
HiRISE terrain. Initial adjacent survey lanes are staged; authoritative trail
segments are resampled for presentation, with accelerated and edited phase
timing. Minor-fault service and Guardian clearance use the actual simulator.
This is a synthetic service scenario, not a hardware repair recording. The
offline capture has a simplified presentation overlay rather than the full
interactive LAB chrome. Production mission state is not changed.

The visible footer and MP4 metadata disclose AI-assisted software, simulated
recovery and the NASA archive. The PNG is a preview frame.

Public video: https://arescope.mrfenek.eu.cc/static/demo/Arescope-Fleet-Demo-30s.mp4

Reproduction, on the cloud computer with LAB Python dependencies, Playwright
1.56.1, Chromium, FFmpeg and Pillow installed:

```bash
python3 scripts/generate_fleet_demo_story.py --root services/arescope-lab --output /tmp/arescope-story.json
node scripts/render_fleet_demo.cjs --root services/arescope-lab --story /tmp/arescope-story.json --out /tmp/arescope-frames --fps 30
python3 scripts/encode_fleet_frames.py --frames /tmp/arescope-frames --output /tmp/Arescope-Fleet-Demo-30s.mp4
```

Add `--preview-only` to the renderer to inspect six key frames first. Its
`validation.json` records per-frame poses, projections, wheel/arm state,
service contact, camera continuity and reproducibility checks.

The older `scripts/export_fleet_demo.py` remains available for real-time captures.
