# Port Rust dengan rust-anything

## Status unit 1: `turbojet/engine/ops/` → crate `ops-rs` — GATE LULUS (23-11-2026)

| Bukti | Hasil |
| --- | --- |
| `diff` | 2260/2260 kasus cocok (pytest + kasus buatan + 996 input CSV realistis `inputs-realistic.jsonl`) |
| `fuzz` | 469/469 input baru cocok |
| Banding langsung | 32.038 panggilan dari 4 seed baru, 0 selisih |
| `bench` (kasus kecil, biaya bridge termasuk) | `aggregate_chunk` 2,18×, `preview` 2,30×, `detect_delimiter` 4,74× |
| Runner penuh, 200.000 baris | Python 0,53 s → Rust 0,31 s (1,72×), output & errors identik byte demi byte |
| Runner penuh, 1.000.000 baris / 10.000 grup | Python 3,10 s → Rust 1,98 s (1,56×), identik |
| `gate` | fmt, clippy `-D warnings`, cargo test, tanpa `unsafe`, tanpa panic, ukuran 3,2× (batas 3× + 50 baris) |
| Laporan PR | `ops-rs/report/REPORT.md`, `ops-rs/report/card.svg` |

**DI-`enable` 23-11-2026.** Blok bertanda `# >>> rust-anything: ops-rs` ada di
`turbojet/engine/ops/group_sum.py` dan `preview.py`; `rust-anything disable rust/ops-rs` menghapusnya persis.
26 tes lulus di kedua jalur. Bench runner 1 juta baris (3 kali): Rust ±2,0 s, Python ±3,0 s.

| Saklar | Efek |
| --- | --- |
| (tanpa env) | Rust bila modul `rust/ops-rs/python/ops_rs` ada; bila tidak, diam-diam kembali ke Python |
| `RUST_ANYTHING_MODE=new` | Wajib Rust; gagal impor = error (pakai di produksi agar tidak diam-diam lambat) |
| `RUST_ANYTHING_UNIT_OPS=original` atau `RUST_ANYTHING_MODE=old` | Paksa Python |

### Windows dan Linux

Tiap crate menyimpan dua modul native berdampingan di `python/<modul>/`, dan Python memilih sendiri:

| Berkas | Untuk | Cara build |
|---|---|---|
| `_native.pyd` | Windows (laptop dev) | `rust-anything build rust/<crate>` |
| `_native.abi3.so` | Linux x86_64, glibc ≥ 2.17, Python ≥ 3.9 | `bash rust/build_linux.sh` (Docker, image `ghcr.io/pyo3/maturin`, toolchain stable) |

`rust-anything package` sengaja tidak dipakai: wheel-nya memasang `turbojet.engine.ops` dan
bertabrakan dengan app. Uji Linux: `bash rust/test_linux.sh [image]`. Hasil 23-11: python:3.11-slim,
3.14-slim, dan 3.9-bullseye (glibc 2.31) semuanya 59/59 di mode `new` dan `old`. Simbol glibc
tertinggi yang dipakai 2.14. Runner 1 jt baris di Linux: Rust 1,37–1,50 s, Python 3,17 s.

**Worker produksi: set `RUST_ANYTHING_MODE=new`** (lewat `turbojet_engine_env` di site_config),
supaya modul native yang gagal dimuat langsung menjadi error, bukan diam-diam jatuh ke Python.
Setelah `port.rs` berubah, jalankan ulang `build_linux.sh` dan commit kedua berkas.

Kenaikan runner penuh lebih kecil dari `bench` karena pemotongan CSV (`csvio.iter_records` /
`iter_chunks`), penggabungan `Decimal`, dan penulisan CSV masih Python. Kandidat unit 2:
`turbojet/engine/csvio.py` (port `iter_chunks` bersama `iter_records`, saran `profile`).

## Status unit 2: `turbojet/engine/split/` → crate `split-rs` — GATE LULUS, DI-ENABLE (23-11-2026)

