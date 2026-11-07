#!/bin/sh
# Container entrypoint: restore the database from the Litestream replica if the volume is empty,
# apply migrations, then run the API under Litestream so every change streams to the bucket.
#
# With a replica configured (BUCKET_NAME and AWS_ENDPOINT_URL_S3 set, litestream installed):
#   litestream restore -if-replica-exists -if-db-not-exists   (never overwrites a database already on /data)
#   alembic upgrade head
#   litestream replicate -exec "uvicorn …"                    (Litestream exits when uvicorn exits)
# Otherwise (local Docker run, no Tigris): alembic upgrade head && uvicorn, plain.
set -eu

DATA_DIR="${TRADING_PORTAL_DATA_DIR:-/data}"
DB_PATH="$DATA_DIR/portal.db"
CONFIG="${LITESTREAM_CONFIG:-/etc/litestream.yml}"
APP="uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"

mkdir -p "$DATA_DIR"
cd /app/backend

if [ -n "${BUCKET_NAME:-}" ] && [ -n "${AWS_ENDPOINT_URL_S3:-}" ] && command -v litestream >/dev/null 2>&1; then
  echo "entrypoint: Litestream replica s3://$BUCKET_NAME/litestream/portal.db (config $CONFIG)"
  if [ -f "$DB_PATH" ]; then
    echo "entrypoint: $DB_PATH already exists; keeping it (no restore)"
  else
    echo "entrypoint: no database on the volume; restoring from the replica if one exists"
  fi
  litestream restore -if-replica-exists -if-db-not-exists -config "$CONFIG" "$DB_PATH"
  alembic upgrade head
  echo "entrypoint: starting uvicorn under litestream replicate"
  exec litestream replicate -config "$CONFIG" -exec "$APP"
else
  if [ -n "${BUCKET_NAME:-}" ] || [ -n "${AWS_ENDPOINT_URL_S3:-}" ]; then
    echo "entrypoint: WARNING bucket settings are incomplete or litestream is missing; running WITHOUT backups"
  else
    echo "entrypoint: no bucket configured; running without Litestream (local data only)"
  fi
  alembic upgrade head
  echo "entrypoint: starting uvicorn"
  exec $APP
fi
