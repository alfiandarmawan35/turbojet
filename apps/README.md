# apps/

App turunan TurboJet yang tinggal di monorepo ini. Buat dengan:

```bash
python -I -X utf8 skill/scripts/buat_app.py --judul "Kasir Kapal"     # -> apps/kasir_kapal
```

Tiap app berdiri sendiri (`pyproject.toml`, `dev/` bench Docker, `rust/`, tes). Perbaikan yang berlaku umum
dikerjakan di `template/` dulu lalu dibawa ke app. App yang butuh repo sendiri dibuat dengan
`--tujuan <folder di luar repo>` (hasilnya monorepo sendiri).