`csvio.py` lama (generator `iter_records`/`iter_chunks` atas objek file) tidak bisa di-bridge.
Didesain ulang: fungsi murni `split.records.split_records(text, max_records, at_eof) ->
[karakter_terpakai, jumlah_rekaman]` + `csvio.ChunkReader` yang membaca blok 4 juta karakter.
Python rujukan memakai pemecahan baris `io.StringIO(newline="")` (C) + hitung kutip per baris —
dua percobaan regex lebih dulu ternyata 1,5–2,8x lebih lambat, jadi dibuang.

| Bukti | Hasil |
| --- | --- |
| `diff` | 1820/1820 (pytest termasuk ukuran blok 1–7 karakter + 800 input acak) |
| `fuzz` | 158/158 |
| Banding langsung | 50.000 input dari 5 seed baru, 0 selisih |
| `bench` (kasus kecil) | 2,17× |
| `gate` | lulus, 73 baris Rust untuk 37 baris Python |
| Runner 1 juta baris (terbaik dari 3) | semua Python 2,89 s → ops Rust 2,02 s → ops+split Rust **1,70 s**, hash hasil sama |

Di-enable: blok `# >>> rust-anything: split-rs` di `split/records.py`. 59 tes lulus di 4 kombinasi saklar. Saklar: `RUST_ANYTHING_UNIT_SPLIT=original`; `RUST_ANYTHING_MODE=old` mematikan kedua unit. `python -m turbojet.engine ops` menampilkan jalur kedua unit. Bench `bench_group_sum.py` 1 juta baris: 1,79–1,86 s (Rust) vs 2,88 s (`MODE=old`).

## Keputusan desain yang lahir dari port

- **Galat sebagai data.** rust-anything tidak bisa membuat kelas exception milik sumber
  (`InvalidOptions(ValueError)`); dari Rust semuanya tiba sebagai `ValueError`. Maka operasi
  mengembalikan `{"error": {"code", "message"}}` (`INVALID_OPTIONS`, `LIMIT_EXCEEDED`, `CSV_ERROR`)
  dan runner yang menerjemahkan. Jalur Python dan Rust identik, tak ada exception yang menyeberang.
- **Pesan galat tanpa detail parser** (`opsi bukan JSON`), karena teks galat `json` Python dan
  serde_json tidak mungkin sama.
- **Registri di `engine/registry.py`**, di luar unit, agar bridge hanya berisi fungsi murni.
- **Parser CSV ditulis tangan** meniru mesin status `_csv.c` CPython (bukan crate `csv`): urutan
  galat juga ditiru — galat batas sel CSV hanya muncul bila pembacaan sampai ke baris itu.

## Aturan paritas

- CSV seperti `csv.reader(io.StringIO(text, newline=""))`: baris dipecah di `\n`, `\r`, `\r\n`;
  kutip ganda `""`; kutip liar di tengah sel tetap jadi isi; batas sel 131.072 karakter.
- Baris kosong dilewati tapi tetap menaikkan nomor baris.
- Angka hanya digit ASCII; `strip` hanya spasi dan tab; `1.5` ditolak di format koma.
- Penjumlahan desimal eksak skala ≤ 6 (i128), skala terbesar dipertahankan, `-0` seperti `Decimal`,
  format tanpa eksponen (`format(x, "f")`).
- Urutan kelompok sesuai kemunculan pertama.
- JSON ringkas tanpa escape non-ASCII, urutan kunci `rows_read, rows_valid, groups, errors`.

## Mengulang

```sh
rust-anything doctor
rust-anything record rust/ops-rs --from-tests --inputs rust/ops-rs/inputs-realistic.jsonl -- .venv/Scripts/python -m pytest -q turbojet/engine/tests
rust-anything build rust/ops-rs
rust-anything diff rust/ops-rs
rust-anything fuzz rust/ops-rs
rust-anything bench rust/ops-rs
rust-anything gate rust/ops-rs
rust-anything report rust/ops-rs
```

Setelah mengubah operasi Python: `rust-anything map` menandai rekaman basi → `record` ulang → `diff`.
