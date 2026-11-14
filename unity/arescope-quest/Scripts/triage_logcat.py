#!/usr/bin/env python3
"""Summarize Quest logcat, including UTF-16 files from PowerShell redirection."""
import argparse
import re
from pathlib import Path


def load(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    if b"\x00" in raw[:1024]:
        even = raw[0:1024:2].count(0)
        odd = raw[1:1024:2].count(0)
        return raw.decode("utf-16-le" if odd >= even else "utf-16-be", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def triage(text):
    lines = text.splitlines()
    ars = [line for line in lines if "[ARS]" in line]
    room = [line for line in lines if "[RoomScan]" in line]
    crashes = [i for i, line in enumerate(lines) if re.search(r"Fatal signal|SIGABRT|beginning of crash|Abort message", line)]
    print(f"lines={len(lines)} managed={len(ars)} roomscan={len(room)} crashes={len(crashes)}")
    for label, items in (("ARESCOPE", ars), ("ROOMSCAN", room)):
        print("\n" + label)
        for line in items[:60]:
            print(line[-240:])
    for i in crashes:
        print("\nCRASH", lines[i][-240:])
        context = [line for line in lines[max(0, i-120):i] if re.search(r"OpenXR|OVRPlugin|xrCreateInstance|xrGetInstanceProcAddr", line)]
        for line in context[-15:]:
            print(line[-240:])
    flags = {
        "no managed output": not ars,
        "depth provider missing": any("sub=null" in line or "occlusion=no-subsystem" in line for line in lines),
        "no active XR loader": any("No active XR loader" in line for line in lines),
        "XR inactive": any("xr=inactive" in line for line in lines),
        "native plugin missing": any("DllNotFoundException" in line or "unable to load dll" in line for line in lines),
        "lifecycle function table missing": any("instanceProcAddr is null" in line for line in lines),
    }
    print("\nFINDINGS")
    for label, hit in flags.items():
        if hit:
            print("!", label)
    if not any(flags.values()):
        print("No conclusive gate failure; inspect device depth-frame progression.")
    return flags


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logcat", type=Path)
    triage(load(parser.parse_args().logcat))
