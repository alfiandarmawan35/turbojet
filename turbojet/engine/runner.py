"""Titik masuk subprocess engine: ``python -m turbojet.engine run|preview|ops|version``.

Kontrak berkas (versi 1) ada di ``contract.py``. Kode keluar:
0 sukses, 2 input/opsi tidak valid, 3 batas terlampaui, 4 kesalahan internal/sementara.
"""

import argparse
import csv
import json
import os
import sys
import time
from decimal import Decimal, localcontext

from turbojet.engine import ENGINE_VERSION, contract, csvio
from turbojet.engine import registry as ops
from turbojet.engine.ops import group_sum
from turbojet.engine.ops.preview import detect_delimiter, preview

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_LIMIT = 3
EXIT_INTERNAL = 4

DEFAULT_CHUNK_ROWS = 50_000
MAX_ERRORS_KEPT = 10_000


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def run(spec_path, input_path, out_dir, chunk_rows=DEFAULT_CHUNK_ROWS, block_chars=csvio.BLOCK_CHARS):
    """Jalankan satu pekerjaan dan kembalikan kode keluar. Tidak pernah melempar."""
    started = time.monotonic()
    try:
        os.makedirs(out_dir, exist_ok=False)
    except FileExistsError:
        _write_failure(out_dir, "OUT_DIR_EXISTS", "direktori keluaran harus baru per percobaan")
        return EXIT_INTERNAL
    try:
        spec = contract.load_spec(spec_path)
        summary = _run_group_sum(spec, input_path, out_dir, chunk_rows, block_chars, started)
    except (InputError, contract.SpecError, group_sum.InvalidOptions) as exc:
        _write_failure(out_dir, getattr(exc, "code", "INVALID_INPUT"), str(exc))
        return EXIT_INPUT
    except UnicodeDecodeError as exc:
        _write_failure(out_dir, "ENCODING", f"berkas tidak bisa dibaca sebagai teks: {exc.reason}")
        return EXIT_INPUT
    except group_sum.LimitExceeded as exc:
        _write_failure(out_dir, "LIMIT_EXCEEDED", str(exc))
        return EXIT_LIMIT
    except Exception as exc:  # noqa: BLE001 - semua sisa = kesalahan internal yang boleh diulang
        _write_failure(out_dir, "INTERNAL", f"{type(exc).__name__}: {exc}")
        return EXIT_INTERNAL
    contract.write_manifest(out_dir, summary["engine_path"])
    return EXIT_OK


