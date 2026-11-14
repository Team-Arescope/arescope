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


def patch_editor_source(text: str) -> str:
    """Adapt the pinned wizard to 6000.2 without dropping its 6000.3 UI setup."""
    text = re.sub(r"\bFindObjectsByType<([\w.]+)>\(\s*\)",
        r"FindObjectsByType<\1>(UnityEngine.FindObjectsSortMode.None)", text)
    text = re.sub(
        r"\bFindObjectsByType<([\w.]+)>\(\s*((?:UnityEngine\.)?FindObjectsInactive\.(?:Include|Exclude))\s*\)",
        r"FindObjectsByType<\1>(\2, UnityEngine.FindObjectsSortMode.None)", text)

    # Track enclosing guards so a second install (or an already guarded SDK)
    # never nests another copy of our version gate. Group adjacent assignments.
    assignment = re.compile(r"([ \t]*)uiDoc\.(?:worldSpaceSizeMode|pivot|pivotReferenceSize)[ \t]*=")
    directive = re.compile(r"^[ \t]*#(if|elif|else|endif)\b(.*)")
    lines = text.splitlines(keepends=True)
    result, guards = [], []
    index = 0
    while index < len(lines):
        line = lines[index]
        command = directive.match(line)
        if command:
            kind, condition = command.groups()
            is_newer = condition.split("//", 1)[0].strip() == "UNITY_6000_3_OR_NEWER"
            if kind == "if":
                guards.append(is_newer)
            elif kind in ("else", "elif") and guards:
                guards[-1] = is_newer if kind == "elif" else False
            elif kind == "endif" and guards:
                guards.pop()
        match = assignment.match(line)
        if match and not any(guards):
            end = index + 1
            while end < len(lines) and assignment.match(lines[end]):
                end += 1
            indent = match[1]
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            block = "".join(lines[index:end])
            if not block.endswith("\n"):
                block += newline
            result.extend((indent + "#if UNITY_6000_3_OR_NEWER" + newline,
                           block, indent + "#endif" + newline))
            index = end
        else:
            result.append(line)
            index += 1
    return "".join(result)


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
    # Keep compatibility edits in the SDK editor scripts; bridge/runtime code
    # does not need these wizard-specific API adjustments.
    for editor in sorted((package / "Editor").rglob("*.cs")):
        if not editor.resolve().is_relative_to(package):
            raise ValueError("Source symlink escapes package root")
        original = editor.read_bytes()
        text = original.decode("utf-8-sig")
        updated = patch_editor_source(text)
        if updated != text:
            missing.append(str(editor.relative_to(package)))
            if not check:
                bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
                editor.write_bytes(bom + updated.encode("utf-8"))
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
