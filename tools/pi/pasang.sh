#!/usr/bin/env bash
# Pasang perangkat agen mandiri (jalankan di mesin agen, mis. Orange Pi, dari folder ini).
#   bash pasang.sh                                  # pasang/perbarui agen.sh, cek-agen, agen@.service, perintah /cek-agen
#   bash pasang.sh buat <nama> <folder-repo> [brief] [progres] [branch]   # buat ~/.config/agen/<nama>.env
#   systemctl --user enable --now agen@<nama>       # mulai agen (skrip ini tidak menyalakannya)
set -euo pipefail
cd "$(dirname "$0")"
if [ "${1:-}" = "buat" ]; then
  N="${2:?nama agen}"; D="$(cd "${3:?folder repo}" && pwd)"
  [[ "$N" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "nama hanya huruf/angka/_.-"; exit 1; }
  mkdir -p ~/.config/agen; F=~/.config/agen/"$N".env
  [ -e "$F" ] && { echo "sudah ada: $F"; exit 1; }
  printf 'AGEN_DIR=%s\nAGEN_BRIEF=%s\nAGEN_PROGRES=%s\nAGEN_BRANCH=%s\n' "$D" "${4:-TUGAS.md}" "${5:-PROGRES.md}" "${6:-agen}" > "$F"
  echo "dibuat: $F  (lihat contoh.env untuk opsi lain)"; exit 0
fi
mkdir -p ~/.local/bin ~/.claude/commands ~/.config/systemd/user ~/.config/agen
install -m 755 agen.sh ~/.local/bin/agen.sh
install -m 755 cek-agen ~/.local/bin/cek-agen
install -m 644 cek-agen.md ~/.claude/commands/cek-agen.md
install -m 644 agen@.service ~/.config/systemd/user/agen@.service
systemctl --user daemon-reload
[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" = yes ] || echo "!! linger belum aktif: sudo loginctl enable-linger $USER"
echo "terpasang: ~/.local/bin/agen.sh, ~/.local/bin/cek-agen, agen@.service, perintah /cek-agen"
