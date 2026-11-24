#!/usr/bin/env bash
# Pelari mandiri di Orange Pi: menjalankan Claude Code headless berulang sampai PROGRES.md berstatus SELESAI.
# Tidak butuh laptop maupun browser. Dijalankan oleh layanan systemd user `pidpos-agen` (lihat tools/pidpos-agen.service).
#   systemctl --user start pidpos-agen     # mulai
#   systemctl --user stop pidpos-agen      # hentikan (atau: touch .agen/STOP)
#   tail -f ~/work/proyek/pid_pos_tj/.agen/agen.log
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
mkdir -p .agen
LOG=.agen/agen.log
MAX_PUTARAN="${MAX_PUTARAN:-300}"
PROMPT='Kamu bekerja mandiri di Orange Pi tanpa user. Baca TUGAS_PID_POS_LENGKAP.md lalu PROGRES.md di folder ini dan lanjutkan pekerjaan dari langkah berikut yang tercatat. Ikuti semua aturan brief (branch pid-pos-lengkap, commit+push berkala, perbarui PROGRES.md, jangan sentuh 65/66/SAP, jangan cetak rahasia). Jangan bertanya ke user; catat pertanyaan di PROGRES.md dan lanjut. Bila semua kriteria selesai terpenuhi, tulis LAPORAN_AKHIR.md, set "STATUS: SELESAI" di PROGRES.md, commit dan push.'

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

for ((i = 1; i <= MAX_PUTARAN; i++)); do
  if [ -f .agen/STOP ]; then log "berhenti: .agen/STOP ada"; exit 0; fi
  if grep -q "^STATUS: SELESAI" PROGRES.md 2>/dev/null; then log "selesai: PROGRES.md SELESAI"; exit 0; fi
  OUT=".agen/putaran-$(date +%Y%m%d-%H%M%S).log"
  log "putaran $i mulai -> $OUT"
  claude -p "$PROMPT" --permission-mode bypassPermissions --output-format text > "$OUT" 2>&1 < /dev/null
  rc=$?
  log "putaran $i selesai rc=$rc"
  if grep -qiE "429|rate.?limit|credits|usage limit|quota|overloaded" "$OUT"; then
    log "batas kuota/limit -> jeda 30 menit"; sleep 1800
  elif [ $rc -ne 0 ]; then
    log "gagal -> jeda 5 menit"; sleep 300
  else
    sleep 60
  fi
done
log "batas $MAX_PUTARAN putaran tercapai"
