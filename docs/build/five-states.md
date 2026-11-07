# Five states on every route (F15)

Prompt 5, step 0 and step 6 (accessibility half), 7 Nov 2026, branch `build/05-hub-calendar-launch`. Every route in `frontend/src/App.tsx` was checked in code for the five states the review kit asks for: **loading** (a skeleton in the shape of the content, never a spinner), **empty** (an `EmptyState` with one next step), **error** (an `ErrorState` with a working `refetch`, or `RefreshFailed` when stale data is still on screen), **read-only** (a `ReadOnlyBanner` or disabled affordances when the record belongs to someone else) and **offline** (cached data stays with the shell's `OfflineBanner`; a cold load with nothing cached shows an offline empty state, not an endless skeleton).

Words: **OK** = already there · **Fixed** = added or corrected in this pass · **Gap** = still missing, with a note · **n/a** = the state has no meaning on that screen (a static page, or one that only ever shows the signed-in person's own data).

## The pattern

- Loading: `Skeleton`, `SkeletonText`, `SkeletonCard`, `ChartSkeleton` (`components/ui/Skeleton.tsx`, `components/charts/Chart.tsx`). The lazy route boundary shows three `SkeletonCard`s.
- Empty: `EmptyState` with a line illustration from `components/ui/Illustrations.tsx` and one action.
- Error: `ErrorState` with `onRetry={() => q.refetch()}`; `RefreshFailed` above stale data (`q.isError && q.data`).
- Read-only: `ReadOnlyBanner` plus `readOnly` / `disabled` controls, keyed off `can_edit` from the API.
- Offline, cold: `offlinePending(q)` (`lib/offline.ts`) is true when a query has nothing to show and is either paused by TanStack Query or failed while `navigator.onLine` is false; render `OfflineState` (`components/ui/States.tsx`) instead of the skeleton. The query refetches on its own when the connection returns (`refetchOnReconnect`). The Hub cards use the older `queryState()` in `lib/hub.ts`, which reads the same way.
- Offline, warm: the shell shows `OfflineBanner`; data already in the query cache stays on screen; the Hub stamps stale figures (`StaleFigures`).

## Route × state

| Route | Loading | Empty | Error | Read-only | Offline |
|---|---|---|---|---|---|
| `/` Hub | OK (per card) | OK (quiet week, no news, no pins, start a streak) | OK (per card, refetch) | n/a | OK (`queryState` per card; checklist hides) · **Fixed**: the week-ahead half of the news pair |
| `/journal` | OK | OK (New strategy, per scope) | OK | n/a (list; owner chips) | **Fixed** (`OfflineState`) |
| `/journal/trash` | OK | OK (plain card copy) | OK | n/a (owner chips; server enforces restore) | **Fixed** |
| `/journal/analytics` | OK (`AnalyticsSkeleton`) | OK (no trades match + Clear filters) | OK | n/a | OK |
| `/journal/strategies/:id` | OK | OK (trade list empty copy, profile copy) | OK · **Fixed**: the Missed card's `ErrorState` had no retry | OK (`ReadOnlyBanner`, hidden actions) | **Fixed** at page level · Gap (small): the Sessions, Trades, Missed and Profile sub-cards fall to `ErrorState` offline; its copy now says "You're offline: this loads when you're back online" |
| `/journal/strategies/:id?tab=backtest` | OK | OK (locked card / Import CSV) | OK | OK | as above |
| `/journal/strategies/3?tab=analytics` (+ `src=ideal`, `src=compare`) | OK | OK | OK | n/a | OK |
| `/journal/strategies/:id/trades/:tradeId` | OK | n/a | OK | OK (`ReadOnlyBanner`) | **Fixed** |
| `/journal/sessions/:sid/annotate` | OK | **Fixed**: "Nothing to annotate" was an `ErrorState` whose Try again navigated away; now an `EmptyState` with Back to the strategy | **Fixed**: retry now refetches (it navigated back) | OK (`canEdit` disables every field) | **Fixed** |
| `/journal/sessions/:sid/match` | OK | OK (unmatched tray copy) | **Fixed**: `ErrorState` had no retry | OK (`canEdit`) | **Fixed** |
| `/news`, `/news?view=week` | OK | OK | OK (`ErrorState` / `RefreshFailed`) | n/a | OK · **Fixed**: the Next-up countdown card |
| `/news/week` | OK | OK | OK + `RefreshFailed` | n/a | **Fixed** |
| `/news/events/:id` | OK | OK (guide, history, reactions) | OK | n/a | **Fixed** |
| `/markets` | OK | OK (pin suggestions) | OK + `RefreshFailed` | n/a | OK |
| `/markets/:symbol` | OK | OK (unavailable instrument) | OK (quote and news sections) | n/a | **Fixed** |
| `/settings/alerts` | OK | OK (no devices) | OK (config, devices, prefs) | n/a | **Fixed** (all three cards) |
| `/calendar` (+ `view=day`, `view=month`) | OK | OK | OK + `RefreshFailed` | OK (`ReadOnlyBanner` in the task drawer, `readOnly` fields) | OK (last tasks stay; drag and edit paused) |
| `/tags`, `/admin/tags` | OK | OK | OK | OK (`ReadOnlyBanner` for members) | **Fixed** |
| `/settings` | OK (per card) | OK (passkeys, API key) | OK (per card) | n/a | **Fixed** (passkeys, keys, news prefs, usage) |
| `/more` | n/a (static links) | n/a | n/a | n/a | OK (shell banner) |
| `/admin/users` | OK | OK (Just you so far) | OK | OK (`RequireAdmin`; members never see it) | **Fixed** |
| `/dev/components` | gallery | gallery · **Fixed**: shows `OfflineState` | gallery | gallery | gallery |
| `/login` | n/a (form) | n/a | OK (inline field error, lockout screen) | n/a | **Fixed**: `AuthFrame` shows `OfflineBanner` (the auth screens sit outside the shell) |
| `/invite/:token` | OK (`SkeletonText` while the invite is checked) | n/a | OK (invalid or used invite copy) | OK (email pinned when the invite names one) | **Fixed** (frame banner) |
| `/reset/:token` | n/a (form) | n/a | OK (inline error) | n/a | **Fixed** (frame banner) |
| `*` (404) | n/a | n/a | **Fixed**: copy said "Not built yet"; now explains there's no page at that address, with a link to the Hub | n/a | n/a |

Totals: 26 rows (the 31 routes in `e2e/routes.spec.ts`, with the query-string variants grouped) × 5 states = 130 cells. **OK 73 · Fixed 25 · n/a 32**, plus **1 gap** noted inside a Fixed cell (strategy sub-cards offline). A cell with both an OK and a Fixed note counts as Fixed; the gallery's five cells count as n/a.

## The one gap left

- **Strategy page sub-cards offline.** The page-level strategy query shows `OfflineState`, but when the strategy itself is cached and only its sessions, trades, missed or profile queries fail offline, those cards show `ErrorState` with the offline copy and a Try again button. Honest and usable, but not the illustrated offline state. Making each sub-card use `offlinePending` is four small edits; left for the next pass because the trade list is virtualised and its empty copy is shared with the live state.

## Checked as part of the same pass

- Every `ErrorState` has a working retry: `onRetry` always calls the query's `refetch` (three fixed: Annotate's two, Matcher's, StrategyPage's Missed card).
- Every `ErrorState` and `EmptyState` renders inside a `.card` when it is the whole page body, so it sits on `surface-1` and the illustration's `text-muted` keeps its contrast.
- `e2e/offline.spec.ts` now covers the cold offline load of `/journal` (the shell's banner, the offline state, no skeleton left) alongside the Hub's warm offline reload.
