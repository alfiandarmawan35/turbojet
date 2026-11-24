"""Kontrak berkas engine versi 1: ``job.json`` masuk; hasil, galat, dan manifest keluar."""

import hashlib
import json
import os

from turbojet.engine import ENGINE_VERSION

CONTRACT_VERSION = 1

RESULT_FILE = "result.json"
OUTPUT_FILE = "output.csv"
ERRORS_FILE = "errors.csv"
MANIFEST_FILE = "manifest.json"  # ditulis paling akhir: tanda hasil lengkap
FAILURE_FILE = "failure.json"
PROGRESS_FILE = "progress.json"

DEFAULT_LIMITS = {
    "max_rows": 5_000_000,
    "max_columns": 200,
    "max_groups": 100_000,
    "max_seconds": 600,
}


class SpecError(ValueError):
    code = "INVALID_SPEC"


def load_spec(path):
    with open(path, encoding="utf-8") as fh:
        try:
            spec = json.load(fh)
        except ValueError as exc:
            raise SpecError(f"job.json bukan JSON: {exc}") from None
    if not isinstance(spec, dict):
        raise SpecError("job.json harus objek")
    if spec.get("contract_version") != CONTRACT_VERSION:
        raise SpecError(f"contract_version harus {CONTRACT_VERSION}")
    if not isinstance(spec.get("operation"), str):
        raise SpecError("operation wajib")
    options = spec.get("options") or {}
    if not isinstance(options, dict):
        raise SpecError("options harus objek")
    limits = dict(DEFAULT_LIMITS)
    for key, value in (spec.get("limits") or {}).items():
        if key not in DEFAULT_LIMITS or not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise SpecError(f"batas tidak valid: {key}")
        limits[key] = value
    return {"operation": spec["operation"], "options": options, "limits": limits}


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_progress(out_dir, rows_read):
    write_json(os.path.join(out_dir, PROGRESS_FILE), {"rows_read": rows_read})


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(out_dir, engine_path):
    files = {}
    for name in (RESULT_FILE, OUTPUT_FILE, ERRORS_FILE):
        full = os.path.join(out_dir, name)
        files[name] = {"sha256": sha256_file(full), "bytes": os.path.getsize(full)}
    write_json(
        os.path.join(out_dir, MANIFEST_FILE),
        {
            "contract_version": CONTRACT_VERSION,
            "engine_version": ENGINE_VERSION,
            "engine_path": engine_path,
            "files": files,
        },
    )


def verify_manifest(out_dir):
    """Kembalikan manifest bila ada dan semua checksum cocok; selain itu ``None``."""
    path = os.path.join(out_dir, MANIFEST_FILE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    for name, meta in manifest.get("files", {}).items():
        full = os.path.join(out_dir, name)
        if not os.path.exists(full) or sha256_file(full) != meta["sha256"]:
            return None
    return manifest
