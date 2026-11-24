---
name: turbojet
description: TurboJet = TEMPLATE RESMI pembuatan aplikasi kita (Frappe + mesin Python/Rust lewat rust-anything). Buat aplikasi baru dari template, atau lanjutkan template/app turunannya dengan semua setup yang sudah ada — konsep, engine, app Frappe, port Rust, build Linux, uji, git. Pakai lewat /turbojet <tugas>, mis. "/turbojet app baru Kasir Kapal", "/turbojet tambah operasi dedupe", "/turbojet port unit baru", "/turbojet pasang ke bench", "/turbojet status".
disable-model-invocation: true
argument-hint: "<tugas: app baru <Judul> | status | operasi baru | port rust | build linux | pasang frappe | ...>"
---

# /turbojet

Tugas dari user: **$ARGUMENTS** (kosong = jalankan "Cek status" lalu tanya mau lanjut apa).
Jawab dalam Bahasa Indonesia.

**Keputusan user 23-11-2026: TurboJet Frappe + Rust adalah satu kesatuan template untuk membuat
aplikasi kita.** Aplikasi baru dimulai dari template ini (bagian 2a), bukan dari nol. Perbaikan yang
berlaku umum dikerjakan di template (monorepo `turbojet`, folder `template/`, branch `main`) lalu dibawa ke app turunan.

## 2a. Aplikasi baru dari template

```bash
python -I -X utf8 ~/.claude/skills/turbojet/scripts/buat_app.py --judul "Kasir Kapal"                       # -> monorepo apps/kasir_kapal
python -I -X utf8 ~/.claude/skills/turbojet/scripts/buat_app.py --judul "Kasir Kapal" --tujuan "<folder baru>"  # repo sendiri, MONOREPO
python -I -X utf8 ~/.claude/skills/turbojet/scripts/buat_app.py --judul "Kasir Kapal" --tujuan "<folder baru>" --datar  # repo sendiri tanpa monorepo
# opsi: --repo <monorepo, default C:/Users/alfian/Documents/turbojet> --ref <branch/commit, default main>
```
Skrip mengambil berkas ter-track folder `template/` dari git (`git archive`, jadi .venv/target tak ikut), mengganti
`turbojet`→`kasir_kapal`, `TurboJet`→`Kasir Kapal` (class `KasirKapalJob`), `TURBOJET`→`KASIR_KAPAL`
di nama folder, DocType, modul Frappe dan isi teks, memperbarui `root` di `rust-anything.json`, dan
menyalin modul native apa adanya (`ops_rs`/`split_rs` tetap). Tanya user dulu: judul app dan tujuan — di monorepo (`apps/<nama>`, bawaan)
atau repo sendiri (`--tujuan`).
App repo sendiri = MONOREPO (bawaan): `<tujuan>/apps/<nama>/` (app Frappe+engine+rust+dev), `<tujuan>/docs/`
(+ salinan konsep TurboJet), `<tujuan>/tools/`, README & .gitignore akar; paket lain (UI web, mobile, layanan) masuk
`apps/<nama>-web`, `apps/<nama>-mobile`, dst. Setelah itu:
1. `cd <folder app> && python -m venv .venv && .venv/Scripts/python -m pip install pytest`, lalu
   `pytest -q` (harus 59 lulus di `RUST_ANYTHING_MODE=new` dan `old`) dan `python -m <app>.engine ops`.
2. Ganti contoh: operasi `group_sum`/`preview`, API `create_import_job`, paket free/pro di `install.py`
   sesuai kebutuhan app; unit Rust contoh boleh dibuang (`rust-anything disable`, hapus crate, buang dari
   `build_linux.sh`) bila operasinya tak dipakai.
3. `git init` / branch baru + commit hanya bila user minta.
Teruji 23-11: app "Kasir Kapal" hasil skrip → 59/59 Windows (new & old) + Linux python:3.11, jalur rust.

## 0. Peta proyek

