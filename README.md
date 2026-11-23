# TurboJet (tenant app)

Kerangka app Frappe `turbojet` sesuai [KONSEP_TURBOJET_FRAPPE_RUST.md](../KONSEP_TURBOJET_FRAPPE_RUST.md) v2.1.
App site induk `turbojet_control` belum dibuat.

## Isi

| Bagian | Lokasi | Status |
| --- | --- | --- |
| Engine (runner, kontrak berkas v1, CSV bertahap, encoding, potongan sadar kutip) | `turbojet/engine/` | Jalan, 59 tes lulus (jalur Rust dan Python, Windows dan Linux) |
| Operasi rujukan `group_sum` (target port Rust) dan `preview` | `turbojet/engine/ops/` | Jalan |
| DocType: Plan (+Limit), Settings, Quota Balance, Usage Entry, Job, Idempotency Key | `turbojet/turbojet/doctype/` | Terpasang di bench lokal v16.60 (`dev/`) |
| Hak paket, buku kuota (`FOR UPDATE`), idempotensi, siklus job (lease + fencing, heartbeat, retry, penyapu) | `turbojet/services/` | Alur job, kuota, idempotensi, penyapu teruji di bench lokal (`dev/README.md`) |
| API v1 (`preview_csv`, `create_import_job`, `job_status`, `list_jobs`, `cancel_job`) | `turbojet/api/v1.py` | preview_csv, create_import_job, job_status, list_jobs teruji (`bash dev/bench.sh smoke`); cancel_job belum |
| Beban bench untuk rust-anything | `bench/bench_group_sum.py` | Jalan |
| Rencana port | `rust/PLAN.md` | Dari `rust-anything analyze` |

Belum ada: portal (halaman www), site induk dan pembayaran, API key, log audit, email.

## Engine tanpa Frappe

```sh
python -m venv .venv && .venv/Scripts/python -m pip install pytest   # Linux: .venv/bin/python
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m turbojet.engine run --spec job.json --input data.csv --out out/attempt-1
.venv/Scripts/python -m turbojet.engine preview --input data.csv
.venv/Scripts/python bench/bench_group_sum.py 200000 1000
```

`job.json`:

```json
{"contract_version": 1, "operation": "group_sum",
 "options": {"group_by": "kota", "value_column": "total", "decimal": "comma"},
 "limits": {"max_rows": 100000, "max_groups": 10000, "max_columns": 200, "max_seconds": 600}}
```

Keluaran: `output.csv`, `errors.csv`, `result.json`, lalu `manifest.json` (SHA-256, ditulis terakhir).
Gagal: `failure.json` + kode keluar 2 (input), 3 (batas), 4 (internal, boleh diulang).
Progres: `progress.json` diperbarui tiap potongan; worker membacanya saat heartbeat.

## Bench lokal untuk uji

`bash dev/bench.sh up` lalu `bash dev/bench.sh smoke` (Docker; lihat [dev/README.md](dev/README.md)).

## Pasang ke Frappe (v15/v16)

```sh
bench get-app /path/ke/turbojet
bench --site dev.localhost install-app turbojet
bench --site dev.localhost set-config turbojet_engine_env '{"RUST_ANYTHING_MODE": "shadow"}' --parse
bench worker --queue long   # engine dijalankan dari antrean long
```

`after_install` membuat peran (Owner/Admin/Member), paket `free` dan `pro`, dan paket aktif `free`.

## Port ke Rust

Lihat [rust/README.md](rust/README.md).
