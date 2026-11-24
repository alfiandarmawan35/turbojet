# tools/pi — agen Claude Code mandiri

Menjalankan Claude Code tanpa pengawasan di mesin Linux yang selalu menyala (mis. Orange Pi / Raspberry Pi / VPS)
sampai sebuah brief tugas tuntas — tanpa laptop, tanpa browser. Satu layanan systemd per app.

| Berkas | Fungsi |
|---|---|
| `agen.sh` | pelari: `claude -p … --permission-mode bypassPermissions` berulang sampai berkas progres berisi `STATUS: SELESAI` atau ada `.agen/STOP`; jeda bila kena limit/kuota |
| `agen@.service` | layanan template systemd user; `agen@<nama>` membaca `~/.config/agen/<nama>.env` |
| `contoh.env` | semua setelan (folder repo, brief, progres, branch, daftar centang, model, jeda, prompt) |
| `cek-agen` | pemeriksa HANYA MEMBACA: layanan, putaran, git/push, daftar centang, progres, 10 aksi terakhir Claude |
| `cek-agen.md` | perintah Claude Code `/cek-agen [nama]` (merangkum keluaran pemeriksa) |
| `pasang.sh` | memasang semuanya + `pasang.sh buat <nama> <folder>` untuk membuat setelan agen |

## Pakai

```bash
bash tools/pi/pasang.sh
bash tools/pi/pasang.sh buat kasir_kapal ~/work/kasir_kapal TUGAS.md PROGRES.md agen
systemctl --user enable --now agen@kasir_kapal
cek-agen kasir_kapal            # atau /cek-agen kasir_kapal di Claude Code
systemctl --user stop agen@kasir_kapal
```

## Pola kerja
- Repo app berisi brief `TUGAS.md` (tujuan, definisi selesai, aturan) dan `PROGRES.md` (ingatan antar-sesi:
  langkah berikut yang persis, masalah, pertanyaan untuk user). Agen membaca keduanya di tiap putaran.
- Agen bekerja di branch sendiri, commit + push berkala, tidak pernah push ke `main`/`master`.
- **Peringatan**: `bypassPermissions` = Claude menjalankan perintah apa pun tanpa bertanya. Pakai hanya di mesin
  khusus, tulis batasan jelas di brief (apa yang tidak boleh disentuh), dan jangan taruh rahasia di repo.
- Butuh Claude Code terpasang dan sudah login di mesin itu, serta linger (`sudo loginctl enable-linger $USER`).
