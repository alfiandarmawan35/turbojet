"""Operasi ``preview``: kolom dan beberapa baris pertama untuk dipilih pengguna di portal."""

import csv
import io
import json

DELIMITERS = (",", ";", "\t", "|")


def detect_delimiter(header_line: str) -> str:
    """Pemisah yang paling sering muncul di luar tanda kutip pada baris header."""
    counts = {d: 0 for d in DELIMITERS}
    in_quote = False
    for ch in header_line:
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote and ch in counts:
            counts[ch] += 1
    best = max(DELIMITERS, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def preview(head_text: str, max_rows: int) -> str:
    """Kembalikan JSON ``{"delimiter", "columns", "rows"}`` dari awal berkas, atau JSON galat."""
    first_line = head_text.split("\n", 1)[0].rstrip("\r")
    delimiter = detect_delimiter(first_line)
    reader = csv.reader(io.StringIO(head_text, newline=""), delimiter=delimiter)
    columns = None
    rows = []
    try:
        for record in reader:
            if not record:
                continue
            if columns is None:
                columns = record
                continue
            if len(rows) >= max_rows:
                break
            rows.append(record)
    except csv.Error as exc:
        out = {"error": {"code": "CSV_ERROR", "message": str(exc)}}
    else:
        out = {"delimiter": delimiter, "columns": columns or [], "rows": rows}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))
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
    globals().update({name: getattr(native, name) for name in ["detect_delimiter", "preview"]})


_rust_anything_ops_rs()
del _rust_anything_ops_rs
# <<< rust-anything: ops-rs
