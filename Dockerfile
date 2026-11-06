# Build the front end, then run FastAPI serving it. Data lives on the Fly volume at /data; the SQLite
# database streams to the Tigris bucket through Litestream (see litestream.yml and backend/entrypoint.sh).
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Litestream: one pinned release (linux x86_64), fetched and unpacked in its own stage so the final
# image only gains the binary. Bump LITESTREAM_VERSION deliberately; the tarball must unpack and run.
FROM debian:bookworm-slim AS litestream
ARG LITESTREAM_VERSION=0.5.14
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL -o /tmp/litestream.tar.gz \
      "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-x86_64.tar.gz" \
 && tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin litestream \
 && chmod +x /usr/local/bin/litestream \
 && /usr/local/bin/litestream version

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TRADING_PORTAL_DATA_DIR=/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
RUN pip install --no-cache-dir --no-deps -e ./backend && chmod +x backend/entrypoint.sh
COPY --from=web /app/frontend/dist frontend/dist
COPY --from=litestream /usr/local/bin/litestream /usr/local/bin/litestream
COPY litestream.yml /etc/litestream.yml
WORKDIR /app/backend
EXPOSE 8080
CMD ["/app/backend/entrypoint.sh"]