| Apa | Di mana |
|---|---|
| Repo | `C:\Users\alfian\Documents\turbojet` (origin `alfiandarmawan35/turbojet`, publik). Dulu folder `turbojet/` di branch `feature/turbojet` addons_sbi; riwayat dipindah 24-11 |
| Branch | `main`. Selalu di-push ke origin; cek `git log --oneline -5` |
| Konsep v2.1 | `KONSEP_TURBOJET_FRAPPE_RUST.md` (akar repo) — baca bagian terkait sebelum mendesain |
| Skill | `skill/` di repo ini (`SKILL.md`, `scripts/buat_app.py`); `~/.claude/skills/turbojet` = junction ke folder ini, jadi edit skill = edit repo |
| Monorepo | `template/` (app template), `skill/` (skill ini), `apps/` (app turunan di monorepo), `tools/pi/` (agen Claude Code mandiri generik: `agen.sh`, `agen@.service`, `cek-agen` + `/cek-agen`, `pasang.sh`), `KONSEP_TURBOJET_FRAPPE_RUST.md` |
| App template | `template/turbojet/` (paket app Frappe), `template/rust/` (crate), `template/bench/`, `template/dev/` (bench Docker) |
| Ringkasan | `README.md` (monorepo), `template/README.md`, `template/rust/README.md` (status unit, saklar, angka) |
| Memori | `turbojet-frappe-rust.md` di folder memori proyek |

Bagian app:
- `engine/` — Python murni, TANPA Frappe: `runner.py` (CLI `run|preview|ops|version`, kode keluar
  0 ok / 2 input / 3 batas / 4 internal), `contract.py` (kontrak berkas v1: spec JSON, `progress.json`,
  `result.json`, `failure.json`, `manifest.json` SHA-256 ditulis terakhir), `csvio.py` (encoding +
  `ChunkReader` blok 4 jt karakter), `registry.py` (`OPERATIONS`, `engine_path`, `describe`),
  `ops/group_sum.py` + `ops/preview.py` (unit Rust 1), `split/records.py` (unit Rust 2), `tests/`.
- `services/` — `entitlements.py` (paket & batas), `quota.py` (buku kuota `SELECT … FOR UPDATE`:
  reserve/commit/release/adjust), `idempotency.py` (claim/complete/purge), `jobs.py` (lease + fencing
  attempt, heartbeat, retry, `sweep` tiap menit, engine dijalankan sebagai subprocess
  `python -m turbojet.engine run`, env dari `frappe.conf["turbojet_engine_env"]`).
- `api/v1.py` — `preview_csv`, `create_import_job`, `job_status`, `list_jobs`, `cancel_job`.
- 7 DocType: Plan, Plan Limit, Settings, Quota Balance, Usage Entry, Job, Idempotency Key.
- `hooks.py` (after_install, cron sweep, purge harian), `install.py` (peran Owner/Admin/Member, paket free/pro).

Status (23-11-2026): engine + 59 tes jalan; ops-rs & split-rs GATE LULUS + DI-ENABLE; `.so` Linux
teruji py3.9/3.11/3.14; app terpasang di bench lokal Docker v16.60 (`dev/`), smoke 8/8 (job → rust,
kuota, idempotensi, penyapu). **Belum**: user non-admin, kuota habis, cancel saat jalan, lease mati, site induk `turbojet_control`, pembayaran Midtrans/Xendit, portal www, API key, audit log, email.

## 1. Cek status (selalu dulu)

```bash
cd /c/Users/alfian/Documents/turbojet && git status -sb | head
cd template
.venv/Scripts/python -m pytest -q -p no:cacheprovider | tail -1     # harus 59+ passed
.venv/Scripts/python -m turbojet.engine ops                          # path rust/python per unit
```
Bila `.venv` hilang: `python -m venv .venv && .venv/Scripts/python -m pip install pytest`.
Repo ini khusus TurboJet; app turunan punya repo sendiri.

## 2. Resep kerja

### Tambah operasi engine baru
1. Tulis fungsi murni di `engine/ops/<nama>.py` (teks blok + `options_json` masuk, string JSON keluar);
   galat dikembalikan sebagai data `{"error": {"code","message"}}`, bukan exception kustom.
2. Daftarkan di `registry.OPERATIONS`; tambah cabang di `runner.run` (sekarang hanya
   `_run_group_sum`) dan validasi spec di `contract.py`.
3. Tes di `engine/tests/` (pola tabel + runner end-to-end, cek hash output identik).
4. Bila perlu kuota/fitur baru: `install.py` (Plan Limit), `entitlements`, API di `api/v1.py`.
5. Ukur dengan pola `bench/bench_group_sum.py`; port ke Rust hanya bila jalur panas.

### Port unit ke Rust (rust-anything)
Panggil tool `Skill` dengan `skill: "rust-anything"` (atau `rust-anything:rust-anything`), lalu ikuti:
analyze → bridge → record → port `src/port.rs` → build → diff → fuzz → bench → gate → enable.
Jangan nyatakan selesai sebelum `gate` lulus. Aturan rumah:
- **Tanya user** sebelum `bridge` pertama dan sebelum `enable`/`disable` (mengubah source).
- Unit harus fungsi murni: generator/objek file/class ber-state tak bisa di-bridge → fungsi atas
  blok teks (contoh `split_records`). Registri/dispatcher di luar folder unit.
