#!/usr/bin/env python3
"""Install Arescope bridges into a resolved RoomScan package, idempotently.

Usage: py Scripts/patch_roomscan_editor.py Library/PackageCache/com.genesis.roomscan@HASH
Writes only inside this project's Library/PackageCache or Packages directories.
The package assembly references the dependency-free Arescope.Core assembly.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
BRIDGES = ("ArescopeLiveCloud", "ArescopeMeshExport", "ArescopeTexturedMesh")


def install(package: Path, check: bool = False) -> int:
    package = package.resolve()
    allowed = ((PROJECT / "Library/PackageCache").resolve(), (PROJECT / "Packages").resolve())
    if not any(package.is_relative_to(root) and package != root for root in allowed):
        raise ValueError("Package root must be inside this project's Library/PackageCache or Packages")
    info = json.loads((package / "package.json").read_text(encoding="utf-8-sig"))
    if info.get("name") != "com.genesis.roomscan":
        raise ValueError("Not a com.genesis.roomscan package")
    surface = (package / "Runtime/Core/GPUSurfaceNets.cs").read_text(encoding="utf-8-sig")
    for declaration in ("VertexStride = 48", "VertexPosOffset = 0", "VertexNormalOffset = 24", "VertexPackedColorOffset = 36"):
        if declaration not in surface:
            raise ValueError("Unsupported SDK layout: " + declaration)
    asm = package / "Runtime/Genesis.RoomScan.asmdef"
    definition = json.loads(asm.read_text(encoding="utf-8-sig"))
    references = definition.setdefault("references", [])
    missing = []
    for name in BRIDGES:
        for suffix in (".cs", ".cs.meta"):
            source = PROJECT / "PackagePatches" / (name + suffix)
            target = package / "Runtime/Utils" / source.name
            if not target.resolve().is_relative_to(package):
                raise ValueError("Bridge destination escapes package root")
            if not source.is_file():
                raise ValueError("Missing bridge source: " + str(source))
            if not target.exists() or target.read_bytes() != source.read_bytes():
                missing.append(target.name)
                if not check:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    if "Arescope.Core" not in references:
        missing.append("Arescope.Core assembly reference")
        if not check:
            references.append("Arescope.Core")
            asm.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
    # UnityCsReference 6000.2.9f1 requires an explicit FindObjectsSortMode;
    # the pinned wizard's parameterless BuildingBlock lookup targets a newer API.
    for editor in sorted(package.rglob("*.cs")):
        if not editor.resolve().is_relative_to(package):
            raise ValueError("Source symlink escapes package root")
        text = editor.read_text(encoding="utf-8-sig")
        updated = re.sub(r"\bFindObjectsByType<([\w.]+)>\(\s*\)",
            r"FindObjectsByType<\1>(UnityEngine.FindObjectsSortMode.None)", text)
        if updated != text:
            missing.append(str(editor.relative_to(package)))
            if not check:
                editor.write_text(updated, encoding="utf-8")
    print(("CHECK" if check else "PATCH"), "changes=" + str(len(missing)))
    for item in missing:
        print("  " + item)
    return 1 if check and missing else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        return install(args.package_root, args.check)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
