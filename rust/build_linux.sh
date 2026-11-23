#!/usr/bin/env bash
# Build modul native Linux (x86_64, manylinux2014 / glibc 2.17, abi3 untuk Python >= 3.9) untuk
# setiap crate rust-anything, lalu taruh sebagai python/<modul>/_native.abi3.so di samping .pyd
# Windows. Blok `rust-anything enable` memuat modul dari folder itu, jadi tidak perlu wheel.
#
#   bash rust/build_linux.sh            # dari folder turbojet/, butuh Docker
#
set -euo pipefail
cd "$(dirname "$0")"
IMAGE="ghcr.io/pyo3/maturin:v1.9.6"
TOOLCHAIN="${TOOLCHAIN:-stable}"
CRATES=(ops-rs split-rs)

for crate in "${CRATES[@]}"; do
  module="$(echo "$crate" | tr '-' '_')"
  lib="lib${module}.so"
  echo "== $crate"
  MSYS_NO_PATHCONV=1 docker run --rm \
    -v "$(pwd -W 2>/dev/null || pwd)/$crate:/io" \
    -v turbojet-cargo-registry:/root/.cargo/registry \
    -v turbojet-rustup:/root/.rustup \
    -e PYO3_PYTHON=/opt/python/cp312-cp312/bin/python \
    --entrypoint bash "$IMAGE" -c "
      set -e
      # rustc bawaan image lebih tua dari rust-version crate; pakai stable terbaru (dicache).
      rustup toolchain install $TOOLCHAIN --profile minimal >/dev/null 2>&1
      cargo +$TOOLCHAIN build --release --locked --target-dir /tmp/target
      cp /tmp/target/release/$lib /io/python/$module/_native.abi3.so
      echo glibc-symbol-max: \$(objdump -T /io/python/$module/_native.abi3.so | grep -o 'GLIBC_[0-9.]*' | sort -V | tail -1)
    "
  ls -l "$crate/python/$module/"
done
