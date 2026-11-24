# TurboJet — template SaaS dengan Frappe dan Rust

**Status:** konsep produk dan rancangan teknis v2.1, 23 November 2026. Dokumen ini menjadi acuan untuk membangun template baru dari awal. Versi v2 menutup celah v1 (pendaftaran multi-site, rute webhook, kontrak engine, kuota atomik) dan menambah kemampuan platform SaaS. Versi v2.1 menetapkan rust-anything sebagai cara membangun mesin Rust.

## Tujuan produk

TurboJet adalah starter kit untuk membuat aplikasi SaaS yang bisa menerima pelanggan, menagih, menjalankan pekerjaan berat dengan cepat, dan membantu admin menjelaskan setiap rupiah dan setiap kegagalan. Produk pertama yang dibangun dari template harus bisa membawa pengguna dari pendaftaran sampai memperoleh hasil pekerjaan. Produk kedua harus bisa memakai kembali akun, pembayaran, kuota, API, dan pekerjaan latar belakang hanya dengan menambahkan fitur bisnisnya sendiri.

Keputusan inti: **Frappe Framework sebagai fondasi aplikasi** dan **Rust sebagai mesin pemrosesan data**, dibangun dengan **rust-anything**: setiap operasi ditulis dulu di Python sebagai rujukan, lalu dipindah ke Rust satu unit demi satu dan baru dipakai setelah terbukti identik. Rancangan ini mandiri dari proyek lama. Nama TurboJet adalah nama kerja. Produk TurboJet HilmiRF menjadi referensi untuk pengalaman memulai proyek dan kelengkapan paket SaaS.

### Prinsip desain

1. **Uang dan hak hanya diputuskan di satu tempat.** Frappe memegang paket, kuota, dan pembayaran. Rust tidak pernah tahu soal uang.
2. **Setiap operasi yang berefek boleh diulang.** Semua tombol, webhook, dan pekerjaan memakai kunci idempotensi, sehingga pengulangan aman.
3. **Buku besar, bukan angka saldo.** Kuota dan kredit dicatat sebagai entri yang tidak diubah. Saldo adalah hasil penjumlahan dan bisa diaudit.
4. **Setiap permintaan bisa ditelusuri.** Satu `request_id` mengikat portal → transaksi → pembayaran → kuota → percobaan worker → berkas hasil.
5. **Fitur baru = spesifikasi + operasi.** Developer tidak menulis ulang akun, izin, antrean, atau penagihan.
6. **Rust hanya setelah terbukti.** Operasi Python adalah rujukan. Port Rust baru dinyalakan bila `rust-anything gate` lulus dan `bench` menunjukkan lebih cepat.

## Arsitektur

Template terdiri dari dua *custom Frappe app* yang dipasang lewat Bench, ditambah crate Rust (PyO3) yang dibangun dengan rust-anything.

| App / komponen | Dipasang di | Tanggung jawab |
| --- | --- | --- |
| `turbojet_control` | Satu **site induk** (control plane), mis. `app.turbojet.id` | Halaman produk dan harga, pendaftaran, pembuatan site pelanggan, katalog paket induk, penerimaan webhook pembayaran, faktur, rekonsiliasi, panel admin lintas site, pemantauan kesehatan semua site. |
| `turbojet` | Setiap **site pelanggan** (tenant), mis. `acme.turbojet.id` | Portal anggota, undangan, peran, hak paket (salinan dari induk), buku kuota, pekerjaan, berkas privat, API key, webhook keluar, log audit. |
| Engine (`turbojet.engine` + crate `rust/*-rs`) | Setiap host worker | Runner Python dalam subprocess membaca input pekerjaan, menjalankan operasi (Python rujukan atau port Rust PyO3 hasil rust-anything), menulis hasil dan manifest. |
| Redis + RQ worker Frappe | Bench | Antrean `short` (notifikasi, sinkron hak), `default` (pekerjaan kecil), `long` (impor besar). |
| Penyimpanan objek (S3-compatible, opsional) | Infrastruktur | Berkas privat besar dan backup terenkripsi per site. |

**Satu site per organisasi** tetap dipertahankan: database, pengguna, dan berkas privat terpisah, sehingga pemulihan satu pelanggan tidak menyentuh pelanggan lain. Biayanya, migrasi dan pemantauan harus mencakup setiap site. Karena itu site induk menyimpan **registri site** (versi app, versi engine, status migrasi, umur backup terakhir) dan menjalankan migrasi bergelombang.

```
Browser ──► app.turbojet.id (turbojet_control)
             │  daftar, bayar, webhook PG, faktur, registri site
             │  ── API internal bertanda tangan (HMAC + nonce) ──►
             ▼
          acme.turbojet.id (turbojet)  ──enqueue──►  RQ worker ──subprocess──► engine
             portal, kuota, job, API key, audit         lease + fencing     runner Python → ops (Rust via PyO3)
```

### Komunikasi induk ↔ tenant

