"""Verify every height sample against byte ranges from the primary NASA PDS files.

No large raw image is saved. Run from the service directory with Python 3.10+.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import struct
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def read_range(url, start, end):
    value = f'bytes={start}-{end}'
    with urlopen(Request(url, headers={'Range': value}), timeout=60) as response:
        assert response.status == 206, 'Primary server must honor byte ranges'
        assert response.headers['Content-Range'].startswith(f'bytes {start}-{end}/')
        raw = response.read(end - start + 2)
    assert len(raw) == end - start + 1
    return raw


def verify(name):
    data = json.loads((ROOT / f"static/data/{name}-gale.json").read_text())
    m = data["metadata"]
    if m.get('source_rows'):
        stride, col = m['col_stride'], m['col0_zero_based']
        def verify_row(index):
            meta = m['source_rows'][index]
            raw = read_range(m['source_url'], meta['start'], meta['end'])
            assert hashlib.sha256(raw).hexdigest() == meta['sha256'], 'Source row checksum changed'
            for c in range(data['grid']['cols']):
                measured = struct.unpack_from('<f', raw, (col + c * stride) * 4)[0]
                assert measured == data['points'][index * data['grid']['cols'] + c][1]
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(verify_row, range(data['grid']['rows'])))
        label = m['source_label_range']
        assert hashlib.sha256(read_range(m['source_url'], label['start'], label['end'])).hexdigest() == m['sha256_label']
        print(f"{name}: verified {len(data['points'])} heights against individual NASA PDS source rows")
        return
    if name == "mola":
        meta = m["source_crop"]
        range_header = meta["http_range"]
        expected_hash, width, col, stride, fmt, size = meta["raw_sha256"], meta["source_width"], meta["col0"], 1, ">h", 2
    else:
        meta = m["range"]
        range_header = f'bytes={meta["start"]}-{meta["end"]}'
        expected_hash, width, col, stride, fmt, size = m["sha256_source_rows"], 6736, m["col0_zero_based"], 8, "<f", 4
    with urlopen(Request(m["source_url"], headers={"Range": range_header}), timeout=60) as response:
        assert response.status == 206, "Primary server must honor byte ranges"
        assert response.headers["Content-Range"].startswith(range_header.replace("=", " ") + "/")
        raw = response.read()
    assert hashlib.sha256(raw).hexdigest() == expected_hash, "Source range checksum changed"
    cols = data["grid"]["cols"]
    for i, point in enumerate(data["points"]):
        r, c = divmod(i, cols)
        y = struct.unpack_from(fmt, raw, ((r * stride) * width + col + c * stride) * size)[0]
        assert y == point[1], (name, r, c, y, point[1])
    print(f"{name}: verified {len(data['points'])} heights against NASA PDS; SHA-256 matches")


if __name__ == "__main__":
    for name in ("mola", "hirise"):
        verify(name)