- Exception kustom tiba di Rust sebagai `ValueError` → galat sebagai data. Pesan galat deterministik
  (jangan teks dari `json`/`csv` bawaan Python).
- Rekam `--from-tests` + `inputs-realistic.jsonl` buatan sendiri; banding langsung ribuan panggilan,
  target 0 selisih. Desimal tiru `Decimal` (i128 skala 6, `-0`); posisi = indeks karakter, bukan byte.
- Jalur panas Python: `io.StringIO(newline="")` lebih cepat dari regex per baris.
- Saklar: `RUST_ANYTHING_MODE=old|new|shadow`, per unit `RUST_ANYTHING_UNIT_<UNIT>=original`.
- Uji tes di semua kombinasi saklar; tes jangan mengunci `engine_path=="python"`.
- Perbarui tabel status di `template/rust/README.md` dan `registry.describe()` untuk unit baru.

### Build & uji Linux (wajib setelah `port.rs` berubah)
```bash
cd /c/Users/alfian/Documents/turbojet/template
bash rust/build_linux.sh            # Docker maturin + cargo +stable → python/<mod>/_native.abi3.so
bash rust/test_linux.sh             # python:3.11-slim; juga coba python:3.14-slim, python:3.9-bullseye
```
Tambah crate baru ke `CRATES=(...)` di `build_linux.sh`. Docker Desktop harus jalan. JANGAN
`rust-anything package` (wheel memasang ulang `turbojet.engine.*`, bentrok). `.gitignore` crate
perlu `!python/*/_native.abi3.so` dan `!python/*/_native.pyd` agar modul ikut commit.

### Bench Frappe lokal (Docker) — uji setiap perubahan bagian Frappe di sini
```bash
cd <folder app>        # template: C:/Users/alfian/Documents/turbojet/template
bash dev/bench.sh up       # erpnext:v16.60.0 + mariadb + redis; site <app>.localhost, install-app, MODE=new
bash dev/bench.sh smoke    # API end-to-end: preview, idempotensi, job done via rust, CSV salah, list
docker compose -f dev/docker-compose.yml restart backend worker   # setelah ubah .py
bash dev/bench.sh migrate  # setelah ubah DocType
```
Browser: `http://<app>.localhost:8090` (Administrator/admin); `localhost:8090` = 404 (site dipilih dari
host; klien API kirim `X-Frappe-Site-Name`). App di-mount + `.pth`, tanpa pip. Cek DB:
`docker compose -f dev/docker-compose.yml exec -T worker bench --site <site> mariadb -e "..."`.
Stderr engine: `sites/<site>/private/turbojet_work/<job>/attempt-N/stderr.log` di container worker.
Path site Frappe relatif — jadikan absolut sebelum dioper ke subprocess.
Tambah skenario baru ke `dev/smoke.py` setiap fitur API baru.

### Pasang ke server Frappe (belum pernah ke server nyata)
```sh
bench get-app /path/ke/turbojet
bench --site <site> install-app turbojet
bench --site <site> set-config turbojet_engine_env '{"RUST_ANYTHING_MODE": "new"}' --parse
bench worker --queue long
```
Produksi: `RUST_ANYTHING_MODE=new` agar modul gagal muat = error, bukan diam ke Python.
Server Frappe lain milik user: `pid-pos-frappe-65` (65:8443, v16) — tanya dulu sebelum menyentuhnya.

## 3. Lingkungan laptop

- Rust 1.100 via rustup (winget) + VS Build Tools; di bash: `export PATH="$HOME/.cargo/bin:$PATH"`.
- Python: `python -I -X utf8` untuk skrip yang mencetak Unicode.
- Folder crate terkunci bila cwd di dalamnya → pindah direktori sebelum menghapus.
- Git repo besar: commit bisa >2 menit; jalankan di latar belakang.

## 4. Aturan umum

- Commit/push hanya bila diminta; pesan commit Bahasa Indonesia; repo `turbojet` branch `main`.
- Skill `tim-10-agen` hanya bila user memanggilnya.
- Setelah kerja: perbarui README terkait + memori `turbojet-frappe-rust.md`; laporkan ringkas
  (apa berubah, tes N/N, bench, yang belum diuji).
