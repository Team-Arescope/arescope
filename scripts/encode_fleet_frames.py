#!/usr/bin/env python3
"""Encode the deterministic cloud-rendered LAB demo, without wall-clock capture."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(args):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    frames = [args.frames / f'{i:06d}.png' for i in range(900)]
    assert all(p.is_file() for p in frames), 'Expected all 900 numbered frames'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
         '-framerate', '30', '-start_number', '0', '-i', str(args.frames/'%06d.png'),
         '-an', '-frames:v', '900', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
         '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
         '-metadata', 'title=Arescope: Shared Mission Control for Mars Rover Teams',
         '-metadata', 'comment=Actual LAB renderer; AI-assisted software; synthetic rover recovery on archived NASA HiRISE terrain; accelerated scenario.',
         str(args.output)])
    info = json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                           '-show_format', '-of', 'json', str(args.output)]))
    assert len(info['streams']) == 1
    stream = info['streams'][0]
    assert stream['codec_name'] == 'h264' and stream['pix_fmt'] == 'yuv420p'
    assert stream['width'] == 1920 and stream['height'] == 1080
    assert stream['avg_frame_rate'] == '30/1' and int(stream['nb_read_frames']) == 900
    assert abs(float(info['format']['duration']) - 30) < .00001
    poster = args.output.with_suffix('.png')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-ss', '17',
         '-i', str(args.output), '-frames:v', '1', '-threads', '2', str(poster)])
    # A small contact sheet is for visual QA, not an extra submitted demo.
    sheet = args.output.with_name('Arescope-Fleet-Demo-Contact-Sheet.png')
    from PIL import Image, ImageDraw
    contact = Image.new('RGB', (1920, 768), '#0d0907')
    draw = ImageDraw.Draw(contact)
    for cell, n in enumerate([0, 135, 240, 480, 660, 840]):
        with Image.open(frames[n]) as im:
            contact.paste(im.resize((640, 360)), ((cell % 3)*640, (cell//3)*384))
        draw.text(((cell % 3)*640+12, (cell//3)*384+363), f'{n/30:.1f} s', fill='#eeae76')
    contact.save(sheet)
    report = {'duration':30, 'frames':900, 'fps':30, 'width':1920, 'height':1080,
              'codec':'h264', 'audio':False, 'bytes':args.output.stat().st_size,
              'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'capture':'deterministic per-frame PNG, same clock for camera, models and captions'}
    report_path = args.output.with_suffix('.json')
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    for p in (args.output, poster, sheet, report_path):
        p.chmod(0o644)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