- Induk → tenant: `entitlement.sync` (paket, batas, periode) dan `site.suspend/resume`. Dikirim sebagai job `short` dengan kunci idempotensi `event_id`. Tenant menyimpan **versi hak** dan menolak pembaruan dengan versi lebih lama.
- Tenant → induk: `usage.report` berkala (untuk paket metered dan dasbor) dan `health.ping`.
- Semua panggilan memakai rahasia per site (dibuat saat provisioning, disimpan di `site_config.json`), tanda tangan HMAC-SHA256 atas body + timestamp + nonce, dan jendela waktu 5 menit.
- Jika induk mati, tenant tetap berjalan dengan hak terakhir yang dimiliki. Pembayaran yang masuk selama induk mati diproses ulang oleh rekonsiliasi.

## Pendaftaran dan provisioning

1. Calon pelanggan mengisi nama organisasi, subdomain, email, dan paket di site induk. Subdomain dicek unik dan tidak masuk daftar kata terlarang.
2. Induk membuat **TurboJet Tenant** berstatus `provisioning` lalu menjalankan job: `bench new-site` (atau pengambilan dari **pool site siap pakai** agar pendaftaran selesai dalam hitungan detik), `install-app turbojet`, penulisan rahasia, pembuatan pemilik organisasi, dan sinkron hak awal.
3. Pengguna menerima tautan masuk sekali pakai (berlaku 15 menit) ke site barunya. Halaman pendaftaran menampilkan progres provisioning lewat realtime Frappe.
4. Bila provisioning gagal di langkah mana pun, job dapat diulang dari langkah terakhir yang tercatat. Site setengah jadi tidak pernah diberikan ke pengguna.

Domain: subdomain wildcard dengan TLS wildcard di rilis awal. Domain kustom milik pelanggan (verifikasi CNAME + TLS otomatis) masuk rilis berikutnya.

## Pembayaran dan penagihan

- **Adapter penyedia** dengan antarmuka yang sama: `create_checkout`, `verify_webhook`, `fetch_transaction`, `refund`. Rilis awal: **simulator lokal** dan **satu penyedia nyata** — usulan Midtrans atau Xendit untuk pasar Indonesia (QRIS, VA bank, e-wallet, kartu).
- Webhook selalu masuk ke **site induk**. Induk memverifikasi tanda tangan, menyimpan **Payment Event** dengan kunci unik `(provider, provider_event_id)`, mencocokkan pesanan, penerima, nominal, dan mata uang, lalu memicu `entitlement.sync` ke tenant.
- **Mesin status pesanan:** `pending → paid → (refunded | partially_refunded)`, plus `expired`/`failed`. Transisi hanya maju. Notifikasi lama tidak bisa menurunkan status yang sudah `paid`.
- **Rekonsiliasi berkala** (mis. tiap 10 menit untuk pesanan pending < 24 jam, lalu harian) bertanya langsung ke penyedia. Ini menutup kasus webhook hilang.
- **Model bisnis yang didukung:** gratis dengan kuota percobaan, langganan bulanan/tahunan, kredit prabayar, dan **metered** (bayar sesuai pemakaian, ditagih di akhir periode dari Usage Entry). Perpindahan paket di tengah periode memakai prorata yang bisa dimatikan.
- **Faktur** bernomor urut tanpa celah per periode, PDF, pajak yang dapat dikonfigurasi (tarif PPN, NPWP pelanggan opsional), dan riwayat yang bisa diunduh pelanggan.
- **Dunning:** langganan yang gagal diperpanjang masuk masa tenggang (default 7 hari, bisa diatur) dengan email pengingat, lalu site dibekukan ke mode baca saja — data tidak dihapus.

## Hak, kuota, dan idempotensi

**Hak (entitlement)** adalah salinan paket di tenant: fitur yang diizinkan, batas per fitur per periode, batas pekerjaan aktif, batas ukuran berkas, dan batas laju API. Semua pemeriksaan akses membaca satu fungsi `turbojet.entitlements.check(feature, amount)` sehingga portal, API, dan generator memakai aturan yang sama.

**Buku kuota** memakai Usage Entry yang hanya ditambah, dengan jenis `reserve`, `commit`, `release`, `grant`, `adjust`. Untuk mencegah balapan, setiap pasangan (site, fitur, periode) punya satu baris **TurboJet Quota Balance** yang dikunci:

```python
with frappe.db.transaction():                       # satu transaksi
    bal = lock_balance(feature, period)              # SELECT ... FOR UPDATE
    if bal.available < amount: raise QuotaExceeded
    job = create_job(...); reserve(bal, job, amount) # job + reservasi bersama
frappe.enqueue(run_job, job=job.name, enqueue_after_commit=True)
```

**Kunci idempotensi:** tabel **TurboJet Idempotency Key** dengan kunci unik `(user, operation, client_key)` dan hash input. Pengulangan dengan input yang sama mengembalikan hasil yang tersimpan; input berbeda dengan kunci yang sama ditolak dengan kode `IDEMPOTENCY_CONFLICT`. Kunci kedaluwarsa setelah 24 jam.

## Pekerjaan latar belakang

**Mesin status Job:** `queued → leased → running → publishing → done`, dengan cabang `retry_wait`, `failed`, dan `cancelled`.

