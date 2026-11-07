# Deploying the Trading Portal to Fly.io

One small always-on machine in London, a 1 GB volume for the SQLite database, a Tigris bucket for
the screenshots and the Litestream backup stream. Under $5 a month. Every command below is run from
the repo root on your Mac unless it says otherwise. Do the steps in order; each one is quick.

What you end up with:

| Piece | Where | Why |
|---|---|---|
| The app (FastAPI + built front end, one Docker image) | Fly machine `shared-cpu-1x`, 512 MB, `lhr`, always on | Serves the portal and runs the scheduler that sends push alerts |
| `portal.db` (SQLite, WAL) | Fly volume `portal_data` mounted at `/data` | The one copy the app writes to |
| Backup stream of `portal.db` | Tigris bucket, `litestream/portal.db/` | Litestream copies every change within a second; 72 hours of point-in-time history |
| Screenshots | Same Tigris bucket, `screenshots/…` | Off the machine from day one, so the volume stays tiny |

## 0. Before you start

- Push access to the GitHub repo, and `main` green in CI.
- A Fly.io account with a card on it (new orgs have no free allowance; the bill is small).
- Your JBlanked API key (free tier is fine) to hand.

## 1. Install flyctl and sign in

```sh
brew install flyctl
```

```sh
fly auth login
```

## 2. Create the app

The name in `fly.toml` is `trading-portal-jamie`. Names are global on Fly, so it may be taken.

```sh
fly apps create trading-portal-jamie
```

If Fly says the name is taken, pick another (say `tp-jamie`) and change it in **three places** before
going on, then use your name everywhere this guide says `trading-portal-jamie`:

