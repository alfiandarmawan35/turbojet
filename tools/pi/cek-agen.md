---
description: Periksa kemajuan agen Claude Code mandiri (layanan agen@<nama>) — hanya membaca
argument-hint: "[nama agen]"
allowed-tools: Bash(cek-agen:*), Bash(~/.local/bin/cek-agen:*), Read
---

Jalankan `~/.local/bin/cek-agen $ARGUMENTS` (tanpa argumen = daftar agen; bila hanya ada satu agen, periksa agen itu)
lalu laporkan singkat dalam bahasa user:

1. Status agen: bekerja, jeda (limit/kuota), berhenti, atau SELESAI.
2. Kemajuan: isi daftar centang (bila ada), modul yang sudah/sedang dikerjakan, commit terakhir & sudah di-push atau belum.
3. Yang sedang dikerjakan sekarang (aktivitas terakhir) dan langkah berikut di berkas progres.
4. Masalah terbuka & pertanyaan untuk user di berkas progres (kutip apa adanya).
5. Tanda bahaya: putaran gagal berulang, macet lama di satu langkah, berkas belum di-commit menumpuk.

Aturan: HANYA MEMBACA. Jangan mengubah berkas, commit, menjalankan/menghentikan layanan, atau melanjutkan pekerjaan
agen (agen bekerja di folder yang sama). Jangan menampilkan rahasia. Menghentikan agen
(`systemctl --user stop agen@<nama>` atau `touch <folder>/.agen/STOP`) hanya bila user memintanya.