- **Lease + fencing token.** Worker mengambil hak eksekusi dengan `UPDATE ... SET lease_owner, lease_until, attempt = attempt + 1 WHERE name = ? AND (lease_until IS NULL OR lease_until < now())`. Nomor `attempt` adalah fencing token: hanya pemegang `attempt` terbaru yang boleh menerbitkan hasil, commit kuota, dan menandai `done` dalam satu transaksi.
- **Heartbeat** memperpanjang lease selama Rust berjalan. Worker yang mati otomatis kehilangan lease.
- **Penyapu berkala** (scheduler Frappe tiap menit) menjadwalkan ulang job `queued` yang tidak bergerak dan job dengan lease kedaluwarsa, serta membersihkan direktori kerja yatim.
- **Retry** dengan backoff eksponensial + jitter, maksimal N percobaan (default 3). Kesalahan input (kode keluar 2) tidak diulang; kesalahan sementara (kode 4, timeout) diulang.
- **Keadilan antar site:** batas pekerjaan aktif per site dari hak paket, ditambah slot cadangan global agar site lain tidak kelaparan. Pekerjaan yang melampaui batas tetap `queued` dan portal menampilkan posisi antrean.
- **Pembatalan** oleh pengguna: status `cancel_requested`, worker mengirim SIGTERM ke engine, reservasi dilepas satu kali.
- **Progres realtime**: engine menulis baris progres JSON ke stderr; worker meneruskannya ke portal lewat `frappe.publish_realtime` (dibatasi maksimal 1 pembaruan per detik).

## Mesin pemrosesan — Python rujukan, Rust lewat rust-anything

