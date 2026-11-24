#!/usr/bin/env bash
# Pelari agen mandiri: menjalankan Claude Code headless berulang sampai berkas progres berstatus SELESAI.
# Tidak butuh laptop maupun browser. Dijalankan oleh layanan systemd user `agen@<nama>` (lihat agen@.service);
# semua setelan dibaca dari ~/.config/agen/<nama>.env (lihat contoh.env).
#   systemctl --user enable --now agen@<nama>   # mulai (dan ikut menyala saat mesin reboot)
#   systemctl --user stop agen@<nama>           # hentikan; atau `touch <AGEN_DIR>/.agen/STOP` (berhenti setelah putaran)
set -uo pipefail
: "${AGEN_DIR:?AGEN_DIR belum diisi (folder repo app)}"
AGEN_BRIEF="${AGEN_BRIEF:-TUGAS.md}"
AGEN_PROGRES="${AGEN_PROGRES:-PROGRES.md}"
AGEN_BRANCH="${AGEN_BRANCH:-agen}"
AGEN_MAKS_PUTARAN="${AGEN_MAKS_PUTARAN:-300}"
AGEN_JEDA_LIMIT="${AGEN_JEDA_LIMIT:-1800}"
AGEN_IZIN="${AGEN_IZIN:-bypassPermissions}"   # mode izin Claude Code; bypassPermissions = tanpa tanya (wajib untuk jalan sendiri)
export PATH="$HOME/.local/bin:$PATH"
cd "$AGEN_DIR" || exit 1
mkdir -p .agen
LOG=.agen/agen.log
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

PROMPT="${AGEN_PROMPT:-Kamu bekerja mandiri tanpa user. Baca $AGEN_BRIEF lalu $AGEN_PROGRES di folder ini dan lanjutkan pekerjaan dari langkah berikut yang tercatat. Ikuti semua aturan brief. Kerja di branch $AGEN_BRANCH, commit + push berkala, perbarui $AGEN_PROGRES setiap commit. Jangan bertanya ke user; catat pertanyaan di $AGEN_PROGRES dan lanjut. Jangan cetak rahasia. Bila semua kriteria selesai terpenuhi, tulis laporan akhir, set \"STATUS: SELESAI\" di $AGEN_PROGRES, commit dan push.}"
MODEL_ARGS=()
[ -n "${AGEN_MODEL:-}" ] && MODEL_ARGS=(--model "$AGEN_MODEL")

for ((i = 1; i <= AGEN_MAKS_PUTARAN; i++)); do
  if [ -f .agen/STOP ]; then log "berhenti: .agen/STOP ada"; exit 0; fi
  if grep -q "^STATUS: SELESAI" "$AGEN_PROGRES" 2>/dev/null; then log "selesai: $AGEN_PROGRES SELESAI"; exit 0; fi
  OUT=".agen/putaran-$(date +%Y%m%d-%H%M%S).log"
  log "putaran $i mulai -> $OUT"
  claude -p "$PROMPT" --permission-mode "$AGEN_IZIN" "${MODEL_ARGS[@]}" --output-format text > "$OUT" 2>&1 < /dev/null
  rc=$?
  log "putaran $i selesai rc=$rc"
  if grep -qiE "429|rate.?limit|credits|usage limit|quota|overloaded" "$OUT"; then
    log "batas kuota/limit -> jeda $AGEN_JEDA_LIMIT dtk"; sleep "$AGEN_JEDA_LIMIT"
  elif [ $rc -ne 0 ]; then
    log "gagal -> jeda 5 menit"; sleep 300
  else
    sleep 60
  fi
done
log "batas $AGEN_MAKS_PUTARAN putaran tercapai"
