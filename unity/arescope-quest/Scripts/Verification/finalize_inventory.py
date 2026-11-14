"""Create stable Unity metadata and an inventory for this agent's owned paths only."""
import hashlib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNED_TREES = ("Assets/Arescope", "Assets/Tests", "Assets/XR", "Assets/Settings", "PackagePatches", "ProjectSettings", "Packages", "Scripts")
OWNED_RESOURCE_TREES = ("Assets/Resources/ArescopeIcons", "Assets/Resources/ArescopeFonts")
OWNED_FILES = ("Assets/Resources/ArescopeWire.shader", "Assets/Resources/arescope-endpoint.example.txt",
               "Assets/Resources/arescope-live-token.example.txt", "Assets/Plugins/Android/AndroidManifest.xml",
               "Assets/Plugins/Android/arm64-v8a/README.md", ".gitignore")
FIXED_GUIDS = {"Assets/Resources/ArescopeWire.shader": "9e167c771ee24f78b2e60a7e9f746d0c"}


def owned_files():
    files = set(ROOT / rel for rel in OWNED_FILES)
    for rel in OWNED_FILES:
        path=ROOT / rel
        if rel.startswith("Assets/"):
            files.add(path.with_name(path.name+".meta"))
    for rel in OWNED_TREES + OWNED_RESOURCE_TREES:
        if rel.startswith("Assets/"):
            path=ROOT / rel
            files.add(path.with_name(path.name+".meta"))
    for tree in OWNED_TREES + OWNED_RESOURCE_TREES:
        files.update(path for path in (ROOT / tree).rglob("*") if path.is_file())
    for path in tuple(files):
        if path.relative_to(ROOT).as_posix().startswith("Assets/"):
            for parent in path.parents:
                if parent==ROOT or parent==ROOT / "Assets":
                    break
                files.add(parent.with_name(parent.name+".meta"))
    return sorted((path for path in files if path.is_file() and
        ".verification" not in path.parts and "__pycache__" not in path.parts), key=lambda path: path.as_posix())


def create_meta(path):
    rel = path.relative_to(ROOT).as_posix()
    if not rel.startswith(("Assets/", "PackagePatches/")) or path.suffix == ".meta":
        return
    meta = path.with_name(path.name + ".meta")
    if meta.exists():
        return
    guid = FIXED_GUIDS.get(rel, uuid.uuid5(uuid.NAMESPACE_URL, "arescope-quest/" + rel).hex)
    text = f"fileFormatVersion: 2\nguid: {guid}\n"
    if path.is_dir():
        text += "folderAsset: yes\nDefaultImporter:\n  externalObjects: {}\n"
    elif path.suffix == ".cs":
        text += ("MonoImporter:\n  externalObjects: {}\n  serializedVersion: 2\n"
                 "  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n")
    elif path.suffix == ".shader":
        text += "ShaderImporter:\n  externalObjects: {}\n  defaultTextures: []\n  nonModifiableTextures: []\n"
    elif path.suffix == ".hlsl":
        text += "ShaderIncludeImporter:\n  externalObjects: {}\n"
    elif path.suffix == ".asmdef":
        text += "AssemblyDefinitionImporter:\n  externalObjects: {}\n"
    elif path.suffix == ".png":
        text += ("TextureImporter:\n  internalIDToNameTable: []\n  externalObjects: {}\n  serializedVersion: 13\n"
                 "  mipmaps:\n    mipMapMode: 0\n    enableMipMap: 0\n    sRGBTexture: 1\n"
                 "  isReadable: 0\n  textureType: 8\n  spriteMode: 1\n  spritePixelsToUnits: 100\n"
                 "  alphaUsage: 1\n  alphaIsTransparency: 1\n  maxTextureSize: 64\n"
                 "  textureSettings:\n    serializedVersion: 2\n    filterMode: 1\n    aniso: 1\n"
                 "    mipBias: 0\n    wrapU: 1\n    wrapV: 1\n    wrapW: 1\n"
                 "  platformSettings:\n  - serializedVersion: 4\n    buildTarget: DefaultTexturePlatform\n"
                 "    maxTextureSize: 64\n    resizeAlgorithm: 0\n    textureFormat: -1\n"
                 "    textureCompression: 0\n    compressionQuality: 100\n    crunchedCompression: 0\n"
                 "    allowsAlphaSplitting: 0\n    overridden: 0\n")
    elif path.suffix == ".txt":
        text += "TextScriptImporter:\n  externalObjects: {}\n"
    else:
        text += "DefaultImporter:\n  externalObjects: {}\n"
    text += "  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
    meta.write_text(text, encoding="utf-8")


def finalize():
    files = owned_files()
    directories = set()
    for path in files:
        create_meta(path)
        if path.relative_to(ROOT).as_posix().startswith("Assets/"):
            for parent in path.parents:
                if parent == ROOT or parent == ROOT / "Assets":
                    break
                directories.add(parent)
    for path in directories:
        create_meta(path)
    lines = ["Arescope core client source/asset inventory (relative to unity/arescope-quest/)",
             "Includes Unity metadata; generated Scripts/.verification/ outputs are excluded.", ""]
    for path in owned_files():
        lines.append(path.relative_to(ROOT).as_posix())
    lines += ["", "Byte-preserved reference payloads (SHA-256):"]
    for path in owned_files():
        rel = path.relative_to(ROOT).as_posix()
        if (rel in ("Packages/manifest.json", "Packages/packages-lock.json", "ProjectSettings/EditorBuildSettings.asset",
                    "Assets/Plugins/Android/AndroidManifest.xml") or
                (rel.startswith(OWNED_RESOURCE_TREES) and path.suffix in (".png", ".txt"))):
            lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + rel)
    (ROOT / "Scripts/CREATED-FILES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Owned-file inventory:", len(owned_files()), "files (including metadata)")


if __name__ == "__main__":
    finalize()
