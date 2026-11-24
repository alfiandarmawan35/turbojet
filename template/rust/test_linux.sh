#!/usr/bin/env bash
# Uji modul native Linux di container Python bersih (tanpa toolchain Rust).
#   bash rust/test_linux.sh [python-image]      # default python:3.11-slim (Frappe v15)
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${1:-python:3.11-slim}"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W 2>/dev/null || pwd):/src:ro" "$IMAGE" bash -c '
  set -e
  cp -r /src /app && cd /app && rm -rf .venv && find . -name __pycache__ -prune -exec rm -rf {} +
  pip install -q --root-user-action=ignore pytest >/dev/null
  echo "== python $(python -V 2>&1 | cut -d" " -f2), glibc $(ldd --version | head -1 | grep -o "[0-9.]*$")"
  echo "== RUST_ANYTHING_MODE=new (wajib Rust)"; RUST_ANYTHING_MODE=new python -m turbojet.engine ops
  RUST_ANYTHING_MODE=new python -m pytest -q -p no:cacheprovider | tail -1
  echo "== RUST_ANYTHING_MODE=old (Python)"; RUST_ANYTHING_MODE=old python -m pytest -q -p no:cacheprovider | tail -1
  echo "== bench 1 juta baris"
  RUST_ANYTHING_MODE=new python bench/bench_group_sum.py 1000000 10000 | cut -c1-70
  RUST_ANYTHING_MODE=new python bench/bench_group_sum.py 1000000 10000 | cut -c1-70
  RUST_ANYTHING_MODE=old python bench/bench_group_sum.py 1000000 10000 | cut -c1-70
'
