# TurboJet (monorepo)

Template resmi pembuatan aplikasi kita: **Frappe v16 + engine Python/Rust (rust-anything)**.

| Folder | Isi |
|---|---|
| `template/` | app template `turbojet`: paket Frappe `turbojet/`, crate Rust `rust/`, `bench/`, bench Docker `dev/`, tes engine (59) |
| `skill/` | skill Claude `/turbojet` (`SKILL.md`, `scripts/buat_app.py`); `~/.claude/skills/turbojet` = junction ke sini |
| `apps/` | app turunan yang dibuat di dalam monorepo |
| `tools/pi/` | agen Claude Code mandiri generik untuk mesin Linux selalu-menyala (pelari, layanan systemd `agen@<nama>`, pemeriksa `/cek-agen`) |
| `KONSEP_TURBOJET_FRAPPE_RUST.md` | konsep v2.1 |

```bash
# app baru di monorepo (apps/<nama>) atau di folder lain (--tujuan)
python -I -X utf8 skill/scripts/buat_app.py --judul "Kasir Kapal"
python -I -X utf8 skill/scripts/buat_app.py --judul "Kasir Kapal" --tujuan D:/kasir_kapal          # repo sendiri = monorepo (apps/kasir_kapal, docs/, tools/)
python -I -X utf8 skill/scripts/buat_app.py --judul "Kasir Kapal" --tujuan D:/kasir_kapal --datar  # tanpa monorepo

# uji template
cd template && python -m venv .venv && .venv/Scripts/python -m pip install pytest && .venv/Scripts/python -m pytest -q
```

Detail template: `template/README.md`, `template/rust/README.md`, `template/dev/README.md`.
