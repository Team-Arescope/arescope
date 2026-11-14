#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/triage_logcat.py" "${1:?usage: triage-logcat.sh logcat.txt}"
