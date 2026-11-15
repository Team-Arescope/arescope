"""Fetch exact archived PDS samples for the ~10 km HiRISE and 64 ppd MOLA views.

No source coordinates are stretched and missing elevations are never filled.
Raw source rows are cached outside the repository; fixtures record their hashes.
"""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HIRISE_URL = 'https://hirise-pds.lpl.arizona.edu/PDS/DTM/PSP/ORB_001400_001499/PSP_001488_1750_PSP_001752_1750/DTEEC_001488_1750_001752_1750_U02.IMG'
MOLA_URL = 'https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg064/megt00n000gb.img'
NATIVE_STEP = 1.0117467945795


def fetch(url, start=None, end=None):
    for attempt in range(4):
        try:
            headers = {'Range': f'bytes={start}-{end}'} if start is not None else {}
            with urlopen(Request(url, headers=headers), timeout=50) as response:
                if start is not None:
                    assert response.status == 206
                    assert response.headers['Content-Range'].startswith(f'bytes {start}-{end}/')
                    raw = response.read(end - start + 2)
                    assert len(raw) == end - start + 1
                else:
                    raw = response.read(65537)
                    assert len(raw) <= 65536
                return raw
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def write_fixture(destination, data):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')


def hirise(output, cache):
    row0, col0, stride, rows, cols, width, image_offset = 1759, 1473, 77, 129, 53, 6736, 26944
    label_raw = fetch(HIRISE_URL, 0, image_offset - 1)
    label = label_raw.decode('ascii').replace('\r', '')
    assert re.search(r'LINE_SAMPLES\s*=\s*6736\b', label)
    assert re.search(r'LINES\s*=\s*13375\b', label)
    assert f'{NATIVE_STEP}' in label

    def source_row(index):
        native_row = row0 + index * stride
        start = image_offset + native_row * width * 4
        cached = cache / f'hirise-row-{native_row}.bin'
        raw = cached.read_bytes() if cached.exists() else fetch(HIRISE_URL, start, start + width * 4 - 1)
        assert len(raw) == width * 4
        cached.write_bytes(raw)
        values = [struct.unpack_from('<f', raw, (col0 + c * stride) * 4)[0] for c in range(cols)]
        assert all(math.isfinite(v) and -4486 < v < -2976 for v in values), 'Missing HiRISE samples: never fill or invent elevations'
        return values, {'row_zero_based': native_row, 'start': start, 'end': start + len(raw) - 1,
                        'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    with ThreadPoolExecutor(max_workers=6) as pool:
        source_rows = list(pool.map(source_row, range(rows)))
    step = stride * NATIVE_STEP
    east, south = (cols - 1) * step, (rows - 1) * step
    center_native_row, center_native_col = row0 + (rows - 1) * stride / 2, col0 + (cols - 1) * stride / 2
    radius, lat_offset, lon_offset = 3396190.0, -276559.50000001, 3577.5000000001

    def lat_lon(row, col):
        y = (lat_offset - (row + 1)) * NATIVE_STEP
        x = ((col + 1) - lon_offset) * NATIVE_STEP
        return [math.degrees(y / radius), 137.3 + math.degrees(x / radius)]

    data = {'source': 'nasa-pds-hirise', 'frame': 'mars-local-metres', 'grid': {'rows': rows, 'cols': cols},
            'metadata': {'live': False, 'title': 'Gale crater / expanded HiRISE strip', 'source_url': HIRISE_URL,
                         'catalog_url': 'https://www.uahirise.org/dtm/dtm.php?ID=PSP_001488_1750',
                         'product_id': 'DTEEC_001488_1750_001752_1750_U02', 'dataset': 'MRO-M-HIRISE-5-DTM-V1.0',
                         'native_spacing_m': NATIVE_STEP, 'effective_spacing_m': step,
                         'spacing_m': {'east': step, 'south': step}, 'extent_m': max(east, south),
                         'extent_m_axes': {'east': east, 'south': south}, 'row0_zero_based': row0,
                         'col0_zero_based': col0, 'row_stride': stride, 'col_stride': stride,
                         'native_shape': [(rows - 1) * stride + 1, (cols - 1) * stride + 1],
                         'source_width': width, 'source_height': 13375, 'image_offset_bytes': image_offset,
                         'null_count': 0, 'null_bits': '0xFF7FFFFB',
                         'units': 'metres above Mars 2000 equipotential datum', 'sample_type': 'PC_REAL little-endian float32',
                         'resampling': 'Exact stride-77 sampling of archived float32 heights. No interpolation, stretching or filling. Fine features may alias.',
                         'caveat': 'The continuous valid source strip is about 4.05 by 9.97 km, not a 10 by 10 km square. The display step does not resolve wheel-scale obstacles.',
                         'center_lat_lon': lat_lon(center_native_row, center_native_col),
                         'corners_lat_lon': {'NW': lat_lon(row0, col0), 'SE': lat_lon(row0 + (rows - 1) * stride, col0 + (cols - 1) * stride)},
                         'projection': 'EQUIRECTANGULAR planetocentric east-positive, center lat=0 lon=137.3, radius=3396190m',
                         'vertical_exaggeration': 1, 'sha256_label': hashlib.sha256(label_raw).hexdigest(),
                         'source_label_range': {'start': 0, 'end': image_offset - 1},
                         'source_rows': [meta for _, meta in source_rows]},
            'points': [[(c - (cols - 1) / 2) * step, source_rows[r][0][c], (r - (rows - 1) / 2) * step]
                       for r in range(rows) for c in range(cols)]}
    write_fixture(output / 'hirise-gale.json', data)
    print('HIRISE', json.dumps({'grid': data['grid'], 'extent_m': data['metadata']['extent_m_axes'], 'step_m': step}), flush=True)


def mola(output, cache):
    label_url = MOLA_URL.replace('.img', '.lbl')
    label_raw = fetch(label_url)
    label = label_raw.decode('ascii').replace('\r', '')
    assert 'MEGT00N000GB.IMG' in label and re.search(r'MAP_RESOLUTION\s*=\s*64\.0', label)
    size, width, ppd, radius = 65, 11520, 64, 3396000.0
    # Centre the compact regional view on the expanded HiRISE strip.
    row0, col0 = 277, 8755
    start, end = row0 * width * 2, (row0 + size) * width * 2 - 1
    raw = fetch(MOLA_URL, start, end)
    lat_north, lon_west = -(row0 + .5) / ppd, (col0 + .5) / ppd
    lat_center, lon_center = lat_north - (size - 1) / ppd / 2, lon_west + (size - 1) / ppd / 2
    south_step = radius * math.pi / 180 / ppd
    east_step = south_step * math.cos(math.radians(lat_center))
    points = [[(c - (size - 1) / 2) * east_step, struct.unpack_from('>h', raw, (r * width + col0 + c) * 2)[0],
               (r - (size - 1) / 2) * south_step] for r in range(size) for c in range(size)]
    data = {'source': 'nasa-pds-mola', 'frame': 'mars-local-metres', 'grid': {'rows': size, 'cols': size},
            'metadata': {'live': False, 'title': 'Gale crater region / MOLA MEGDR 64 ppd',
                         'dataset_id': 'MGS-M-MOLA-5-MEGDR-L3-V1.0', 'product_id': 'MEGT00N000GB.IMG', 'product_version': '2.0',
                         'source_url': MOLA_URL, 'label_url': label_url,
                         'overview_url': 'https://pds-geosciences.wustl.edu/missions/mgs/megdr.html',
                         'units': 'metres', 'vertical_datum': 'radius minus GMM3 (mgm1025) areoid, degree/order 50',
                         'center': {'latitude': lat_center, 'longitude': lon_center}, 'grid_pixels_per_degree': ppd,
                         'grid_degrees': 1 / ppd, 'spacing_m': {'east': east_step, 'south': south_step},
                         'extent_m': {'east': (size - 1) * east_step, 'south': (size - 1) * south_step},
                         'pixel_centres': {'north': lat_north, 'south': lat_north - (size - 1) / ppd, 'west': lon_west, 'east': lon_west + (size - 1) / ppd},
                         'elevation_range_m': [min(p[1] for p in points), max(p[1] for p in points)],
                         'projection': 'local equirectangular tangent approximation, R=3396000m, cos(center latitude) longitude correction',
                         'vertical_exaggeration': 1,
                         'processing': 'Exact 65 by 65 crop of native 64 ppd signed big-endian int16 samples. No resampling, smoothing, stretching or filling.',
                         'caveat': 'Native grid spacing is not effective resolving power. The original product includes interpolated empty bins and equatorial track gaps up to 12km. Not rover navigation ground truth.',
                         'source_crop': {'row0': row0, 'col0': col0, 'rows': size, 'cols': size, 'source_width': width,
                                         'http_range': f'bytes={start}-{end}', 'raw_bytes': len(raw),
                                         'raw_sha256': hashlib.sha256(raw).hexdigest(), 'label_sha256': hashlib.sha256(label_raw).hexdigest()},
                         'credit': 'NASA / MGS MOLA Science Team / Goddard Space Flight Center; NASA PDS Geosciences Node'},
            'points': points}
    write_fixture(output / 'mola-gale.json', data)
    print('MOLA', json.dumps({'grid': data['grid'], 'extent_m': data['metadata']['extent_m'], 'step_m': data['metadata']['spacing_m']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'static/data')
    parser.add_argument('--cache-dir', type=Path, required=True)
    args = parser.parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    hirise(args.output_dir, args.cache_dir)
    mola(args.output_dir, args.cache_dir)


if __name__ == '__main__':
    main()
