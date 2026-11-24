# Perangkat Orange Pi (agen mandiri)

Agar Claude Code di Orange Pi bisa menyelesaikan pekerjaan panjang tanpa laptop dan tanpa browser.

| Berkas | Fungsi |
|---|---|
| `agen_pi.sh` | pelari: `claude -p … --permission-mode bypassPermissions` berulang sampai `PROGRES.md` berisi `STATUS: SELESAI` atau ada `.agen/STOP`; jeda 30 menit bila kena limit. Ditaruh di `tools/` folder app. |
| `pidpos-agen.service` | layanan systemd user (linger aktif → jalan tanpa login, ikut menyala saat reboot bila di-enable) |
| `cek-pidpos` | pemeriksa HANYA MEMBACA: layanan, putaran, git/push, endpoint x/369, PROGRES, kontainer, 10 aksi terakhir Claude (jam WIB) |
| `cek-pidpos.md` | perintah Claude/Orca `/cek-pidpos` (merangkum keluaran pemeriksa) |
| `pasang_di_pi.sh` | memasang tiga berkas terakhir ke `~/.local/bin`, `~/.claude/commands`, `~/.config/systemd/user` |

Pola kerja: brief `TUGAS_*.md` + `PROGRES.md` (ingatan antar-sesi) di repo app, branch kerja sendiri, commit + push
berkala, jangan push ke `master`/`main`. Model = bawaan Claude Code di Pi (lewat 9Router).
Saat ini disetel untuk PID POS (`~/work/proyek/pid_pos_tj`); untuk app lain ganti nama layanan, folder, dan prompt.
