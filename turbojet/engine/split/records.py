"""Cari batas rekaman CSV di awal sebuah blok teks, sadar tanda kutip.

Aturan (sama dengan membaca berkas per baris dengan ``open(..., newline="")``):

* baris berakhir di ``\\r\\n``, ``\\r``, atau ``\\n`` (pemecahan baris ``io.StringIO(newline="")``);
* rekaman berakhir di akhir baris bila jumlah ``"`` sejak awal rekaman genap;
* baris terakhir blok yang belum final dan belum lengkap (tanpa akhir baris, atau berakhir ``\\r``
  yang mungkin bagian dari ``\\r\\n``) tidak dipakai;
* bila ``at_eof``, sisa teks (baris tanpa akhir, atau kutip yang tak tertutup) menjadi satu rekaman.

Posisi dihitung dalam karakter (indeks ``str`` Python), bukan byte.
"""

import io


def split_records(text: str, max_records: int, at_eof: bool) -> list:
    """``[karakter_terpakai, jumlah_rekaman]`` untuk paling banyak ``max_records`` rekaman utuh."""
    length = len(text)
    pos = 0
    count = 0
    if max_records <= 0:
        return [0, 0]
    end = 0
    in_quote = False
    for line in io.StringIO(text, newline=""):
        end += len(line)
        last = line[-1]
        terminated = last == "\n" or last == "\r"
        if end == length and not at_eof and (not terminated or last == "\r"):
            return [pos, count]
        if line.count('"') % 2:
            in_quote = not in_quote
        if terminated and not in_quote:
            count += 1
            pos = end
            if count == max_records:
                return [pos, count]
    if at_eof and pos < length:
        count += 1
        pos = length
    return [pos, count]
# >>> rust-anything: split-rs is on. `rust-anything disable ../../../rust/split-rs` removes this block.
def _rust_anything_split_rs():
    import importlib, os, sys
    mode = os.environ.get("RUST_ANYTHING_MODE")
    if mode == "old" or os.environ.get("RUST_ANYTHING_UNIT_SPLIT") == "original":
        return
    at = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../rust/split-rs/python"))
    sys.path.insert(0, at)
    try:
        native = importlib.import_module("split_rs")
    except ImportError:
        if mode == "new":
            raise
        return
    finally:
        sys.path.remove(at)
    globals().update({name: getattr(native, name) for name in ["split_records"]})


_rust_anything_split_rs()
del _rust_anything_split_rs
# <<< rust-anything: split-rs
