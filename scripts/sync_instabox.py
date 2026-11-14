#!/usr/bin/env python3
"""Package clean Arescope sources (excluding secrets/caches) and sync to InstaBox."""
import argparse
import json
import os
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    ".cache",
    ".tmp",
    ".pytest_cache",
    ".npm-cache",
    ".runtime",
    "node_modules",
    "__pycache__",
    ".verification",
    "artifacts",
}
INCLUDE_TOPS = ["README.md", "archive", "docs", "services", "unity"]


def load_api_key(repo_root: Path) -> str:
    env_key = os.environ.get("INSTABOX_API_KEY", "").strip()
    if env_key:
        return env_key
    env_file = repo_root / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("INSTABOX_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("INSTABOX_API_KEY missing in environment and .env")


def pack_repo(repo_root: Path, out_path: Path, skip_archive_media: bool = False) -> int:
    count = 0
    with tarfile.open(out_path, "w:gz") as tf:
        for top in INCLUDE_TOPS:
            p = repo_root / top
            if not p.exists():
                continue
            if p.is_file():
                tf.add(p, arcname=top)
                count += 1
                continue
            for dirpath, dirnames, filenames in os.walk(p):
                if skip_archive_media and Path(dirpath).as_posix().endswith("archive/evidence"):
                    dirnames[:] = [d for d in dirnames if d not in {"screenshots", "device_logs"}]
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                for fn in sorted(filenames):
                    if fn == ".env" or (fn.startswith(".env.") and fn != ".env.example") or fn == ".coverage":
                        continue
                    fp = Path(dirpath) / fn
                    tf.add(fp, arcname=fp.relative_to(repo_root).as_posix())
                    count += 1
    return count


def api_json(method: str, url: str, api_key: str, payload: dict | None = None, timeout: int = 120) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"X-API-Key": api_key}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_file(machine_id: str, remote_path: str, local_path: Path, api_key: str) -> dict:
    url = f"https://api.instabox.sh/v1/machines/{machine_id}/files?path={remote_path}&parents=true"
    body = local_path.read_bytes()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"X-API-Key": api_key, "Content-Type": "application/octet-stream"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", default="m_agq5rkexzksyb63jwlmdlo35su")
    parser.add_argument("--remote-dir", default="/data/workspace/arescope")
    parser.add_argument("--skip-archive-media", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    api_key = load_api_key(repo_root)
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "arescope-sync.tar.gz"
        files_packed = pack_repo(repo_root, tar_path, skip_archive_media=args.skip_archive_media)
        remote_tar = f"{args.remote_dir.rstrip('/')}.tar.gz"
        up = upload_file(args.machine, remote_tar, tar_path, api_key)
    extract_cmd = (
        f"mkdir -p {args.remote_dir} && "
        f"tar -xzf {remote_tar} -C {args.remote_dir} && "
        f"rm -f {remote_tar} && ls -la {args.remote_dir}"
    )
    ex = api_json(
        "POST",
        f"https://api.instabox.sh/v1/machines/{args.machine}/exec",
        api_key,
        {"cmd": extract_cmd},
        timeout=120,
    )
    print(json.dumps({"files_packed": files_packed, "upload": up, "extract": ex}, indent=2))
    return ex.get("exitCode", 1)


if __name__ == "__main__":
    raise SystemExit(main())
