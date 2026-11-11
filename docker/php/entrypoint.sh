#!/usr/bin/env bash
# Waits for PostgreSQL, applies migrations and seeds, then starts the given command.
set -euo pipefail
cd /var/www/backend

# Keys that are not given are generated once and kept in the `secrets` volume (never in the repository, never in the
# image): a redeploy then comes back with the same Reverb key, so the games that are open reconnect to their rooms
# instead of being refused until the page is reloaded. Without the volume they are generated per container.
KEYS="${SECRETS_DIR:-/var/lib/touge}/keys.env"
if [ -d "$(dirname "$KEYS")" ]; then
  if [ ! -s "$KEYS" ]; then
    # (readable by root only)
    (
      umask 077
      {
        echo "GEN_APP_KEY=base64:$(head -c 32 /dev/urandom | base64)"
        echo "GEN_REVERB_APP_KEY=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
        echo "GEN_REVERB_APP_SECRET=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
      } > "$KEYS"
    )
    echo "[entrypoint] generated keys in $(dirname "$KEYS")"
  fi
  # shellcheck disable=SC1090
  . "$KEYS"
fi

if [ -z "${APP_KEY:-}" ]; then
  # The API is stateless, but Laravel wants a key.
  export APP_KEY="${GEN_APP_KEY:-base64:$(head -c 32 /dev/urandom | base64)}"
fi

if [ "${START_REVERB:-false}" = "true" ]; then
  export REVERB_APP_KEY="${REVERB_APP_KEY:-${GEN_REVERB_APP_KEY:-$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')}}"
  export REVERB_APP_SECRET="${REVERB_APP_SECRET:-${GEN_REVERB_APP_SECRET:-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')}}"
fi

if [ "${DB_CONNECTION:-pgsql}" = "pgsql" ]; then
  echo "[entrypoint] waiting for postgres at ${DB_HOST}:${DB_PORT:-5432}..."
  for i in $(seq 1 60); do
    if pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USERNAME" >/dev/null 2>&1; then break; fi
    sleep 1
  done
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  php artisan migrate --force
  # seeding is idempotent (skips existing bot records)
  php artisan db:seed --force
fi

php artisan config:cache >/dev/null
php artisan route:cache >/dev/null
chown -R www-data:www-data storage bootstrap/cache

if [ "${START_REVERB:-false}" = "true" ]; then
  # WebSocket server for online battles, restarted if it ever exits
  ( while true; do
      php artisan reverb:start --host="${REVERB_SERVER_HOST:-0.0.0.0}" --port="${REVERB_SERVER_PORT:-8080}" &
      echo $! > /run/reverb.pid
      wait $! || true
      echo "[entrypoint] reverb exited, restarting in 1s"; sleep 1
    done ) &
  # ... and if it stops answering while its port still accepts connections (seen when the container's network was
  # changed under it: every room then fell back to polling, and it ignored SIGTERM): three checks 10 s apart
  # without an HTTP answer end it, and the loop above starts another
  ( misses=0
    while sleep 10; do
      if curl -s -m 5 -o /dev/null "http://127.0.0.1:${REVERB_SERVER_PORT:-8080}/"; then misses=0; else misses=$((misses + 1)); fi
      if [ "$misses" -ge 3 ]; then
        echo "[entrypoint] reverb does not answer, ending it"
        kill -9 "$(cat /run/reverb.pid)" 2>/dev/null || true
        misses=0
      fi
    done ) &
fi

exec "$@"
