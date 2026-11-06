# Restore test: the quarterly drill

A backup you have never restored is a hope, not a backup. Once a quarter (first week of January,
April, July and October), restore the Litestream replica somewhere harmless, check it opens cleanly
and compare it with the live database. Fifteen minutes.

What runs: `python -m app.cli restore-test` (`make restore-test` locally). It restores the replica
into `/tmp/tp-restore-test/portal.db`, runs `PRAGMA integrity_check`, prints a table of row counts
(live vs restored) for every table and exits 0 only when the check says `ok` and every table that
isn't expected to drift matches.

## 1. On Fly (the real thing)

Litestream and the bucket settings are already on the machine, so this restores from Tigris for real.

```sh
fly ssh console -C "python -m app.cli restore-test"
```

The restored copy lands at `/tmp/tp-restore-test/portal.db` on the machine and is thrown away at
the next restart. Nothing touches `/data`.

If you have renamed the app, add `-a <app-name>`.

## 2. Locally (a second opinion, and the way to practise without the machine)

You need the Litestream binary and the bucket credentials on your Mac.

```sh
brew install benbjohnson/litestream/litestream
```

Get the values the Fly app uses (they are secrets, so Fly won't print them; copy them from the Tigris
dashboard, or run the next command on the machine):

```sh
fly ssh console -C "env" | grep -E "^(BUCKET_NAME|AWS_ENDPOINT_URL_S3|AWS_REGION|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)="
```

Export them in your shell (never into `.env` in the repo and never into a commit), then:

```sh
export BUCKET_NAME=… AWS_ENDPOINT_URL_S3=… AWS_REGION=auto AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=…
make restore-test
```

Locally there is no live database to compare with (unless you point `TRADING_PORTAL_DATA_DIR` at a
copy), so the drill prints the restored counts on their own and passes on `integrity_check: ok`.

To restore from a particular moment (Litestream keeps 72 hours of history):

```sh
cd backend && .venv/bin/litestream restore -timestamp 2026-11-06T09:00:00Z -o /tmp/tp-restore-test/portal.db "s3://$BUCKET_NAME/litestream/portal.db"
.venv/bin/python -m app.cli restore-test --replica /tmp/tp-restore-test
```

(The second command takes a directory holding a `.db` as a "file replica": it skips Litestream and
just checks and compares.)

## 3. Without Litestream at all

`make restore-test REPLICA=<directory>` accepts a directory holding a snapshot (for example the
`db/` folder unzipped from an admin **Export everything**). It prints, in capitals, that the real
Litestream restore was not exercised. Useful for checking an export; it does not count as the drill.

## What a pass looks like

```
$ litestream restore -o /tmp/tp-restore-test/portal.db s3://…/litestream/portal.db
Restored s3://…/litestream/portal.db with Litestream.

PRAGMA integrity_check: ok

Row counts: live /data/portal.db vs restored /tmp/tp-restore-test/portal.db
table                  live  restored
---------------------  ----  --------
alert_deliveries         12        12  =
app_state                 4         4  =
audit_log               812       810  ~ changes continuously
…
sessions                  6         5  ~ changes continuously
strategies                4         4  =
trades                 1180      1180  =
users                     3         3  =

'~' tables (sessions, leases, app_state, audit_log, price_cache, …) change continuously and are allowed to differ.

RESTORE TEST PASSED: integrity ok and every other table matches.
```

- `=` means identical. `~` tables (`sessions`, `leases`, `app_state`, `audit_log`, `price_cache`,
  `feed_runs`, `alert_deliveries`) change on their own every minute, so a small difference there is
  expected and ignored.
- `MISMATCH` on any other table (`users`, `strategies`, `trades`, `screenshots`, `events`, …) fails
  the drill. If you imported trades in the seconds between the replica and the live read, run it
  again; a repeatable mismatch is a real problem.

## If it fails

| Symptom | What it means | Do this |
|---|---|---|
| `no matching backups found` or `litestream restore failed` | Litestream isn't writing to the bucket | `fly logs` and look for `litestream` lines. Check `fly secrets list` shows `BUCKET_NAME`, `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Check the bucket in the Tigris dashboard has a `litestream/portal.db/` folder with recent files. |
| `integrity_check` is not `ok` | The replica is corrupt | Restore from an earlier point with `-timestamp` (above). Take an **Export everything** from the admin page right away, so a good copy exists off the machine. |
| `MISMATCH` that repeats | The replica is behind or stale | `fly ssh console -C "litestream replicas /data/portal.db"` shows the replica's position; `fly logs` shows sync errors. Restart the machine (`fly machine restart`) and re-run. |
| `litestream` not on PATH (on the machine) | The image was built without it | The Dockerfile's `litestream` stage failed or was changed: redeploy from `main`. |

Whatever the cause: while the replica is in doubt, take an **Export everything** zip (Admin → Users)
and keep it somewhere safe. That zip is a consistent snapshot of the database plus every screenshot.

## Record the date

Add a line here each time, newest first:

| Date | Where | Result | Notes |
|---|---|---|---|
| _not run yet_ | | | First deploy pending (docs/DEPLOY.md) |
