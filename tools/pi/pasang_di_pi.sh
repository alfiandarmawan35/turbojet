#!/usr/bin/env bash
# Pasang perangkat agen mandiri di Orange Pi (jalankan di Pi dari folder ini):
#   bash pasang_di_pi.sh                       # pasang/perbarui layanan + pemeriksa + perintah Claude/Orca /cek-pidpos
#   systemctl --user enable --now pidpos-agen  # mulai agen (skrip ini tidak menyalakannya)
# Saat ini disetel untuk PID POS: folder kerja ~/work/proyek/pid_pos_tj (agen_pi.sh disalin ke tools/ app itu).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ~/.local/bin ~/.claude/commands ~/.config/systemd/user
install -m 755 cek-pidpos ~/.local/bin/cek-pidpos
install -m 644 cek-pidpos.md ~/.claude/commands/cek-pidpos.md
install -m 644 pidpos-agen.service ~/.config/systemd/user/pidpos-agen.service
systemctl --user daemon-reload
echo "terpasang: ~/.local/bin/cek-pidpos, /cek-pidpos, layanan pidpos-agen ($(systemctl --user is-enabled pidpos-agen 2>/dev/null || echo belum-enable))"
