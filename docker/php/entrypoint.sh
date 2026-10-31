#!/usr/bin/env bash
# Waits for PostgreSQL, applies migrations and seeds, then starts the given command.
set -euo pipefail
cd /var/www/backend

if [ -z "${APP_KEY:-}" ]; then
  # The API is stateless, but Laravel wants a key; generate an ephemeral one.
  export APP_KEY="base64:$(head -c 32 /dev/urandom | base64)"
  echo "[entrypoint] APP_KEY not set, using an ephemeral key"
fi

if [ "${START_REVERB:-false}" = "true" ]; then
  # Reverb app credentials are never committed: generate them per container unless provided.
  export REVERB_APP_KEY="${REVERB_APP_KEY:-$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')}"
  export REVERB_APP_SECRET="${REVERB_APP_SECRET:-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')}"
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
      php artisan reverb:start --host="${REVERB_SERVER_HOST:-0.0.0.0}" --port="${REVERB_SERVER_PORT:-8080}" || true
      echo "[entrypoint] reverb exited, restarting in 1s"; sleep 1
    done ) &
fi

exec "$@"
