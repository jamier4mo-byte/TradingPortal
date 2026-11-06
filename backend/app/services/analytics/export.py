"""Export for AI (F8 + 2.4): a streamed zip Claude can read, plus Copy for AI and a CSV.

Zip layout:
    README_prompt.md   ready-to-paste prompt: what's in the bundle and how to analyse it
    strategy.md        per strategy: description, rulebook, reasoning template, profile, KPIs with formulas
    trades.jsonl       one JSON object per trade: every field, reasoning, tags, rules, outcome, image paths
    images/            screenshots, long edge ≤ 1568 px (Claude's vision sweet spot), WebP (JPEG fallback)
    manifest.json      app version, export time, filters, counts and a SHA-256 for every other file

Only trade, strategy and display-name data is read: never emails, password hashes, sessions or API keys.
The zip is written entry by entry and yielded as it grows, so memory stays at about one image.
"""

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime

from PIL import Image, features
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import __version__
from ...models import Strategy, Trade, User
from ...schemas.analytics import AnalyticsQuery, ExportQuery
from .. import journal_rules as rules
from ..journal import live_screenshots
from ..storage import StorageError, get_storage
from .insights import insights
from .metrics import BY_ID, compute
from .query import apply_filters, ideal_block, load_rows, reconcile
from .rows import WEEKDAYS, Row, prepare
from .series import breakdowns, rulebook

MAX_EDGE = 1568
IMAGE_FORMAT = "WEBP" if features.check("webp") else "JPEG"
IMAGE_EXT = "webp" if IMAGE_FORMAT == "WEBP" else "jpg"
COPY_TRADE_LINES = 120

HEADLINE = (
    "trades",
    "win_rate",
    "net_pnl",
    "total_r",
    "avg_r",
    "expectancy_r",
    "expectancy_pnl",
    "profit_factor",
    "avg_win_r",
    "avg_loss_r",
    "max_dd_r",
    "max_dd_pnl",
    "longest_win_streak",
    "longest_loss_streak",
    "best_r",
    "worst_r",
    "avg_duration",
    "rules_kept_rate",
    "exit_efficiency",
    "r_left_on_table",
)
IDEAL_HEADLINE = ("trades", "avg_r", "avg_tp_r", "avg_sl_distance", "avg_tp_distance", "median_duration")


# ---- selection -----------------------------------------------------------------------------------


def _kinds(source: str) -> list[str]:
    return {"ideal": ["ideal"], "backtest": ["backtest"], "compare": ["ideal", "backtest"]}[source]


def select_rows(db: Session, user: User, q: AnalyticsQuery) -> list[Row]:
    """The same rows the Analytics view shows for these filters."""
    from ..tags import resolve_tag

    rows = prepare(
        load_rows(db, user, kinds=_kinds(q.source), strategy_id=q.strategy_id, scope=q.scope),
        user.breakeven_threshold,
    )
    tag_ids = None
    if q.filters.tags:
        tag_ids = {t.id for t in (resolve_tag(db, n) for n in q.filters.tags) if t}
    return apply_filters(rows, q.filters, tag_ids=tag_ids)


def _load_trades(db: Session, ids: list[int]) -> dict[int, Trade]:
    out: dict[int, Trade] = {}
    for i in range(0, len(ids), 500):
        for t in db.scalars(select(Trade).where(Trade.id.in_(ids[i : i + 500]))):
            out[t.id] = t
    return out


# ---- formatting ----------------------------------------------------------------------------------


def fmt_value(metric_id: str, v: float | None) -> str:
    if v is None:
        return "—"
    unit = BY_ID[metric_id].unit if metric_id in BY_ID else "count"
    sign = "+" if v > 0 else "−" if v < 0 else ""
    if unit == "pct":
        return f"{round(v * 100)}%"
    if unit == "r":
        return f"{sign}{abs(v):.2f}R"
    if unit == "usd":
        return f"{sign}${abs(v):,.2f}"
    if unit == "duration":
        return fmt_duration(v)
    if unit == "ratio":
        return f"{v:.2f}"
    return f"{v:g}" if isinstance(v, float) and not v.is_integer() else f"{int(v)}"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    m = round(seconds / 60)
    if m < 60:
        return f"{m} min"
    h, rest = divmod(m, 60)
    if h < 24:
        return f"{h}h {rest}m" if rest else f"{h}h"
    return f"{h // 24}d {h % 24}h"


