"""Operasi ``group_sum``: jumlah baris dan total per kelompok untuk satu potongan CSV.

Unit ini adalah target port rust-anything. Aturannya:

* murni: tanpa Frappe, tanpa I/O, tanpa jam;
* argumen dan hasil hanya ``str``/``int``; nilai uang dikembalikan sebagai string desimal;
* galat sebagai data, bukan exception: kelas exception Python tidak bisa dibuat dari Rust,
  jadi galat yang disengaja dikembalikan sebagai ``{"error": {"code", "message"}}``
  (kode ``INVALID_OPTIONS``, ``LIMIT_EXCEEDED``, ``CSV_ERROR``). Runner yang menerjemahkannya.

Format hasil (JSON ringkas, ``ensure_ascii=False``, urutan kunci tetap)::

    {"rows_read": 3, "rows_valid": 2,
     "groups": [["Jakarta", 2, "1500.50"]],
     "errors": [[4, "total", "NOT_A_NUMBER", "12x"]]}

    {"error": {"code": "LIMIT_EXCEEDED", "message": "jumlah kelompok melebihi 2"}}

``groups`` berurutan sesuai kemunculan pertama. Nomor baris = nomor rekaman CSV
seperti di spreadsheet (header = 1), dihitung termasuk baris kosong yang dilewati.
"""

import csv
import io
import json
import re
from decimal import Decimal, localcontext

MAX_INT_DIGITS = 15
MAX_FRAC_DIGITS = 6
SNIPPET_CHARS = 40
DELIMITERS = (",", ";", "\t", "|")

# Format Indonesia: titik pemisah ribuan, koma desimal. "1.5" ditolak karena ambigu.
_COMMA = re.compile(r"[+-]?(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,[0-9]+)?")
# Format internasional: koma pemisah ribuan, titik desimal.
_DOT = re.compile(r"[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?")


class InvalidOptions(ValueError):
    """Opsi pekerjaan tidak valid (tidak diulang)."""


class LimitExceeded(Exception):
    """Batas paket terlampaui (tidak diulang)."""


def aggregate_chunk(chunk_text: str, options_json: str, first_row: int) -> str:
    """Agregasi satu potongan CSV (tanpa header) menjadi hasil parsial JSON, atau JSON galat."""
    try:
        return _aggregate(chunk_text, options_json, first_row)
    except InvalidOptions as exc:
        return _error_json("INVALID_OPTIONS", str(exc))
    except LimitExceeded as exc:
        return _error_json("LIMIT_EXCEEDED", str(exc))
    except csv.Error as exc:
        return _error_json("CSV_ERROR", str(exc))


def _error_json(code, message):
    return json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=False, separators=(",", ":"))


def _aggregate(chunk_text, options_json, first_row):
    opts = _parse_options(options_json)
    columns = opts["columns"]
    group_idx = columns.index(opts["group_by"])
    value_col = opts["value_column"]
    value_idx = columns.index(value_col)
    max_groups = opts["max_groups"]
    pattern = _COMMA if opts["decimal"] == "comma" else _DOT

    groups = {}
    errors = []
    rows_read = 0
    rows_valid = 0
    reader = csv.reader(io.StringIO(chunk_text, newline=""), delimiter=opts["delimiter"])
    with localcontext() as ctx:
        ctx.prec = 40
        for offset, record in enumerate(reader):
            if not record:
                continue
            row_no = first_row + offset
            rows_read += 1
            if len(record) != len(columns):
                errors.append([row_no, "", "BAD_COLUMN_COUNT", _snippet(opts["delimiter"].join(record))])
                continue
            raw = record[value_idx]
            value, code = _parse_number(raw, pattern, opts["decimal"])
            if code is not None:
                errors.append([row_no, value_col, code, _snippet(raw)])
                continue
            key = record[group_idx]
            entry = groups.get(key)
            if entry is None:
                if len(groups) >= max_groups:
                    raise LimitExceeded(f"jumlah kelompok melebihi {max_groups}")
                groups[key] = [1, value]
            else:
                entry[0] += 1
                entry[1] += value
            rows_valid += 1

    result = {
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "groups": [[key, count, format(total, "f")] for key, (count, total) in groups.items()],
        "errors": errors,
    }
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _parse_options(options_json):
    try:
        opts = json.loads(options_json)
    except ValueError:
        # Pesan tetap (tanpa detail parser) agar port Rust bisa menghasilkan teks yang sama.
        raise InvalidOptions("opsi bukan JSON") from None
    if not isinstance(opts, dict):
        raise InvalidOptions("opsi harus objek JSON")
    columns = opts.get("columns")
    if not isinstance(columns, list) or not columns or not all(isinstance(c, str) for c in columns):
        raise InvalidOptions("columns harus daftar nama kolom")
    for key in ("group_by", "value_column"):
        if opts.get(key) not in columns:
            raise InvalidOptions(f"{key} tidak ada di columns")
    if opts.get("delimiter", ",") not in DELIMITERS:
        raise InvalidOptions("delimiter tidak didukung")
    if opts.get("decimal", "comma") not in ("comma", "dot"):
        raise InvalidOptions("decimal harus comma atau dot")
    max_groups = opts.get("max_groups", 100000)
    if not isinstance(max_groups, int) or isinstance(max_groups, bool) or max_groups < 1:
        raise InvalidOptions("max_groups harus bilangan bulat positif")
    return {
        "columns": columns,
        "group_by": opts["group_by"],
        "value_column": opts["value_column"],
        "delimiter": opts.get("delimiter", ","),
        "decimal": opts.get("decimal", "comma"),
        "max_groups": max_groups,
    }


def _parse_number(raw, pattern, decimal_mode):
    text = raw.strip(" \t")
    if text == "":
        return None, "EMPTY"
    if not pattern.fullmatch(text):
        return None, "NOT_A_NUMBER"
    if decimal_mode == "comma":
        norm = text.replace(".", "").replace(",", ".")
    else:
        norm = text.replace(",", "")
    int_part, _, frac = norm.lstrip("+-").partition(".")
    if len(int_part.lstrip("0")) > MAX_INT_DIGITS or len(frac) > MAX_FRAC_DIGITS:
        return None, "OUT_OF_RANGE"
    return Decimal(norm), None


def _snippet(text):
    return text[:SNIPPET_CHARS]
# >>> rust-anything: ops-rs is on. `rust-anything disable ../../../rust/ops-rs` removes this block.
def _rust_anything_ops_rs():
    import importlib, os, sys
    mode = os.environ.get("RUST_ANYTHING_MODE")
    if mode == "old" or os.environ.get("RUST_ANYTHING_UNIT_OPS") == "original":
        return
    at = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../rust/ops-rs/python"))
    sys.path.insert(0, at)
    try:
        native = importlib.import_module("ops_rs")
    except ImportError:
        if mode == "new":
            raise
        return
    finally:
        sys.path.remove(at)
    globals().update({name: getattr(native, name) for name in ["aggregate_chunk"]})


_rust_anything_ops_rs()
del _rust_anything_ops_rs
# <<< rust-anything: ops-rs
