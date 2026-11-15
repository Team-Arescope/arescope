#!/usr/bin/env python3
"""Export a browser capture as a verified, silent, exactly 30-second demo.

Run on the cloud computer with ffmpeg (libx264) and ffprobe installed. Python
dependencies are standard-library only; captions must already be in the capture.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SECONDS = 30
FPS = 30
FRAMES = SECONDS * FPS
WIDTH, HEIGHT = 1920, 1080
THREADS = "4"


def seconds(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("Use a number of seconds.") from exc
    if not result.is_finite() or result < 0:
        raise argparse.ArgumentTypeError("Seconds must be finite and nonnegative.")
    return result


def run(command: list[str], timeout: int = 600) -> str:
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-3000:]
        raise RuntimeError(f"{Path(command[0]).name} failed: {detail}")
    return result.stdout


def verify_video(ffprobe: str, path: Path) -> dict:
    probe = json.loads(run([
        ffprobe, "-v", "error", "-threads", THREADS, "-count_frames",
        "-show_streams", "-show_format", "-of", "json", str(path),
    ], timeout=120))
    streams = probe.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_type") != "video":
        raise RuntimeError("Export must contain exactly one video stream and no audio.")
    video = streams[0]
    duration = Decimal(probe.get("format", {}).get("duration", "0"))
    frame_count = int(video.get("nb_read_frames", "0"))
    if abs(duration - SECONDS) > Decimal("0.0005") or frame_count != FRAMES:
        raise RuntimeError(
            f"Capture is too short or timestamps are invalid: exported {duration}s, "
            f"{frame_count} frames; required 30.000s, 900 frames. "
            "Record at least 30 seconds after --start."
        )
    if (
        video.get("width") != WIDTH or video.get("height") != HEIGHT
        or video.get("codec_name") != "h264"
        or video.get("pix_fmt") != "yuv420p"
        or video.get("avg_frame_rate") != "30/1"
        or video.get("sample_aspect_ratio") != "1:1"
    ):
        raise RuntimeError("Export does not match 1920x1080, 30fps, H.264/yuv420p.")
    return {
        "duration_seconds": float(duration), "frames": frame_count,
        "width": WIDTH, "height": HEIGHT, "fps": FPS,
        "codec": "h264", "pixel_format": "yuv420p", "audio": False,
    }


def publish(staged: Path, destination: Path, overwrite: bool) -> None:
    if overwrite:
        os.replace(staged, destination)
    else:
        # Both paths are on the same filesystem. link() publishes the completed
        # file atomically and fails if another process has created destination.
        os.link(staged, destination)
        staged.unlink()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--input", required=True, type=Path, help="Browser WebM capture.")
    result.add_argument("--output", required=True, type=Path, help="Final .mp4 path.")
    result.add_argument("--start", type=seconds, default=Decimal(0),
                        help="Seconds to skip before the demo begins (default: 0).")
    result.add_argument("--duration", type=seconds, default=Decimal(SECONDS),
                        help="Must be 30; other durations are rejected.")
    result.add_argument("--poster", type=Path, help="Optional .png poster path.")
    result.add_argument("--poster-at", type=seconds, default=Decimal(18),
                        help="Poster time relative to the exported video (default: 18).")
    result.add_argument("--contact-sheet", type=Path,
                        help="Optional .png strip: frames at 2, 8, 16, 23 and 28 seconds.")
    result.add_argument("--overwrite", action="store_true",
                        help="Explicitly allow replacing existing output files.")
    return result


def export(args: argparse.Namespace) -> dict:
    if args.duration != SECONDS:
        raise ValueError("This demo must be exactly 30 seconds; use --duration 30.")
    if args.poster_at >= SECONDS:
        raise ValueError("--poster-at must be less than 30 seconds.")
    source = args.input.expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("--input must be a file.")
    outputs = {"output": args.output, "poster": args.poster,
               "contact_sheet": args.contact_sheet}
    targets = {key: value.expanduser().absolute()
               for key, value in outputs.items() if value is not None}
    seen = {source}
    for key, target in targets.items():
        expected = ".mp4" if key == "output" else ".png"
        if target.suffix.lower() != expected:
            raise ValueError(f"{key} must have the {expected} extension.")
        resolved = target.resolve()
        if resolved in seen or (target.exists() and target.samefile(source)):
            raise ValueError("Input and output artifact paths must all be distinct.")
        seen.add(resolved)
        if target.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists; pass --overwrite to replace: {target}")
        if target.exists() and not target.is_file():
            raise ValueError(f"Output is not a file: {target}")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("Install ffmpeg (with libx264) and ffprobe on the cloud computer.")

    with ExitStack() as stack:
        staged = {}
        for key, target in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            folder = Path(stack.enter_context(tempfile.TemporaryDirectory(
                prefix=".fleet-export-", dir=target.parent,
            )))
            staged[key] = folder / target.name
        base = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
        run(base + [
            "-threads", THREADS, "-filter_threads", THREADS,
            "-ss", str(args.start), "-i", str(source),
            "-map", "0:v:0", "-an", "-sn", "-dn",
            "-vf", "setpts=PTS-STARTPTS,fps=30,"
            "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p",
            "-frames:v", str(FRAMES), "-t", str(SECONDS),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-threads", THREADS, "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-map_metadata", "-1", "-map_chapters", "-1",
            str(staged["output"]),
        ])
        info = verify_video(ffprobe, staged["output"])
        if "poster" in staged:
            run(base + [
                "-threads", THREADS, "-filter_threads", THREADS,
                "-ss", str(args.poster_at), "-i", str(staged["output"]),
                "-map", "0:v:0", "-frames:v", "1", "-threads", THREADS,
                "-update", "1", str(staged["poster"]),
            ])
        if "contact_sheet" in staged:
            run(base + [
                "-threads", THREADS, "-filter_threads", THREADS,
                "-i", str(staged["output"]), "-map", "0:v:0",
                "-vf", "select='eq(n,60)+eq(n,240)+eq(n,480)+eq(n,690)+eq(n,840)',"
                "scale=384:216,tile=5x1",
                "-frames:v", "1", "-threads", THREADS, "-update", "1",
                str(staged["contact_sheet"]),
            ])
        for key, destination in targets.items():
            publish(staged[key], destination, args.overwrite)
        return {"ok": True, **info,
                **{key: str(value) for key, value in targets.items()},
                "bytes": targets["output"].stat().st_size}


def main() -> int:
    args = parser().parse_args()
    try:
        print(json.dumps(export(args), ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
