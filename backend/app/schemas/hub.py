"""GET /api/hub: what the Hub's engagement cards need in one call (Foundations §1, Engaging touches, F15)."""

from pydantic import BaseModel


class StreakDayOut(BaseModel):
    date: str  # UK calendar date, YYYY-MM-DD
    active: bool


class StreakOut(BaseModel):
    """Showing up, not winning: a day is active when the user logged, imported, reviewed or annotated."""

    current_days: int
    best_days: int
    active_today: bool
    last_active_date: str | None
    days: list[StreakDayOut]  # the last 28 UK dates, oldest first


class PersonalBestOut(BaseModel):
    key: str  # best_month_r | longest_rule_run
    label: str
    value: float
    value_text: str
    detail: str | None  # "March 2026", "to 14 Mar 2026"
    achieved_at: str
    is_new: bool  # achieved within the last 7 days


class ChecklistOut(BaseModel):
    twelve_data_key: bool
    strategy_created: bool
    first_csv_imported: bool
    alerts_enabled: bool
    all_done_server: bool  # the fifth item (install to the home screen) is detected on the client


class WeekRecapOut(BaseModel):
    show: bool  # Sunday 18:00 UK → Monday 23:59 UK
    week_start: str  # Monday, YYYY-MM-DD (UK)
    week_end: str  # Sunday
    sessions: int
    trades: int
    total_r: float | None
    total_pnl: float | None = None  # the $ headline (amends, Nov 2026); null when no trade has a P&L
    win_rate: float | None
    rules_kept_rate: float | None
    best_day: str | None  # weekday name of the best day by total R, e.g. "Wednesday"
    best_day_r: float | None


class HubOut(BaseModel):
    welcome_back: bool
    server_now: str
    streak: StreakOut
    personal_bests: list[PersonalBestOut]
    checklist: ChecklistOut
    week_recap: WeekRecapOut
