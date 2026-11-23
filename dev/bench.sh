#!/usr/bin/env bash
# Bench Frappe lokal untuk app ini. Butuh Docker. Jalankan dari folder app (yang berisi dev/).
#   bash dev/bench.sh up       nyalakan; pertama kali juga buat site + install-app
#   bash dev/bench.sh smoke    unggah CSV lewat API, buat job, tunggu selesai, cek hasil/kuota/idempotensi
#   bash dev/bench.sh migrate  setelah DocType berubah
#   bash dev/bench.sh bench …  jalankan perintah bench apa saja, mis. `bash dev/bench.sh bench --site all list-apps`
#   bash dev/bench.sh down     matikan (data tetap); `down -v` hapus total
set -euo pipefail
cd "$(dirname "$0")"
APP="${TURBOJET_APP:-turbojet}"
SITE="${TURBOJET_SITE:-$APP.localhost}"
PORT="${TURBOJET_PORT:-8090}"
ADMIN_PW="${ADMIN_PASSWORD:-admin}"
DB_PW="${DB_ROOT_PASSWORD:-admin}"
DC=(docker compose -f docker-compose.yml)
export MSYS_NO_PATHCONV=1

run() { "${DC[@]}" run --rm --no-deps -T backend "$@"; }

case "${1:-up}" in
  up)
    "${DC[@]}" up -d db redis-cache redis-queue
    until "${DC[@]}" exec -T db healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; do sleep 2; done
    if ! run test -d "sites/$SITE"; then
      echo "== site baru $SITE"
      run bash -c "
        set -e
        bench set-config -g db_host db
        bench set-config -gp db_port 3306
        bench set-config -g redis_cache redis://redis-cache:6379
        bench set-config -g redis_queue redis://redis-queue:6379
        bench set-config -g redis_socketio redis://redis-queue:6379
        sed -i -e '\$a\\' sites/apps.txt   # apps.txt image tak berakhir newline
        grep -qx $APP sites/apps.txt || echo $APP >> sites/apps.txt
        bench new-site $SITE --db-root-password '$DB_PW' --admin-password '$ADMIN_PW' --mariadb-user-host-login-scope=%
        bench --site $SITE install-app $APP
        bench --site $SITE set-config ${APP}_engine_env '{\"RUST_ANYTHING_MODE\": \"new\"}' --parse
        bench --site $SITE enable-scheduler
        bench use $SITE
      "
    fi
    "${DC[@]}" up -d
    echo "== siap: http://$SITE:$PORT (Administrator / $ADMIN_PW)"
    ;;
  migrate) run bench --site "$SITE" migrate ;;
  bench) shift; run bench "$@" ;;
  smoke) shift; python -I -X utf8 smoke.py --url "http://localhost:$PORT" --app "$APP" --site "$SITE" --password "$ADMIN_PW" "$@" ;;
  down) shift; "${DC[@]}" down "$@" ;;
  logs) shift; "${DC[@]}" logs --tail=80 "$@" ;;
  *) echo "perintah: up | smoke | migrate | bench … | logs [svc] | down [-v]"; exit 2 ;;
esac
