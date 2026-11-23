# Bench Frappe lokal (uji, bukan produksi)

Docker: `frappe/erpnext:v16.60.0` (Frappe v16, Python 3.14; versi sama dengan server 65), MariaDB 11.8,
Redis 7. Source app di-mount langsung (tanpa pip, lewat `.pth`), jadi perubahan Python cukup
`docker compose -f dev/docker-compose.yml restart backend worker`; DocType berubah → `bash dev/bench.sh migrate`.

```bash
bash dev/bench.sh up       # pertama kali: site turbojet.localhost + install-app + RUST_ANYTHING_MODE=new
bash dev/bench.sh smoke    # uji asap API end-to-end
bash dev/bench.sh bench --site turbojet.localhost console
bash dev/bench.sh logs worker
bash dev/bench.sh down     # data tetap; `down -v` hapus total
```

Buka di browser: http://turbojet.localhost:8090 (Administrator / admin). Frappe memilih site dari
nama host, jadi `http://localhost:8090` memberi 404; klien API kirim header `X-Frappe-Site-Name`.
Variabel: `TURBOJET_PORT` (8090), `TURBOJET_SITE`, `ADMIN_PASSWORD`, `DB_ROOT_PASSWORD`, `FRAPPE_IMAGE`.

## Hasil 23-11-2026

`smoke` 8/8 lulus: preview_csv, idempotensi (client_key sama → job sama), job `done` lewat jalur
**rust**, 4/3/1 baris, output.csv benar, CSV salah → `failed INVALID_OPTIONS` dengan kuota dilepas,
list_jobs. Job yang gagal sebelum perbaikan dipungut ulang oleh penyapu (attempt 2 → done).
Buku kuota: 3 reserve = 2 commit + 1 release, saldo reserved 0. Error Log kosong.

Bug yang ditemukan dan diperbaiki: `jobs._execute` memakai path relatif site sedangkan engine
berjalan dengan `cwd=attempt_dir` (engine keluar kode 4, FileNotFoundError) → path dibuat absolut.

Belum diuji: user non-admin (peran TurboJet Member, izin `if_owner`), kuota habis, pembatalan saat
berjalan, lease kedaluwarsa saat worker mati, berkas besar.