def _run_group_sum(spec, input_path, out_dir, chunk_rows, block_chars, started):
    if spec["operation"] != "group_sum":
        raise InputError("UNKNOWN_OPERATION", f"operasi tidak dikenal: {spec['operation']}")
    options = dict(spec["options"])
    limits = spec["limits"]
    encoding = options.get("encoding") or csvio.detect_encoding(input_path)
    aggregate = ops.resolve("group_sum")

    with open(input_path, encoding=encoding, newline="") as fh:
        reader = csvio.ChunkReader(fh, block_chars)
        header_text, _ = reader.take(1)
        if not header_text.strip():
            raise InputError("EMPTY_FILE", "berkas kosong")
        delimiter = options.get("delimiter") or detect_delimiter(header_text.rstrip("\r\n"))
        columns = next(csv.reader([header_text.rstrip("\r\n")], delimiter=delimiter))
        if len(columns) > limits["max_columns"]:
            raise group_sum.LimitExceeded(f"jumlah kolom melebihi {limits['max_columns']}")
        chunk_options = json.dumps(
            {
                "columns": columns,
                "group_by": options.get("group_by"),
                "value_column": options.get("value_column"),
                "delimiter": delimiter,
                "decimal": options.get("decimal", "comma"),
                "max_groups": limits["max_groups"],
            },
            ensure_ascii=False,
        )

        groups = {}
        errors = []
        rows_read = rows_valid = errors_total = 0
        next_row = 2  # header = baris 1
        with localcontext() as ctx:
            ctx.prec = 40
            for chunk_text, n_records in reader.chunks(chunk_rows):
                part = json.loads(aggregate(chunk_text, chunk_options, next_row))
                _raise_part_error(part)
                next_row += n_records
                rows_read += part["rows_read"]
                rows_valid += part["rows_valid"]
                errors_total += len(part["errors"])
                room = MAX_ERRORS_KEPT - len(errors)
                if room > 0:
                    errors.extend(part["errors"][:room])
                for key, count, total in part["groups"]:
                    entry = groups.get(key)
                    if entry is None:
                        if len(groups) >= limits["max_groups"]:
                            raise group_sum.LimitExceeded(f"jumlah kelompok melebihi {limits['max_groups']}")
                        groups[key] = [count, Decimal(total)]
                    else:
                        entry[0] += count
                        entry[1] += Decimal(total)
                if rows_read > limits["max_rows"]:
                    raise group_sum.LimitExceeded(f"jumlah baris melebihi {limits['max_rows']}")
                if time.monotonic() - started > limits["max_seconds"]:
                    raise group_sum.LimitExceeded(f"waktu proses melebihi {limits['max_seconds']} detik")
                contract.write_progress(out_dir, rows_read)

    path = ops.engine_path(aggregate)
    _write_output(out_dir, options["group_by"], options["value_column"], groups)
    _write_errors(out_dir, errors)
    summary = {
        "operation": "group_sum",
        "engine_path": path,
        "encoding": encoding,
        "delimiter": delimiter,
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "rows_rejected": errors_total,
        "errors_kept": len(errors),
        "groups": len(groups),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    contract.write_json(os.path.join(out_dir, contract.RESULT_FILE), summary)
    return summary


def _raise_part_error(part):
    """Operasi mengembalikan galat sebagai data (sama untuk jalur Python dan Rust)."""
    err = part.get("error")
    if err is None:
        return
    if err["code"] == "LIMIT_EXCEEDED":
        raise group_sum.LimitExceeded(err["message"])
    raise InputError(err["code"], err["message"])


def _write_output(out_dir, group_col, value_col, groups):
    with open(os.path.join(out_dir, contract.OUTPUT_FILE), "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([group_col, "rows", f"sum_{value_col}"])
        for key, (count, total) in groups.items():
            writer.writerow([key, count, format(total, "f")])


def _write_errors(out_dir, errors):
    with open(os.path.join(out_dir, contract.ERRORS_FILE), "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row", "column", "code", "value"])
        writer.writerows(errors)


def _write_failure(out_dir, code, message):
    try:
        os.makedirs(out_dir, exist_ok=True)
        contract.write_json(os.path.join(out_dir, contract.FAILURE_FILE), {"code": code, "message": message})
    except OSError:
        pass
    print(json.dumps({"error": code, "message": message}, ensure_ascii=False), file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m turbojet.engine")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--spec", required=True)
    p_run.add_argument("--input", required=True)
    p_run.add_argument("--out", required=True)
    p_run.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    p_prev = sub.add_parser("preview")
    p_prev.add_argument("--input", required=True)
    p_prev.add_argument("--rows", type=int, default=20)
    sub.add_parser("ops")
    sub.add_parser("version")
    args = parser.parse_args(argv)

    if args.cmd == "run":
        return run(args.spec, args.input, args.out, args.chunk_rows)
    if args.cmd == "preview":
        encoding = csvio.detect_encoding(args.input)
        with open(args.input, encoding=encoding, errors="replace", newline="") as fh:
            head = fh.read(64 * 1024)
        print(preview(head, args.rows))
        return EXIT_OK
    if args.cmd == "ops":
        print(json.dumps(ops.describe()))
        return EXIT_OK
    print(json.dumps({"engine_version": ENGINE_VERSION, "contract_version": contract.CONTRACT_VERSION}))
    return EXIT_OK
