---
description: Periksa kemajuan agen PID POS (layanan pidpos-agen) di Pi — hanya membaca
allowed-tools: Bash(cek-pidpos), Bash(~/.local/bin/cek-pidpos), Read
---

Jalankan `~/.local/bin/cek-pidpos` lalu laporkan dalam Bahasa Indonesia, singkat:

1. Apakah agen sedang bekerja, jeda (limit/kuota), berhenti, atau sudah SELESAI.
2. Kemajuan: endpoint selesai dari 369, modul yang sudah/sedang dikerjakan, commit terakhir & sudah di-push atau belum.
3. Apa yang sedang dikerjakan sekarang (dari aktivitas terakhir) dan langkah berikut di PROGRES.md.
4. Masalah terbuka & pertanyaan untuk user di PROGRES.md (kutip apa adanya).
5. Tanda bahaya bila ada: putaran gagal berulang, agen macet lama di satu langkah, kontainer bench mati, berkas belum di-commit menumpuk.

Aturan: HANYA MEMBACA. Jangan mengubah berkas, jangan commit, jangan menjalankan/menghentikan layanan atau bench,
dan jangan melanjutkan pekerjaan agen (agen sedang bekerja di folder yang sama). Jangan menampilkan rahasia.
Bila user minta menghentikan agen: `systemctl --user stop pidpos-agen` (atau `touch ~/work/proyek/pid_pos_tj/.agen/STOP`
untuk berhenti setelah putaran berjalan selesai) — lakukan hanya bila user memintanya.