def describe_filters(q: AnalyticsQuery) -> str:
    f = q.filters
    parts: list[str] = []
    if f.date_from or f.date_to:
        parts.append(f"dates {f.date_from or '…'} to {f.date_to or '…'}")
    for label, values in (
        ("instruments", f.instruments),
        ("sessions", f.sessions),
        ("entry models", f.entry_models),
        ("tags", f.tags),
        ("outcomes", f.outcomes),
    ):
        if values:
            parts.append(f"{label} {', '.join(values)}")
    if f.weekdays:
        parts.append("days " + ", ".join(WEEKDAYS[d] for d in sorted(f.weekdays)))
    if f.directions:
        parts.append("direction " + ", ".join("long" if d == "buy" else "short" for d in f.directions))
    if f.time_from or f.time_to:
        parts.append(f"entry time {f.time_from or '00:00'}–{f.time_to or '24:00'} UK")
    if f.owners:
        parts.append(f"owners #{', #'.join(str(o) for o in f.owners)}")
    if f.rules:
        parts.append("all rules kept" if f.rules == "all_kept" else "any rule broken")
    if f.news:
        parts.append(
            {"inside": "inside news windows", "outside": "outside news windows", "no_data": "no news data"}[
                f.news
            ]
        )
    if f.news_event_types:
        parts.append(f"news events {', '.join(f.news_event_types)}")
    scope = {"mine": "my trades", "others": "other people's trades", "everyone": "everyone's trades"}[q.scope]
    return f"{q.source} · {scope}" + (f" · {'; '.join(parts)}" if parts else " · no other filters")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "export"


def export_filename(db: Session, q: AnalyticsQuery, ext: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    name = "all-strategies"
    if q.strategy_id:
        s = db.get(Strategy, q.strategy_id)
        name = slugify(s.name) if s else name
    return f"trading-portal-{name}-{q.source}-{now:%Y%m%d-%H%M}.{ext}"


# ---- per-trade record ----------------------------------------------------------------------------


def _r4(v: float | None) -> float | None:
    return None if v is None else round(v, 4)


def trade_record(t: Trade, row: Row, n: int, owner: str, strategy: Strategy, images: list[dict]) -> dict:
    labels = {f["key"]: f["label"] for f in strategy.reasoning_template or []}
    rule_text = {r["key"]: r["text"] for r in strategy.rules or []}
    uk = rules.to_uk(t.opened_at)
    return {
        "n": n,
        "id": t.id,
        "fx_replay_id": t.fx_id,
        "strategy": strategy.name,
        "logged_by": owner,
        "kind": t.kind,
        "instrument": t.instrument,
        "direction": "long" if t.side == "buy" else "short",
        "opened_at_utc": t.opened_at.isoformat(),
        "opened_uk": uk.strftime("%Y-%m-%d %H:%M"),
        "closed_at_utc": t.closed_at.isoformat() if t.closed_at else None,
        "weekday": WEEKDAYS[uk.weekday()],
        "session": t.session_label,
        "duration_seconds": t.duration_seconds,
        "entry_price": t.entry_price,
        "stop_price": t.initial_sl,
        "target_price": t.max_tp,
        "best_price_fx_replay": t.ideal_tp,
        "exit_price": t.exit_price,
        "stop_distance": t.sl_distance,
        "target_distance": t.tp_distance,
        "target_r": _r4(t.tp_r),
        "r": _r4(t.r_multiple),
        "pnl": t.pnl,
        "outcome": row.outcome,
        "max_favourable_r": _r4(row.mfe_r),
        "max_adverse_r": _r4(t.mae_r),
        "entry_model": t.entry_model,
        "reasoning": {labels.get(k, k): v for k, v in (t.reasoning or {}).items() if str(v).strip()},
        "notes": t.notes or "",
        "tags": [tag.name for tag in t.tags],
        "rules": [
            {"rule": rule_text.get(k, k), "kept": bool(v)} for k, v in (t.rules_followed or {}).items()
        ],
        "all_rules_kept": row.rules_kept,
        "news_impact": t.news_impact,
        "news": row.news_status,
        "news_events": t.news_events or [],
        "completed": t.annotated_at is not None,
        "images": images,
    }


def resize_image(data: bytes) -> tuple[bytes, int, int]:
    """Long edge ≤ MAX_EDGE, re-encoded as WebP (or JPEG). Never upscales."""
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        if IMAGE_FORMAT == "JPEG" and img.mode == "RGBA":
            img = img.convert("RGB")
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format=IMAGE_FORMAT, quality=85)
        return out.getvalue(), img.width, img.height


