#!/bin/sh
# A dump of the database once a day into /backups, one file per day of the month: a month of days, each written
# over a month later, so there is nothing to tidy up. A dump that failed (database away, disk full) leaves the
# day's older file as it was.
# The dump drops and recreates its tables (--clean), so it restores over the database as it stands:
#   docker compose stop app
#   docker compose exec -T backup sh -c 'gzip -dc /backups/touge-dayNN.sql.gz | psql -v ON_ERROR_STOP=1 -q'
#   docker compose start app
# The desk's reports (About → AI窓口) are packed next to it as desk-dayNN.tar.gz:
#   docker compose exec -T backup cat /backups/desk-dayNN.tar.gz | docker compose exec -T app tar -xzf - -C storage/app/desk
while true; do
  day=$(date +%d)
  if pg_dump --no-owner --clean --if-exists | gzip > /backups/dump.part && [ "$(gzip -dc /backups/dump.part | head -c 64 | wc -c)" -gt 0 ]; then
    mv /backups/dump.part "/backups/touge-day$day.sql.gz"
    echo "[backup] touge-day$day.sql.gz $(date -u +%FT%TZ)"
  else
    echo "[backup] failed $(date -u +%FT%TZ)"
  fi
  # the desk's reports (the `desk` volume, mounted read only): the same day's file next to the dump. Plain text
  # of a few MB at most; restoring is unpacking it into the volume
  if [ -d /desk ] && [ -n "$(ls -A /desk 2>/dev/null)" ]; then
    if tar -czf /backups/desk.part -C /desk . 2>/dev/null; then
      mv /backups/desk.part "/backups/desk-day$day.tar.gz"
      echo "[backup] desk-day$day.tar.gz $(date -u +%FT%TZ)"
    else
      rm -f /backups/desk.part
      echo "[backup] desk failed $(date -u +%FT%TZ)"
    fi
  fi
  sleep 86400
done