1. `fly.toml` → `app = "…"`.
2. `fly.toml` → `[env]` → `TRADING_PORTAL_RP_ID = "<name>.fly.dev"` and
   `TRADING_PORTAL_ORIGINS = '["https://<name>.fly.dev"]'` (passkeys are bound to the host; get this
   wrong and Face ID sign-in won't work).
3. `.github/workflows/deploy.yml` doesn't hold the name itself (it reads `fly.toml`), but check the
   comment at the top of `fly.toml` and `docs/ops/RESTORE-TEST.md` for the URL.

Commit that change to `main` before the first deploy.

## 3. Create the volume (the database's home)

One gigabyte in London. The database for years of journaling is a few tens of megabytes.

```sh
fly volumes create portal_data --size 1 --region lhr --app trading-portal-jamie
```

Answer **y** to the warning about a single volume: Litestream is the redundancy here, not a second
volume.

## 4. Create the Tigris bucket (screenshots and backups)

Run this inside the repo folder so it attaches to the app from `fly.toml`:

```sh
fly storage create
```

Accept the suggested bucket name or type one (it is not public). Tigris then **stages these secrets on
the app for you**, so you never type them:

| Secret set by `fly storage create` | Used by |
|---|---|
| `AWS_ACCESS_KEY_ID` | boto3 (`S3Storage`) and Litestream, both read it directly |
| `AWS_SECRET_ACCESS_KEY` | same |
| `AWS_ENDPOINT_URL_S3` | `S3Storage` (setting `s3_endpoint_url`) and `litestream.yml` (`endpoint`) |
| `BUCKET_NAME` | `S3Storage` (`s3_bucket`) and `litestream.yml` (`bucket`): one bucket, two prefixes |
| `AWS_REGION` (sometimes) | Tigris uses `auto`; the app and `litestream.yml` default to `auto` if it's missing |

`STORAGE_BACKEND = "s3"` is already in `fly.toml` under `[env]`, so the app will use the bucket for
screenshots as soon as it boots. (If `BUCKET_NAME` were missing, the app would refuse to start with a
message saying exactly that, rather than quietly writing screenshots to the volume.)

Check what's staged:

```sh
fly secrets list --app trading-portal-jamie
```

## 5. Set the app's own secrets

Set each one by name. Replace the `<…>` placeholders; never paste real values into the repo or a chat.

**`TRADING_PORTAL_SECRET_KEY`**: derives the key that encrypts everyone's API keys in the database.
Generate it, then set it. Lose it and every saved API key has to be re-entered (nothing else is lost).

```sh
python3 -c 'import secrets;print(secrets.token_urlsafe(48))'
```

```sh
fly secrets set TRADING_PORTAL_SECRET_KEY='<paste the 64-character value>' --app trading-portal-jamie
```

**`JBLANKED_API_KEY`**: actuals for news releases (free tier: one request a day).

```sh
fly secrets set JBLANKED_API_KEY='<your JBlanked key>' --app trading-portal-jamie
```

**`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`**: the Web Push identity. Make a pair
locally (it writes the three lines into your local `.env`; they are not committed), then copy them:

```sh
make vapid
```

```sh
grep '^VAPID_' .env
```

```sh
fly secrets set VAPID_PUBLIC_KEY='<from .env>' VAPID_PRIVATE_KEY='<from .env>' VAPID_SUBJECT='mailto:<your email>' --app trading-portal-jamie
```

Each `fly secrets set` on an app that isn't running yet is staged for the first deploy; later ones
restart the machine (a few seconds).

## 6. Let GitHub Actions deploy

Create a deploy token (long-lived; `-x` is the expiry) and copy the output:

```sh
fly tokens create deploy -x 999999h --app trading-portal-jamie
```

In GitHub: the repo → **Settings** → **Secrets and variables** → **Actions** → **New repository
secret**, name `FLY_API_TOKEN`, value the token (the whole `FlyV1 …` string).

## 7. First deploy

Push `main`. CI runs the tests, builds the front end and then deploys:

```sh
git push origin main
```

Watch it in the repo's **Actions** tab. For the first deploy it is also fine (and quicker to debug) to
deploy from your Mac:

```sh
fly deploy --remote-only --app trading-portal-jamie
```

What happens on boot (`backend/entrypoint.sh`): Litestream looks for a replica in the bucket (none yet
on a fresh app, which is fine), `alembic upgrade head` creates the schema on `/data/portal.db`, then
uvicorn starts under `litestream replicate` so every write streams to the bucket. The health check
(`GET /api/health`, every 30 s) turns green once the database answers.

```sh
fly logs --app trading-portal-jamie
```

You should see `entrypoint: Litestream replica s3://…`, a few `alembic` lines, then uvicorn.

## 8. Create your admin account

Runs on the machine; it asks three questions (email, display name, password twice, 10+ characters):

```sh
fly ssh console -C "python -m app.cli create-admin" --app trading-portal-jamie
```

Non-interactive alternative (the password comes from an environment variable so it never appears in
shell history on the machine):

```sh
fly ssh console --app trading-portal-jamie
```

then inside:

```sh
ADMIN_PW='<password>' python -m app.cli create-admin --email you@example.com --name Jamie --password-env ADMIN_PW
```

Everyone else joins through **Admin → Users → Invite someone**.

## 9. Smoke checks (five minutes)

1. The API answers and sees the database:

   ```sh
   curl https://trading-portal-jamie.fly.dev/api/health
   ```

   Expect `"db_ok": true` and `"frontend_built": true`.

2. Open `https://trading-portal-jamie.fly.dev`, sign in with the admin account. The Hub greets you.

3. **Settings → API keys** → paste your Twelve Data key → **Test**. Prices start on the Hub and in the
   News Room.

4. On the iPhone: open the URL in Safari → **Share** → **Add to Home Screen**. Open it from the icon
   (push notifications only work from the installed app on iOS).

5. In the installed app: **Settings → Alerts** → **Turn on alerts on this device** → Allow → **Send
   test notification**. A notification arrives within a few seconds.

6. Add a passkey in **Settings → Passkeys** and sign in with Face ID once. If it fails with an origin
   error, `TRADING_PORTAL_RP_ID` / `TRADING_PORTAL_ORIGINS` in `fly.toml` don't match the URL (step 2).

7. In the Tigris dashboard (or `fly storage dashboard`) the bucket should show a `litestream/` folder
   within a minute of the first sign-in, and a `screenshots/` folder after the first upload.

## 10. Moving an existing local journal to Fly (only if you have one)

A fresh deploy needs none of this. If you've been using the app locally and want that data on Fly:

1. Stop the local app. Stop the Fly machine so nothing writes to `/data` while you copy:

   ```sh
   fly machine list --app trading-portal-jamie
   ```

   ```sh
   fly machine stop <machine id> --app trading-portal-jamie
   ```

2. Upload the database and the screenshots folder (`~/TradingPortal/data` by default) with SFTP:

   ```sh
   fly ssh sftp shell --app trading-portal-jamie
   ```

   inside: `put ~/TradingPortal/data/portal.db /data/portal.db`, then `put -r ~/TradingPortal/data/screenshots /data/screenshots`
   (if `-r` isn't supported by your flyctl, upload the folder as a tarball and `tar -xf` it on the
   machine with `fly ssh console`).

3. Start the machine, then copy the screenshots from the volume into the bucket (idempotent: run it
   again if it is interrupted; it never deletes the local files):

   ```sh
   fly machine start <machine id> --app trading-portal-jamie
   ```

   ```sh
   fly ssh console -C "python -m app.cli migrate-screenshots" --app trading-portal-jamie
   ```

   It prints `copied N, skipped M (already there), missing K`. `make migrate-screenshots` is the same
   command for a local shell. Once everything is copied you can delete `/data/screenshots` to free
   the volume.

The entrypoint never overwrites a database that already exists on `/data` (`restore -if-db-not-exists`),
so the uploaded file is what the app uses; Litestream starts streaming it straight away.

## 11. The first restore test

Do it in the first week, then every quarter: `docs/ops/RESTORE-TEST.md`. The short version:

```sh
fly ssh console -C "python -m app.cli restore-test" --app trading-portal-jamie
```

Expect `PRAGMA integrity_check: ok` and `RESTORE TEST PASSED`. Record the date in that document.

## 12. Keeping it under $5 a month

Expected: machine `shared-cpu-1x` 512 MB always on ≈ **$3.69**, volume 1 GB ≈ **$0.15**, Tigris within
its free 5 GB (no egress fees) ≈ **$0**, outbound data a few cents. About **$3.90**.

- `fly dashboard` → **Billing** shows the running total and the invoice. Check it after the first
  full month.
- `fly scale show --app trading-portal-jamie` must say **1** machine, `shared-cpu-1x`, **512MB**.
  Two machines doubles the bill (and the scheduler is single-instance anyway).
- `fly volumes list --app trading-portal-jamie` must show one 1 GB volume. Fly keeps daily volume
  snapshots for 5 days by default; those are free within the allowance.
- Tigris: the dashboard shows storage used. Screenshots are a few hundred KB each; 5 GB is roughly
  10,000 of them. Past that it's about $0.02/GB/month.
- Don't add a dedicated IPv4 address ($2/month): the shared one Fly gives the app is fine.

## What each secret is for

| Name | Set by | Used for | If it's wrong |
|---|---|---|---|
| `TRADING_PORTAL_SECRET_KEY` | you, step 5 | Derives the Fernet key for the per-user API-key vault | App refuses to start without it (production); change it and saved keys must be re-entered |
| `JBLANKED_API_KEY` | you, step 5 | Actual figures for news releases, once a day | News still shows Forex Factory's schedule; actuals stay blank |
| `VAPID_PUBLIC_KEY` | `make vapid`, step 5 | Identifies the app to the browsers' push services | Alerts can't be turned on; the Alerts page says so |
| `VAPID_PRIVATE_KEY` | `make vapid`, step 5 | Signs each push message | Same |
| `VAPID_SUBJECT` | you (`mailto:…`), step 5 | Contact address push services may use | Some push services reject sends |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `fly storage create`, step 4 | Credentials for the Tigris bucket (boto3 and Litestream) | Screenshot uploads fail with a storage error; Litestream logs auth errors; no backups |
| `AWS_ENDPOINT_URL_S3` | `fly storage create`, step 4 | Where the bucket lives (`https://t3.storage.dev`) | Same |
| `BUCKET_NAME` | `fly storage create`, step 4 | The bucket, shared by screenshots (`screenshots/`) and the database stream (`litestream/`) | App refuses to start: `STORAGE_BACKEND=s3 but BUCKET_NAME is not set` |
| `AWS_REGION` | `fly storage create` (sometimes) | Tigris region, `auto` | Defaults to `auto` when missing |
| `FLY_API_TOKEN` | you, step 6 (GitHub, not Fly) | Lets GitHub Actions run `fly deploy` | Deploys are skipped with a message in the Actions log |

Settings that are **not** secrets live in `fly.toml` under `[env]`: `TRADING_PORTAL_ENV=production`,
`TRADING_PORTAL_DATA_DIR=/data`, `STORAGE_BACKEND=s3`, the passkey host and origins, feeds live and
the scheduler on.

## Day to day

- **Deploy**: merge to `main`. CI tests, then deploys. Migrations run on boot.
- **Logs**: `fly logs --app trading-portal-jamie`.
- **Shell**: `fly ssh console --app trading-portal-jamie` (the app lives in `/app/backend`).
- **Restart**: `fly machine restart <id> --app trading-portal-jamie`.
- **Export everything**: Admin → Users → **Export everything** downloads a zip with a consistent
  database snapshot and every screenshot. Do it before anything risky.
- **Restore drill**: quarterly, `docs/ops/RESTORE-TEST.md`.
- **Disaster**: a new machine with an empty volume restores itself from the bucket on first boot
  (`litestream restore -if-replica-exists -if-db-not-exists`). Screenshots are already in the bucket.