# ---- markdown --------------------------------------------------------------------------------------


def _kpi_table(kpis: dict, ids: tuple[str, ...]) -> list[str]:
    lines = ["| Metric | Value | How it's worked out |", "|---|---|---|"]
    for mid in ids:
        if mid in kpis and mid in BY_ID:
            m = BY_ID[mid]
            lines.append(f"| {m.label} | {fmt_value(mid, kpis[mid])} | {m.formula.replace('|', '\\|')} |")
    return lines


def _group_table(title: str, groups: list[dict]) -> list[str]:
    groups = [g for g in groups if g["n"]]
    if not groups:
        return []
    lines = [f"**By {title}**", "", "| | Trades | Win rate | Total R | Avg R |", "|---|---|---|---|---|"]
    for g in groups:
        wr = f"{round(g['win_rate'] * 100)}%" if g["win_rate"] is not None else "—"
        lines.append(
            f"| {g['label']} | {g['n']} | {wr} | {fmt_value('total_r', g['total_r'])} | "
            f"{fmt_value('avg_r', g['avg_r'])} |"
        )
    return lines + [""]


def strategy_markdown(db: Session, strategy: Strategy, rows: list[Row], q: AnalyticsQuery, owner: str) -> str:
    ideal = [r for r in rows if r.kind == "ideal"]
    backtest = [r for r in rows if r.kind == "backtest"]
    out = [f"## {strategy.name}", ""]
    out.append(
        f"Logged by {owner} · instruments {', '.join(strategy.instruments) or '—'} · timeframes "
        f"{', '.join(strategy.timeframes) or '—'} · entry models {', '.join(strategy.entry_models) or '—'} · "
        f"CSV timezone {strategy.csv_timezone}"
    )
    out.append("")
    if strategy.description:
        out += [strategy.description, ""]
    if strategy.rules:
        out += ["### Rulebook", ""] + [f"{i}. {r['text']}" for i, r in enumerate(strategy.rules, 1)] + [""]
    if strategy.reasoning_template:
        out += ["### Reasoning template (each trade's `reasoning` uses these headings)", ""]
        out += [f"- {f['label']}" for f in strategy.reasoning_template] + [""]
    if ideal:
        block = ideal_block(ideal)
        out += [f"### Ideal trades profile ({len(ideal)} winners: what a textbook trade looks like)", ""]
        out += _kpi_table(block["kpis"], IDEAL_HEADLINE) + [""]
        p = block["profile"]
        for label, key in (
            ("Most common entry hours (UK)", "entry_hours"),
            ("Sessions", "sessions"),
            ("Entry models", "entry_models"),
            ("Weekdays", "weekdays"),
            ("Tags", "tags"),
        ):
            if p[key]:
                out.append(f"- {label}: " + ", ".join(f"{x['label']} ({x['count']})" for x in p[key]))
        out.append("")
    if backtest:
        kpis = compute(backtest, "backtest")
        out += [f"### Backtest results ({len(backtest)} trades)", ""]
        out += _kpi_table(kpis, HEADLINE) + [""]
        b = breakdowns(backtest)
        for title, key in (("session", "session"), ("weekday", "weekday"), ("entry model", "entry_model")):
            out += _group_table(title, b[key])
        rb = rulebook(backtest, strategy.rules)
        if rb["marked"]:
            kept, broken = rb["all_kept"], rb["any_broken"]
            out += [
                "### Rulebook adherence",
                "",
                f"- All rules kept: {kept['n']} trades, total {fmt_value('total_r', kept['total_r'])}, "
                f"average {fmt_value('avg_r', kept['avg_r'])}",
                f"- Any rule broken: {broken['n']} trades, total {fmt_value('total_r', broken['total_r'])}, "
                f"average {fmt_value('avg_r', broken['avg_r'])}",
            ]
            for r in rb["rules"]:
                if r["broken"]:
                    out.append(
                        f"- Broke “{r['text']}” {r['broken']}×; cost {fmt_value('total_r', r['cost_r'])}"
                    )
            out.append("")
    found = insights(backtest or ideal, "backtest" if backtest else "ideal")
    if found:
        out += ["### Auto-insights (slices of 8+ trades; under 20 is an early signal)", ""]
        out += [f"- {i['text']}" for i in found] + [""]
    rec = reconcile(db, strategy, _kinds(q.source))
    if rec:
        out += ["### Reconcile against FX Replay's CSV", ""]
        for r in rec:
            mark = (
                "✓"
                if r["ok"]
                else f"✗ off by {r['diff_trades']} trades, {fmt_value('net_pnl', r['diff_pnl'])}"
            )
            out.append(
                f"- {r['filename'] or 'import'} ({r['kind']}): app {r['app']['trades']} trades "
                f"{fmt_value('net_pnl', r['app']['pnl'])} vs kept from CSV {r['kept']['trades']} trades "
                f"{fmt_value('net_pnl', r['kept']['rpnl_sum'])} {mark}"
            )
        out.append("")
    return "\n".join(out)