Engine **tidak ditulis langsung di Rust**. Setiap operasi ditulis dulu sebagai fungsi Python murni di app `turbojet`, lalu bagian yang panas dipindah ke Rust memakai **[rust-anything](https://crates.io/crates/rust-anything)** (v3.3.0, sudah terpasang di laptop pengembang). Python menjadi *oracle*: perilakunya direkam, Rust harus menghasilkan jawaban yang sama persis, dan satu operasi baru boleh memakai Rust setelah `gate` lulus.

Alasannya:
- Fitur baru bisa langsung jalan di Python pada hari pertama, tanpa menunggu port Rust.
- Kebenaran Rust dibuktikan oleh kasus yang direkam dari Python, bukan klaim. Selisih = bug di port, bukan di rekaman.
- Python tetap ada sebagai jalur cadangan. Satu saklar mengembalikan operasi ke Python bila Rust bermasalah di produksi.
- Hanya bagian yang terbukti lambat yang dipindah. `profile` dan `bench` yang memutuskan, bukan dugaan.

### Struktur kode

```
apps/turbojet/turbojet/engine/
  runner.py            # titik masuk subprocess: python -m turbojet.engine run --spec ...
  contract.py          # baca job.json, tulis result.json / errors.csv / manifest.json
  ops/
    group_sum.py       # operasi rujukan (Python murni, tanpa import Frappe)
    preview.py
  tests/               # pytest: golden file + kasus tepi → sumber rekaman
apps/turbojet/rust/
  group_sum-rs/        # crate hasil `rust-anything bridge` (PyO3); port di src/port.rs
  preview-rs/
apps/turbojet/bench/
  bench_group_sum.py   # beban nyata untuk `profile` dan `bench`
```

Aturan menulis operasi agar mudah dipindah: fungsi di `ops/` **murni** (tanpa Frappe, tanpa I/O database), argumen dan hasil berupa tipe sederhana (`str`, `int`, `float`, `bool`, `list`, `dict` dari JSON), dan **nilai uang dikirim/dikembalikan sebagai string desimal** (di dalam Python memakai `Decimal`, di Rust `rust_decimal`) supaya hasil keduanya identik byte demi byte. Kesalahan yang disengaja **dikembalikan sebagai data** (`{"error": {"code": "INVALID_OPTIONS", "message": "..."}}`), bukan dilempar sebagai exception: rust-anything tidak bisa membuat kelas exception milik sumber, sehingga dari Rust semua galat tiba sebagai `ValueError`. Runner yang menerjemahkan kode galat menjadi kode keluar (terbukti saat port unit pertama, 23-11-2026). Penjumlahan di port memakai desimal eksak i128, bukan `rust_decimal`.

Unit yang dipindah ke Rust adalah **pemrosesan satu potongan data** (mis. `aggregate_chunk(csv_text, options_json) -> result_json`), bukan fungsi per baris. Fungsi kecil yang dipanggil sekali per baris lebih mahal di-bridge daripada isinya; `profile` akan menyarankan memindahkan pemanggilnya atau memakai batch (`--batch fn:param`) yang berjalan di semua core.

### Siklus per operasi

| Langkah | Perintah | Hasil yang disimpan di repo |
| --- | --- | --- |
| 0. Ukur | `rust-anything profile apps/turbojet -- python bench/bench_group_sum.py` | Daftar fungsi panas + saran (port pemanggil / batch). |
| 1. Rencana | `rust-anything analyze apps/turbojet -o rust/PLAN.md` | Urutan unit, risiko per `file:line`, unit yang tetap di Python (`keep`). |
| 2. Bridge | `rust-anything bridge apps/turbojet <unit-id>` | Crate PyO3 `rust/<op>-rs/`. Hanya `src/port.rs` yang ditulis tangan. |
| 3. Rekam | `rust-anything record rust/<op>-rs --from-tests -- pytest turbojet/engine/tests` ditambah `--inputs` berisi CSV nyata (format desimal Indonesia, BOM, Windows-1252, baris rusak) | `cases.jsonl` = suite karakterisasi. |
| 4. Port | Tulis `src/port.rs` (crate `csv`, `rust_decimal`, `indexmap` bila urutan grup sampai ke output). | Kode Rust. |
| 5. Buktikan | `build` → `diff` (harus N/N) → `fuzz` (input baru di luar rekaman) → `bench` (Python vs Rust termasuk biaya bridge) | Angka cocok dan kecepatan. |
| 6. Uji bayangan | `rust-anything shadow rust/<op>-rs`, jalankan di staging dengan `RUST_ANYTHING_MODE=shadow` | Hasil tetap dari Python, selisih Rust dilaporkan. |
| 7. Gerbang | `rust-anything gate rust/<op>-rs` | fmt, clippy tanpa warning, tes, tanpa `unsafe`/`unwrap` liar, semua jalur error tercapai, semua kasus cocok. |
| 8. Nyalakan | `rust-anything enable rust/<op>-rs` (blok bertanda di kode Python, bisa dihapus persis dengan `disable`) | Operasi memakai Rust untuk semua pemanggil. |
| 9. Laporkan | `rust-anything report rust/<op>-rs` | `report/REPORT.md` + `card.svg` untuk PR: kasus cocok, speedup, mesin uji. |

Selisih yang **disengaja** (mis. Rust memperbaiki bug Python) hanya boleh dicatat di `known-diffs.jsonl` setelah disetujui pemilik produk, dan Python rujukan ikut diperbaiki. Setelah mengubah operasi Python, `rust-anything map` menandai port mana yang rekamannya basi; CI menolak rilis bila ada.

### Saklar produksi

| Saklar | Efek |
| --- | --- |
| `RUST_ANYTHING_MODE=shadow` | Hasil dari Python, Rust dijalankan berdampingan dan selisihnya dicatat sebagai metrik `engine_shadow_mismatch`. Dipakai di staging dan di minggu pertama produksi. |
| `RUST_ANYTHING_MODE=new` | Hasil dari Rust (mode normal setelah shadow bersih). |
| `RUST_ANYTHING_UNIT_<UNIT>=original` (mis. `RUST_ANYTHING_UNIT_OPS` untuk crate `ops-rs`) | Satu unit kembali ke Python tanpa deploy. Worker juga bisa menyetelnya untuk satu job ketika percobaan Rust gagal dengan kode internal. |

Job mencatat **jalur yang dipakai** (`python` / `rust`) dan versi crate, sehingga `trace` bisa menjelaskan dari mana sebuah angka berasal.

### Kontrak pemanggilan

Isolasi tetap dari subprocess: worker menjalankan runner Python di proses terpisah, dan runner itu memanggil operasi (yang di dalamnya sudah Rust bila di-enable). Dengan begitu batas memori, batas waktu, direktori kerja, dan sandbox tetap berlaku, sementara Rust berjalan in-process di dalam runner lewat PyO3 tanpa biaya serialisasi tambahan.

```
python -m turbojet.engine run --spec job.json --input input.csv --out <workdir>/attempt-<n>/
python -m turbojet.engine ops       # daftar operasi + skema opsi + jalur aktif (python/rust)
python -m turbojet.engine version   # versi kontrak, versi app, versi tiap crate Rust
```

| Berkas | Isi |
| --- | --- |
| `job.json` (masuk) | `contract_version`, `operation` (mis. `group_sum`), `options` (kolom grup, kolom angka, pemisah, encoding, format desimal `1.234,56` atau `1,234.56`), `limits` (baris, kolom, grup, memori, waktu). |
| `result.json` (keluar) | Ringkasan: baris dibaca, valid, ditolak, hasil agregat, durasi, memori puncak. |
| `errors.csv` (keluar) | Nomor baris, kolom, kode alasan (`EMPTY`, `NOT_A_NUMBER`, `TOO_MANY_COLUMNS`, ...), cuplikan nilai yang dipotong. |
| `output.*` (keluar) | Hasil utama (CSV/XLSX/Parquet tergantung operasi). |
| `manifest.json` (keluar, ditulis terakhir) | Daftar berkas + SHA-256 + versi engine + jalur (`python`/`rust`). Worker hanya menerbitkan hasil bila manifest ada dan checksum cocok. |

**Kode keluar:** `0` sukses, `2` input tidak valid (tidak diulang), `3` batas terlampaui (tidak diulang, pesan jelas ke pengguna), `4` kesalahan internal/sementara (boleh diulang), sinyal/timeout = sementara.

### Kemampuan

- **Streaming**: runner membaca CSV per potongan (mis. 50.000 baris) dan memberikan setiap potongan ke operasi; memori sebanding dengan jumlah grup, bukan jumlah baris. Deteksi encoding (UTF-8, UTF-8 BOM, Windows-1252) dan pemisah dilakukan di runner.
- **Paralel**: port Rust boleh memakai `rayon` di dalam satu potongan, atau operasi didaftarkan sebagai batch rust-anything agar potongan diproses di semua core. Hasil tetap deterministik: urutan grup stabil (`indexmap`) dan penjumlahan desimal dengan `rust_decimal`, sehingga `diff` terhadap Python tetap N/N.
- **Registri operasi**: satu operasi = satu fungsi Python di `ops/` + skema opsi + (opsional) satu crate Rust. Menambah laporan kedua = menambah operasi Python dan spesifikasi fitur di Frappe; port Rust menyusul bila `profile` menunjukkan perlu.
- **Sandbox**: runner berjalan sebagai pengguna OS tanpa hak, direktori kerja khusus per percobaan, tanpa jaringan (namespace/seccomp di Linux bila tersedia), `rlimit` memori dan CPU, batas waktu dari worker. Port Rust dilarang memakai `unsafe` kecuali terisolasi dengan komentar `// SAFETY:` (dicek oleh `gate`).
- **Uji berlapis**: golden test pytest untuk Python rujukan → rekaman `cases.jsonl` → `diff` Rust → `fuzz` dengan seed baru → `shadow` di staging. Rekaman diperbarui setiap operasi Python berubah.
- **Distribusi**: `rust-anything package` menyiapkan wheel per platform dan workflow CI (tanpa menerbitkan). Image worker memasang wheel itu; tanpa wheel, operasi otomatis berjalan di Python.

Opsi masa depan bila beban menuntut: memindahkan runner seluruhnya ke Rust (alur *whole app* rust-anything: `app record` → `app front-door` → `app lift`) atau menjadikannya layanan terpisah. Kontrak berkas di atas tetap dipertahankan supaya uji dan riwayat tetap valid.

## Kemampuan platform tambahan

| Kemampuan | Rilis | Ringkasan |
| --- | --- | --- |
| API publik + API key | R1 | Key per organisasi dengan scope (`jobs:write`, `jobs:read`, `billing:read`), hanya hash yang disimpan, bisa dirotasi/dicabut. Endpoint REST berversi `/api/v1/` memakai `check()` yang sama dengan portal. Batas laju per key dari hak paket. |
| Log audit | R1 | Setiap perubahan peran, paket, koreksi kredit, unduhan berkas, dan impersonasi tercatat dengan pelaku, alasan, `request_id`, dan IP. Tidak bisa diubah dari Desk. |
| Email transaksional | R1 | Undangan, verifikasi, pekerjaan selesai/gagal, faktur, pengingat dunning. Template per bahasa, antrean email Frappe. |
| Bahasa id/en | R1 | Semua teks portal lewat terjemahan Frappe. Bahasa default dipilih saat konfigurasi produk. |
| Webhook keluar ke pelanggan | R2 | Kejadian `job.completed`, `job.failed`, `subscription.updated`; tanda tangan HMAC, retry bertahap, log pengiriman yang bisa diulang dari portal. |
| Impersonasi admin | R2 | Admin dapat masuk sebagai pengguna untuk dukungan, wajib alasan, ada banner, dan tercatat di log audit pelanggan. |
| Feature flag | R2 | Fitur bisa dinyalakan per paket, per site, atau bertahap (persentase) tanpa deploy ulang. |
| Ekspor dan penghapusan data | R2 | Pemilik organisasi bisa mengunduh seluruh datanya dan meminta penghapusan akun, sejalan dengan UU Pelindungan Data Pribadi. |
| Domain kustom, SSO (OIDC/Google Workspace) | R3 | Untuk paket bisnis. |

## Model data

| DocType | Lokasi | Informasi yang disimpan |
| --- | --- | --- |
| TurboJet Tenant | Induk | Subdomain, site, status (`provisioning`, `active`, `grace`, `suspended`, `deleted`), versi app & engine, umur backup terakhir, rahasia (terenkripsi). |
| TurboJet Plan | Induk (sumber) → tenant (salinan) | Kode paket, harga, periode, model tagih, fitur, batas tiap fitur, batas laju, batas pekerjaan aktif. |
| TurboJet Order / Invoice | Induk | Pesanan checkout, nominal, mata uang, status, nomor faktur, pajak. |
| TurboJet Payment Event | Induk | Penyedia, ID kejadian unik per penyedia, referensi transaksi, payload terverifikasi, hasil pemrosesan. |
| TurboJet Subscription | Induk (sumber) → tenant (salinan) | Paket aktif, periode berlaku, status, referensi pelanggan di penyedia, versi hak. |
| TurboJet Quota Balance | Tenant | Satu baris per (fitur, periode): tersedia, direservasi, terpakai. Baris yang dikunci saat reservasi. |
| TurboJet Usage Entry | Tenant | Jenis (`reserve`, `commit`, `release`, `grant`, `adjust`), jumlah, rujukan ke Job atau koreksi admin + alasan. |
| TurboJet Job | Tenant | Pemilik, jenis, spesifikasi, berkas input/hasil, status, attempt, lease, progres, kode kesalahan, versi engine. |
| TurboJet Idempotency Key | Tenant & induk | Pengguna, operasi, kunci klien, hash input, rujukan hasil, kedaluwarsa. |
| TurboJet API Key | Tenant | Prefix, hash, scope, pembuat, terakhir dipakai, dicabut. |
| TurboJet Audit Log | Tenant & induk | Pelaku, aksi, objek, alasan, `request_id`, IP, waktu. |

Peran: **pemilik organisasi** (penagihan, hapus organisasi), **admin** (anggota, API key, semua pekerjaan), **anggota** (pekerjaan sendiri dan yang dibagikan), dan **penagihan** (opsional, hanya faktur). Semua izin diperiksa di server, termasuk unduhan berkas privat lewat endpoint yang memeriksa pemilik/tim sebelum mengalirkan berkas.

## Pengalaman developer

1. `bench get-app turbojet` + `bench turbojet init` — membuat site induk dan satu site contoh, menanyakan nama produk, bahasa, model bisnis, dan paket, lalu mengisi data contoh dan simulator pembayaran. Target: dari repo kosong ke alur CSV berjalan **di bawah 15 menit**.
2. `bench turbojet new-feature reports_sales` — generator minimal yang **ikut rilis awal**: halaman portal, handler/endpoint API, entri hak paket, pengaitan kuota, operasi Python di `engine/ops/` + golden test pytest + skrip bench, dan uji akses. Generator yang lebih lengkap (UI builder, banyak template) masuk R2.
3. `bench turbojet port reports_sales` — pembungkus alur rust-anything untuk operasi itu: `profile` → `bridge` → `record --from-tests` → tulis `port.rs` → `build`/`diff`/`fuzz`/`bench` → `shadow` → `gate` → `enable`. Untuk satu operasi yang lambat cukup `rust-anything go -- python bench/bench_reports_sales.py`. Agen coding (Claude Code) dapat menulis `port.rs` lewat MCP rust-anything; developer menyetujui setiap unit.
4. `bench turbojet doctor` — memeriksa versi engine dan wheel Rust di setiap host worker (memanggil `rust-anything doctor` di mesin pengembang), rekaman basi (`rust-anything map`), koneksi Redis, scheduler, rahasia site, konfigurasi penyedia pembayaran, dan umur backup.
5. `bench turbojet trace <request_id>` — menampilkan seluruh jejak satu permintaan sampai ke pembayaran, kuota, percobaan worker (termasuk jalur python/rust), dan berkas hasil. Tampilan yang sama tersedia di Desk.
6. Aktifkan penyedia pembayaran nyata lewat konfigurasi, uji di sandbox penyedia, lalu deploy web, worker, dan scheduler sesuai panduan (Docker Compose berbasis `frappe_docker` + wheel Rust hasil `rust-anything package` di image worker). CI menjalankan `rust-anything gate` dan `map` untuk setiap crate yang di-enable; rilis ditolak bila ada yang gagal atau basi.

## Contoh bawaan — impor CSV menjadi laporan

Pengguna masuk ke portal, mengunggah CSV (unggahan bertahap/resumable untuk berkas besar), lalu memilih kolom pengelompokan dan kolom angka dari **pratinjau 20 baris pertama** yang dihasilkan engine dalam mode cepat. Frappe memeriksa izin dan ukuran berkas, lalu membuat pekerjaan dan mereservasi satu kuota dalam satu transaksi.

Setelah transaksi tersimpan, worker menjalankan Rust untuk membaca data secara bertahap, menghitung jumlah baris dan total per kelompok, serta mencatat nomor baris dan alasan untuk nilai yang tidak valid. Portal menampilkan progres (baris terproses, estimasi waktu). Pengguna dapat menutup browser, menerima email saat selesai, dan kembali ke halaman riwayat. Hasil tersedia sebagai CSV dan XLSX, beserta `errors.csv`.

Jika pemrosesan berhenti sementara, percobaan berikutnya memakai ID pekerjaan dan reservasi yang sama. Jika gagal permanen, reservasi dilepas satu kali. Baris valid tetap diproses dan jumlah baris yang dikecualikan ditampilkan bersama hasil. Opsi "tolak seluruh berkas bila ada baris rusak > X%" tersedia per pekerjaan.

## Keamanan

- Berkas unggahan: validasi ukuran, tipe, dan encoding sebelum job dibuat; disimpan privat; nama berkas tidak pernah dipakai sebagai path.
- Rahasia (kunci penyedia pembayaran, rahasia site, API key) hanya di `site_config.json`/secret manager, tidak di DocType yang bisa diekspor, tidak di log.
- Webhook masuk: verifikasi tanda tangan, cek timestamp, tolak replay; endpoint terpisah dari sesi pengguna.
- Batas laju login, pendaftaran, dan API; CAPTCHA pihak ketiga opsional pada pendaftaran.
- Isolasi tenant diuji otomatis: setiap rilis menjalankan uji lintas-site untuk API, unduhan, dan realtime.
- Engine berjalan dalam sandbox tanpa jaringan (lihat bagian Rust).

## Observabilitas

- Log terstruktur JSON dengan `request_id`, `site`, `job`, `attempt`, dan kode kesalahan — tanpa isi CSV dan tanpa kredensial.
- Metrik (endpoint Prometheus di induk): umur job tertua per site, panjang antrean per queue, tingkat retry, durasi engine p50/p95, memori puncak, transaksi pembayaran belum cocok, umur backup per site, site yang tertinggal versi.
- Dasbor Desk di induk untuk admin non-teknis: pelanggan aktif, MRR, pembayaran gagal, pekerjaan gagal 24 jam terakhir.
- Alarm: antrean macet > 10 menit, rekonsiliasi menemukan selisih, backup site > 26 jam, migrasi gagal.

## Ketahanan saat dipakai banyak pelanggan

| Kejadian | Perilaku yang dirancang |
| --- | --- |
| Tombol ditekan dua kali / koneksi putus setelah permintaan diterima | Kunci idempotensi `(user, operation, client_key)` + hash input. Input sama → pekerjaan yang sudah ada; input beda → `IDEMPOTENCY_CONFLICT`. Reservasi + pembuatan job dalam satu transaksi dengan baris saldo terkunci. |
| Antrean berhenti setelah pekerjaan tersimpan | Job tetap `queued`; penyapu tiap menit menjadwalkan ulang; worker mengambil lease secara atomik. |
| Worker lama hidup kembali setelah pekerjaan diambil alih | Fencing token `attempt`: penerbitan hasil, commit kuota, dan status `done` hanya diterima dari attempt terbaru dalam satu transaksi. Direktori percobaan lama dibersihkan penyapu. |
| Notifikasi pembayaran terlambat, hilang, ganda, atau tidak berurutan | Payment Event unik per penyedia; mesin status hanya maju; rekonsiliasi bertanya ke penyedia; `entitlement.sync` berversi sehingga tenant mengabaikan versi lama. Refund mengikuti transisi tersendiri. |
| Site induk mati | Tenant tetap jalan dengan hak terakhir; webhook ditolak sementara sehingga penyedia mengirim ulang; rekonsiliasi menutup sisa saat induk pulih. |
| Satu organisasi mengirim banyak impor besar | Batas pekerjaan aktif per site + slot cadangan global; engine streaming; batas ukuran, kolom, grup, waktu, dan memori dari hak paket. Batas terlampaui → pesan jelas dan reservasi dilepas satu kali. |
| Versi engine di host worker berbeda | Job mencatat `contract_version` dan versi crate; worker menolak engine yang tidak kompatibel dan `doctor` melaporkannya sebelum rilis. Host tanpa wheel Rust tetap benar karena berjalan di Python rujukan. |
| Port Rust salah di produksi | Mode `shadow` menangkap selisih sebelum `new`. Setelah `new`, `RUST_ANYTHING_UNIT_<UNIT>=original` mengembalikan operasi ke Python tanpa deploy; kasus penyebab ditambahkan ke rekaman (`record --inputs`) sebelum Rust dinyalakan lagi. |
| Admin perlu menjelaskan tagihan atau kegagalan | `trace <request_id>` di CLI dan Desk; log audit; metrik dan alarm di atas. |

## Cakupan rilis

**R1 — alur pertama lengkap**
- `turbojet_control` + `turbojet`, provisioning site (dengan pool site siap pakai), subdomain wildcard.
- Pendaftaran, undangan, peran, katalog paket, hak, buku kuota, idempotensi.
- Simulator pembayaran + satu penyedia nyata, rekonsiliasi, faktur PDF, dunning dasar.
- Engine: runner + kontrak berkas + sandbox; operasi `group_sum` dan pratinjau di Python rujukan dengan golden test; `group_sum` diport ke Rust lewat rust-anything sampai `gate` lulus, `bench` lebih cepat, dan `shadow` bersih di staging, lalu di-enable.
- Impor CSV dengan progres realtime, riwayat, unduhan CSV/XLSX, email selesai.
- API publik + API key, log audit, bahasa id/en.
- CLI `init`, `new-feature` (minimal), `port`, `doctor`, `trace`; panduan setup, deploy, backup, dan pemulihan.

**R2** — webhook keluar, impersonasi, feature flag, kredit prabayar dan metered, penyedia pembayaran kedua, ekspor/penghapusan data, generator fitur lengkap, operasi tambahan (join, pivot, dedup, validasi skema) — masing-masing Python dulu, Rust menyusul lewat siklus yang sama.

**R3** — domain kustom, SSO, multi-region/beberapa bench dikelola dari satu induk, engine sebagai layanan terpisah bila hasil ukur menuntut.

## Kriteria penerimaan

| Skenario | Hasil yang harus dapat diperiksa |
| --- | --- |
| Instalasi baru | Developer mengikuti panduan pada mesin kosong, menjalankan `init`, mendaftar organisasi baru, mengunggah CSV, dan mengunduh hasil dalam ≤ 15 menit. |
| Provisioning | Pendaftaran dari pool siap pakai selesai ≤ 10 detik; kegagalan di tengah dapat diulang dan tidak pernah menghasilkan site setengah jadi yang dapat diakses. |
| Isolasi pelanggan | Pengguna/API key site A tidak bisa membaca data, berkas privat, atau event realtime site B. Di dalam satu site, unduhan mematuhi izin pemilik dan tim. |
| Permintaan bersamaan | Sisa kuota satu, 50 permintaan bersamaan → tepat satu reservasi berhasil, sisanya `QuotaExceeded`. |
| Idempotensi | Permintaan diulang dengan kunci dan input sama → satu job; input berbeda → `IDEMPOTENCY_CONFLICT`. |
| Pembayaran berulang | Menutup browser tidak menghalangi aktivasi. Notifikasi yang sama dikirim 5 kali dan notifikasi lama dikirim setelah lunas → hak aktif tepat satu kali. |
| Pembayaran tanpa notifikasi | Rekonsiliasi mengaktifkan paket dalam satu siklus. |
| Pemulihan pekerjaan | Worker dibunuh di tengah proses dan setelah hasil ditulis tetapi sebelum `done` → satu laporan akhir dan paling banyak satu pemakaian kuota. |
| Ketepatan hasil Rust | Data contoh dengan baris valid, kosong, angka rusak, format desimal Indonesia, dan BOM → total per grup dan nomor baris bermasalah cocok byte-per-byte dengan rujukan. `rust-anything diff` N/N, `fuzz` tanpa selisih baru, `gate` lulus, `known-diffs.jsonl` kosong atau setiap barisnya disetujui. |
| Saklar Rust/Python | Job yang sama dijalankan dengan `RUST_ANYTHING_UNIT_OPS=original` dan dengan Rust → checksum `output` dan `errors.csv` sama; `trace` menunjukkan jalur yang dipakai. |
| API | Membuat job dan mengunduh hasil lewat API key memakai kuota dan izin yang sama dengan portal; key dicabut langsung ditolak. |
| Pemakaian ulang | Developer menambahkan laporan kedua dengan `new-feature` (berjalan di Python) lalu `port` ke Rust, tanpa mengubah kode akun, pembayaran, antrean, atau riwayat. |

## Uji sebelum dipakai di produksi

Angka beban berikut adalah **target awal yang diusulkan**. Catat versi Frappe, versi app, versi engine, CPU, RAM, jumlah slot worker, ukuran berkas, dan jumlah grup agar hasil bisa diulang.

| Uji | Bukti yang harus dihasilkan |
| --- | --- |
| Kecepatan engine | CSV 1 juta baris, 20 kolom, 10.000 grup diproses ≤ 10 detik dengan memori puncak ≤ 256 MB pada 2 vCPU di jalur Rust. Lampirkan `rust-anything report` (speedup terhadap Python rujukan, biaya bridge termasuk). Operasi yang `bench`-nya tidak lebih cepat tetap di Python. |
| Shadow di staging | Minimal 1 minggu atau 1.000 job nyata dengan `RUST_ANYTHING_MODE=shadow`: metrik `engine_shadow_mismatch` = 0 sebelum beralih ke `new`. |
| Beban campuran | Dua slot worker; site A mengirim 10 impor @100.000 baris dengan batas 1 pekerjaan aktif; site B mengirim impor kecil saat A masih antre. B harus mulai sebelum antrean A habis. Catat waktu tunggu, durasi, memori puncak, dan p95 respons portal. Cocokkan semua hasil dengan rujukan. |
| Banyak tenant | 200 site aktif pada satu bench uji: migrasi bergelombang selesai, penyapu dan scheduler tidak menumpuk, p95 portal tetap di bawah target. |
| Gangguan pada batas transaksi | Putuskan antrean setelah reservasi; hentikan worker setelah hasil ditulis sebelum `done`. Setelah pulih: tepat satu hasil final dan satu debit. |
| Pembayaran tanpa notifikasi | Penyedia menyatakan lunas, portal masih menunggu; jalankan rekonsiliasi lalu kirim ulang notifikasi lama dan lunas. Paket aktif tepat sekali; saldo cocok dengan penyedia. |
| Induk mati | Matikan site induk 30 menit saat ada pembayaran masuk. Tenant tetap melayani; setelah induk pulih semua pembayaran terekonsiliasi. |
| Pemulihan satu pelanggan | Pulihkan database, berkas privat, dan konfigurasi site dari backup ke lingkungan terisolasi dengan email dan transaksi keluar dinonaktifkan. Verifikasi login, izin unduh, saldo kuota, dan checksum laporan. Catat RTO dan RPO. |
| Pembaruan versi template | Instal versi baru pada salinan site berisi langganan aktif dan pekerjaan tertunda; migrasi; lanjutkan pekerjaan dengan engine kompatibel; verifikasi akses, saldo, dan hasil sebelum gelombang berikutnya. |

Pemilik produk menilai kesiapan rilis dari laporan pengujian ini. Sasaran waktu respons, kapasitas per worker, RTO, dan RPO ditetapkan setelah ada hasil ukur pada lingkungan yang mewakili deployment sebenarnya.

## Keputusan terbuka

1. Penyedia pembayaran nyata pertama: Midtrans atau Xendit.
2. Domain produk dan penyedia TLS wildcard.
3. Penyimpanan berkas: disk lokal bench atau S3-compatible sejak R1.
4. Batas default paket gratis dan Pro (baris per impor, impor per bulan, pekerjaan aktif).
5. Lisensi template (komersial tertutup atau sumber terbuka dengan lisensi tertentu).
6. Ukuran potongan (chunk) yang diberikan runner ke operasi, ditentukan dari hasil `profile` pertama.
7. Platform wheel Rust yang wajib (Linux x86_64 saja, atau juga arm64) untuk `rust-anything package`.

## Referensi

- [Frappe Framework](https://docs.frappe.io/framework/user/en/introduction)
- [Frappe Sites](https://docs.frappe.io/framework/user/en/basics/sites)
- [Background Jobs](https://docs.frappe.io/framework/user/en/api/background_jobs)
- [frappe_docker](https://github.com/frappe/frappe_docker)
- [rust-anything](https://crates.io/crates/rust-anything) — v3.3.0 terpasang lokal; alur per unit: analyze → bridge → record → port → build → diff → shadow → gate
- [Referensi produk TurboJet HilmiRF](https://www.hilmirf.com/en/products/turbojet-boilerplate)
