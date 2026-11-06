"""Reconcile line (F16): does what the app holds for an imported session add up to the CSV's own figures?

At import we store the CSV's totals in the session's import_report (`csv_totals`, `kept_totals`). For sessions
imported before that existed, the kept totals are rebuilt from each trade's raw row (FX Replay's rPnL).
"""

from ...models import JournalSession, Trade

TOLERANCE = 0.01  # dollars


def csv_totals(rows) -> dict:
    """FX Replay's own figures for the whole file: trade count, Σ rPnL, and the balance change it reports."""
    pnl = round(sum(r.pnl for r in rows), 2)
    out: dict = {"trades": len(rows), "rpnl_sum": pnl, "balance_start": None, "balance_end": None}
    try:
        ordered = sorted(rows, key=lambda r: (r.closed_at or r.opened_at, r.fx_id))
        start = float(ordered[0].raw.get("initialBalance") or "nan")
        end = float(ordered[-1].raw.get("currentRealizedBalance") or "nan")
        if start == start and end == end:  # not NaN
            out["balance_start"], out["balance_end"] = start, end
    except (IndexError, ValueError, AttributeError):
        pass
    return out


def _raw_pnl(t: Trade) -> float | None:
    try:
        return float((t.raw_row or {}).get("rPnL", "").replace(",", ""))
    except ValueError:
        return None


def reconcile_session(session: JournalSession, all_trades: list[Trade]) -> dict:
    """Compare the session's live trades with what the import kept from the CSV.

    `all_trades` are every trade the session created, deleted ones included.
    """
    report = session.import_report or {}
    live = [t for t in all_trades if t.deleted_at is None]
    app = {"trades": len(live), "pnl": round(sum(t.pnl or 0.0 for t in live), 2)}
    kept = report.get("kept_totals")
    if not kept:
        raw = [_raw_pnl(t) for t in all_trades]
        kept = {"trades": len(all_trades), "rpnl_sum": round(sum(p for p in raw if p is not None), 2)}
    csv = report.get("csv_totals")
    diff_trades = app["trades"] - kept["trades"]
    diff_pnl = round(app["pnl"] - kept["rpnl_sum"], 2)
    ok = diff_trades == 0 and abs(diff_pnl) <= TOLERANCE
    notes: list[str] = []
    if csv:
        balance_ok = None
        if csv.get("balance_start") is not None and csv.get("balance_end") is not None:
            balance_ok = abs((csv["balance_end"] - csv["balance_start"]) - csv["rpnl_sum"]) <= TOLERANCE
            if not balance_ok:
                notes.append("FX Replay's balance change doesn't equal the sum of rPnL in the file.")
        left_out = csv["trades"] - kept["trades"]
        if left_out:
            parts = []
            if report.get("duplicates"):
                parts.append(f"{len(report['duplicates'])} already imported")
            if report.get("skipped_not_winners"):
                parts.append(f"{report['skipped_not_winners']} not winners (Ideal keeps winners only)")
            notes.append(f"{left_out} of the file's {csv['trades']} rows left out: " + ", ".join(parts) + ".")
    else:
        balance_ok = None
    if diff_trades < 0:
        notes.append(f"{-diff_trades} imported trade{'s' if diff_trades != -1 else ''} since deleted.")
    return {
        "session_id": session.id,
        "kind": session.kind,
        "filename": session.source_filename,
        "csv": csv,
        "kept": kept,
        "app": app,
        "diff_trades": diff_trades,
        "diff_pnl": diff_pnl,
        "balance_ok": balance_ok,
        "ok": ok,
        "notes": notes,
    }