def strategy_md(db: Session, user: User, q: AnalyticsQuery, rows: list[Row], users: dict[int, User]) -> str:
    by_strategy: dict[int, list[Row]] = {}
    for r in rows:
        by_strategy.setdefault(r.strategy_id, []).append(r)
    head = [
        "# Strategy dossier",
        "",
        f"Exported {datetime.now(UTC):%d %b %Y %H:%M} UTC from the Trading Portal {__version__} "
        f"by {user.display_name}.",
        f"Filters: {describe_filters(q)}.",
        f"Breakeven threshold: ±${user.breakeven_threshold:g} of P&L. Times are UK (Europe/London).",
        "",
    ]
    if not rows:
        head.append("No trades match these filters.")
    body = []
    for sid, srows in by_strategy.items():
        s = db.get(Strategy, sid)
        if s:
            owner = users[s.owner_id].display_name if s.owner_id in users else "someone"
            body.append(strategy_markdown(db, s, srows, q, owner))
    return "\n".join(head) + "\n" + "\n\n".join(body) + "\n"


README_PROMPT = """# Read me first: how to analyse this trading bundle

Paste this whole file into Claude (or attach the zip) and say "Go".

## Who I am and what this is

I'm a discretionary trader who backtests ICT/SMC-style setups in FX Replay and journals them in my Trading
Portal. This bundle is an export of {what}. It was made on {when} with these filters: {filters}.

## What's in the bundle

- `strategy.md`: for each strategy, the idea, the rulebook, the reasoning template, the ideal-trade profile
  (winners only, the textbook examples) and the backtest KPIs, each with the formula used. Start here.
- `trades.jsonl`: one JSON object per line, one line per trade ({trades} trades). Every field, my written
  reasoning (keyed by the template headings), tags, each rule with kept true/false, the outcome, and the
  relative paths of its screenshots.
- `images/`: {images_line}
- `manifest.json`: counts, the filters, and a SHA-256 for every file, so you can tell nothing is missing.

## How to read the numbers

- **R** is the realised risk multiple, signed: a clean stop-out is −1.00R; +2R made twice the risk.
  `target_r` is the planned target in R. `max_favourable_r` is the best R price reached (entered by hand, or
  FX Replay's "ideal" best price, which can be up to a week after the close); `max_adverse_r` is the worst.
- **Outcome**: a win or loss is P&L beyond ±${threshold:g}; anything inside is a breakeven.
  **Win rate leaves breakevens out** (wins ÷ (wins + losses)), the same way FX Replay does.
- **Ideal trades** are hand-picked winners. They describe what a good trade looks like; they are not a
  track record, so never read their win rate as an edge.
- **Backtest trades** are every valid setup taken in replay: wins, losses and breakevens.
- Dollar P&L uses FX Replay's position sizes, which vary, so prefer R when comparing trades.
- Times are UK. Sessions: Asia 00–08, London 08–13, New York 13–22; anything else is "Out of session".
- `news` is "inside" when the entry was within my news window (± minutes) of a high-impact release for a
  currency that moves the instrument (listed in `news_events`, with minutes from entry), "outside" when
  it wasn't, and "no_data" when our news history doesn't cover that date yet. Treat no_data as unknown.
- Small samples: under 20 trades in a slice is an early signal, not a finding. Say so when you use one.

## What I'd like from you

1. **Check the data first.** Flag anything that looks wrong or inconsistent (a stop on the wrong side,
   an R that doesn't match the prices, reasoning that contradicts the direction, missing screenshots).
2. **What's working.** Which conditions produce my best trades? Use the numbers, and quote trade `n`s.
3. **Where the edge is and isn't**, with numbers: by session, entry hour, weekday, entry model, direction,
   and rulebook adherence. Give n for every claim and say how confident you are.
4. **Ideal vs backtest.** How much of the ideal trades' average R do the backtest winners capture? Which
   ideal patterns (times, models, stop sizes) fail to hold up in the backtest?
5. **Look at the screenshots** for my 5 best and 5 worst trades. What do the charts show that the numbers
   don't? Do the losers break any rule in a way the checkboxes missed?
6. **Exits.** Using `max_favourable_r` and `max_adverse_r`, am I leaving R on the table or getting shaken out?
7. **Rule changes.** The 3 specific filters or rule changes most likely to keep the winners and cut the
   losers, each with the trades it would have removed and the R impact.
8. **What to record next.** Data I'm not capturing that would make the next review sharper.

Keep it plain and direct. Tables are welcome. Don't invent numbers that aren't in the files; if you
compute something, say how.
"""


# ---- the zip ----------------------------------------------------------------------------------------


def images_line(count: int) -> str:
    if not count:
        return "no screenshots in this export (none were added yet, or they were left out)."
    return (
        f"{count} screenshots, long edge at most 1,568 px. Each trade has up to three labelled shots:\n"
        "  `htf` (higher-timeframe context), `entry` and `outcome`, plus extras. File names are\n"
        f"  `<trade n>-<slot>.{IMAGE_EXT}`, matching `n` in `trades.jsonl`."
    )


class _Sink(io.RawIOBase):
    """Unseekable buffer zipfile writes into; we drain it after every entry."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self.buf += b
        return len(b)

    def take(self) -> bytes:
        out = bytes(self.buf)
        self.buf.clear()
        return out


def _what(db: Session, q: AnalyticsQuery) -> str:
    kinds = {"ideal": "ideal trades", "backtest": "backtest trades", "compare": "ideal and backtest trades"}
    s = db.get(Strategy, q.strategy_id) if q.strategy_id else None
    return f"the {kinds[q.source]} of “{s.name}”" if s else f"the {kinds[q.source]} of every strategy"


def stream_ai_zip(db: Session, user: User, q: ExportQuery) -> Iterator[bytes]:
    """Read everything from the database now; return a generator that only reads images and zips.

    The response streams after the request's database session has closed, so nothing lazy may touch it.
    """
    rows = select_rows(db, user, q)
    rows.sort(key=lambda r: (r.opened_at, r.id))  # trades in the order they were taken
    trades = _load_trades(db, [r.id for r in rows])
    strategy_ids = {r.strategy_id for r in rows}
    strategies = {s.id: s for s in db.scalars(select(Strategy).where(Strategy.id.in_(strategy_ids)))}
    owner_ids = {r.owner_id for r in rows} | {s.owner_id for s in strategies.values()}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(owner_ids)))} if owner_ids else {}
    dossier = strategy_md(db, user, q, rows, users)
    what = _what(db, q)
    planned = []
    for n, row in enumerate(rows, 1):
        t = trades.get(row.id)
        if not t:
            continue
        shots = [(s.slot, s.full_key) for s in live_screenshots(t)] if q.include_images else []
        owner = users[t.owner_id].display_name if t.owner_id in users else "someone"
        planned.append((n, row, t, shots, owner))
    threshold, display_name = user.breakeven_threshold, user.display_name
    filters_json, filters_text = q.filters.model_dump(mode="json"), describe_filters(q)

    def generate() -> Iterator[bytes]:
        storage = get_storage()
        sink = _Sink()
        files: list[dict] = []
        missing: list[str] = []
        zf = zipfile.ZipFile(sink, "w")

        def add(path: str, data: bytes, *, compress: bool = True) -> None:
            info = zipfile.ZipInfo(path, date_time=datetime.now(UTC).timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
            files.append({"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

        jsonl = io.StringIO()
        image_count = 0
        for n, row, t, shots, owner in planned:
            images: list[dict] = []
            counts: dict[str, int] = {}
            for slot, key in shots:
                counts[slot] = counts.get(slot, 0) + 1
                suffix = f"-{counts[slot]}" if slot == "extra" else ""
                path = f"images/{n:04d}-{slot}{suffix}.{IMAGE_EXT}"
                try:
                    data, w, h = resize_image(storage.get(key))
                except (StorageError, OSError, ValueError):
                    missing.append(path)
                    images.append({"slot": slot, "path": None, "missing": True})
                    continue
                add(path, data, compress=False)
                image_count += 1
                images.append(
                    {"slot": slot, "path": path, "width": w, "height": h, "sha256": files[-1]["sha256"]}
                )
                yield sink.take()
            record = trade_record(t, row, n, owner, strategies[t.strategy_id], images)
            jsonl.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
        add("trades.jsonl", jsonl.getvalue().encode())
        add("strategy.md", dossier.encode())
        add(
            "README_prompt.md",
            README_PROMPT.format(
                what=what,
                when=f"{datetime.now(UTC):%d %b %Y %H:%M} UTC",
                filters=filters_text,
                trades=len(planned),
                images_line=images_line(image_count),
                threshold=threshold,
            ).encode(),
        )
        yield sink.take()
        manifest = {
            "app": "Trading Portal",
            "version": __version__,
            "format": "trading-portal-ai-export",
            "format_version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "exported_by": display_name,
            "source": q.source,
            "scope": q.scope,
            "strategy_id": q.strategy_id,
            "filters": filters_json,
            "filters_text": filters_text,
            "breakeven_threshold": threshold,
            "counts": {
                "trades": len(planned),
                "strategies": len(strategies),
                "images": image_count,
                "missing_images": len(missing),
            },
            "images": {
                "max_long_edge": MAX_EDGE,
                "format": IMAGE_FORMAT.lower(),
                "included": q.include_images,
            },
            "missing_images": missing,
            "files": files,
            "note": "SHA-256 covers every file except this manifest.",
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=_json_default))
        zf.close()
        yield sink.take()

    return generate()


def _json_default(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return str(v)


# ---- copy for AI and CSV --------------------------------------------------------------------------


def copy_text(db: Session, user: User, q: AnalyticsQuery) -> dict:
    """strategy.md plus a compact KPI line and one line per trade, for the clipboard."""
    rows = select_rows(db, user, q)
    rows.sort(key=lambda r: (r.opened_at, r.id))
    owner_ids = {r.owner_id for r in rows} | {
        s.owner_id for s in db.scalars(select(Strategy).where(Strategy.id.in_({r.strategy_id for r in rows})))
    }
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(owner_ids)))} if owner_ids else {}
    md = strategy_md(db, user, q, rows, users)
    lines = [md, "## Trades (compact)", ""]
    lines.append("n | opened (UK) | instrument | dir | model | session | R | P&L | outcome | rules kept")
    for n, r in enumerate(rows[:COPY_TRADE_LINES], 1):
        uk = rules.to_uk(r.opened_at).strftime("%Y-%m-%d %a %H:%M")
        kept = "—" if r.rules_kept is None else ("yes" if r.rules_kept else "no")
        lines.append(
            f"{n} | {uk} | {r.instrument} | {'long' if r.side == 'buy' else 'short'} | "
            f"{r.entry_model or '—'} | "
            f"{r.session_label or '—'} | {fmt_value('total_r', r.r)} | {fmt_value('net_pnl', r.pnl)} | "
            f"{r.outcome or '—'} | {kept}"
        )
    if len(rows) > COPY_TRADE_LINES:
        lines.append(
            f"… and {len(rows) - COPY_TRADE_LINES} more. "
            "Use Export for AI for every trade and the screenshots."
        )
    lines += [
        "",
        "Please review this: what's working, where the edge is and isn't (with n for every claim),",
        "how the backtest compares with the ideal profile, and the 3 rule changes most likely to keep",
        "the winners and cut the losers.",
    ]
    return {"text": "\n".join(lines), "trades": len(rows)}


CSV_COLUMNS = (
    "id",
    "fx_replay_id",
    "strategy",
    "logged_by",
    "kind",
    "instrument",
    "direction",
    "opened_uk",
    "opened_at_utc",
    "closed_at_utc",
    "weekday",
    "session",
    "duration_seconds",
    "entry_price",
    "stop_price",
    "target_price",
    "exit_price",
    "stop_distance",
    "target_distance",
    "target_r",
    "r",
    "pnl",
    "outcome",
    "max_favourable_r",
    "max_adverse_r",
    "entry_model",
    "tags",
    "all_rules_kept",
    "completed",
    "news",
    "news_events",
    "notes",
)


FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value):
    """Spreadsheet-safe cell: free text that starts like a formula gets a leading apostrophe.

    Numbers stay numbers (a −1.0 R is data, not a formula); only strings are neutralised.
    """
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value


def stream_csv(db: Session, user: User, q: AnalyticsQuery) -> Iterator[str]:
    """Rows are built now (the database session closes before the response streams)."""
    rows = select_rows(db, user, q)
    rows.sort(key=lambda r: (r.opened_at, r.id))
    trades = _load_trades(db, [r.id for r in rows])
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.owner_id for r in rows})))}
    strategy_ids = {r.strategy_id for r in rows}
    strategies = {s.id: s for s in db.scalars(select(Strategy).where(Strategy.id.in_(strategy_ids)))}
    records = []
    for n, row in enumerate(rows, 1):
        t = trades.get(row.id)
        if not t:
            continue
        owner = users[t.owner_id].display_name if t.owner_id in users else ""
        rec = trade_record(t, row, n, owner, strategies[t.strategy_id], [])
        rec["tags"] = "; ".join(rec["tags"])
        rec["news_events"] = "; ".join(
            str(e.get("name", "")) for e in rec["news_events"] if isinstance(e, dict)
        )
        rec["notes"] = rec["notes"].replace("\r", " ").replace("\n", " ")
        records.append([csv_cell(rec.get(c)) for c in CSV_COLUMNS])

    def generate() -> Iterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(CSV_COLUMNS)
        yield "\ufeff" + buf.getvalue()  # BOM so Excel reads UTF-8
        for i in range(0, len(records), 200):
            buf.seek(0)
            buf.truncate()
            writer.writerows(records[i : i + 200])
            yield buf.getvalue()

    return generate()
