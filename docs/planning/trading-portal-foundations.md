# Trading Portal Foundations

Nov 3, 2026 · @Jamie

## Introduction

Following on from the Replay Journal, this will be a multi-tool web app hosted on fly.io. The goal is to create a practical tool to support and collate data throughout my and my mates’ trading journey. Very open to suggestions and ideas to enhance the practicality of this tool.

We will add to this as we develop the plan.

## Look and feel

The Trading Portal replaces the earlier “Floor” direction with a darker, sharper look: a tailored, high-resolution tool built for long sessions of reading charts and numbers. It takes the structure and restraint of three reference dashboards, not their decoration. The Hub, Replay Journal and News Room all use the same system, so they feel like one product.

### Principles

- **An instrument, not a showcase:** every element shows data or does something. No decorative 3D shapes or stock imagery on working screens.
- **High resolution:** crisp 1px borders, sharp type, fixed-width numbers, and charts with real axes and exact values on hover. It should look precise on a Retina or 4K screen.
- **Calm density:** plenty of information per screen, held together by a strict grid and one card pattern, so it reads as organised rather than busy.
- **Colour means something:** colour is reserved for state (win/loss, news impact, owner, live/stale), never for decoration.
- **One system:** the same cards, controls, charts and motion in every tool.

### Colour

Hex values are starting points to refine during the build.

- **Base:** a deep navy, near-black background (around #0B0F1A), with two raised surface levels for cards and inner panels (around #121829 and #182036), separated by thin, faint borders rather than heavy shadows.
- **One brand accent:** electric blue #2F7BFF for active states, primary buttons, selected toggles and focus rings. The blue-to-violet gradient (#2F7BFF → #8B5CF6) is kept for brand marks and hero moments only. News Room's own colour is violet → purple (#8B5CF6 → #C45BFF). A light cyan (around #5CC8FF) is the second data series, so it never reads as the brand. This replaces the earlier teal accent.
- **Reserved meanings:** green = win / profit / positive R; red = loss; grey = breakeven. News impact: red high, orange medium, yellow low. These colours are used for nothing else.
- **Owner colours:** a fixed set of distinct hues for calendar owners and “logged by” tags, shown as small dots and chips.
- **Text:** near-white for primary text; secondary text must still be clearly readable. The faint grey small text in the references is a weakness to avoid.
- **Dark mode first:** dark is the default and main target; a light mode can come later.

### Typography

- One clean sans-serif for the interface (e.g. Inter), with fixed-width (tabular) figures for all prices, P&L and stats, so columns line up and live numbers don’t jitter.
- An optional monospace (e.g. JetBrains Mono) for symbols, timestamps and raw trade data.
- A clear scale: large hero numbers for the headline figure on a card, medium-weight card titles, small sentence-case labels.
- Brand wordmarks only: Archivo Black italic (weight 900). App names use a condensed width (about 78%); TRADING PORTAL uses standard width. Never used for interface text.

### Brand marks

Four marks share one system: heavy italic Archivo, rounded capsule outlines, the blue-to-violet gradient and a halftone sparkle cut through the letters. Replay Journal keeps its original twin-capsule design, recoloured from yellow/orange to blue/violet.

&#91;image: Trading Portal logo\]

&#91;image: T tile favicon and app icon\]

&#91;image: Replay Journal logo\]

&#91;image: News Room logo\]

| Mark | Where it appears | Files (transparent PNG) |
| --- | --- | --- |
| Trading Portal logo | Desktop top bar, login screen, link previews | tradingportal-logo.png (2041 × 320) |
| T tile (favicon / app icon) | Browser tab, phone home screen, mobile top bar | favicon.ico, favicon-16/32/192/512.png, apple-touch-icon-180.png |
| Replay Journal logo | Homepage launch island, Replay Journal header | replayjournal-logo.png (1932 × 350) |
| News Room logo | Homepage launch island, News Room header | newsroom-logo.png (1472 × 350) |

- Dark backgrounds only: the white capsule and letters disappear on light surfaces. A light-mode version comes with light mode.
- On phones, the top bar shows the T tile alone; the full Trading Portal logo needs at least 240px of width.
- The 16px and 32px favicons drop the sparkle so they stay sharp in a browser tab.
- No recolouring, stretching, outer glows or drop shadows. Leave clear space around each mark at least as wide as its capsule stroke.
- Page head tags:

```html
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon-180.png">
<link rel="manifest" href="/site.webmanifest"> <!-- lists favicon-192 and favicon-512 -->
```

### Layout and components

- **App shell:** a left sidebar (collapsible to icons) listing the tools with status dots, and a top bar with search, UK clock and session status, notifications and user avatar.
- **Grid of cards:** rounded cards (about 16px radius outside, 10px for inner panels) on a 12-column grid with consistent padding.
- **Card pattern:** title and optional subtitle top-left, controls top-right (pill toggles, period selector), content below. Every card in every tool follows it.
- **Hero greeting card:** one atmospheric card at the top of the Hub with the greeting, date and session status, on a subtle market-themed image or gradient. This is the only place atmosphere is allowed.
- **KPI strip:** a row of 3–5 stat tiles for headline numbers (strategy cards, Analytics).
- **Ticker cards:** instrument, price, % change and a sparkline, used for the live market watchlist.
- **Pill toggles and segmented controls:** Ideal / Backtest / Compare, Day / Week / Month, date ranges.
- **Chips with coloured dots:** news impact, owners, tags, sessions.
- **Ring and arc gauges, used sparingly:** win rate, progress to 6 months of ideal-trade coverage, daily data credits used, countdown to the next event.
- **Launch islands:** larger cards with an icon, subtitle and live mini-stat; on hover a slight lift and an accent glow.

### Charts

- Thin lines, faint gridlines, labelled axes and a hover crosshair showing exact values.
- Equity curve (in R) as a line with a soft gradient fill underneath.
- Bars for distributions and breakdowns (by session, entry model, day of week); a heatmap for entry times.
- No more than two or three series on one chart. Win/loss bars and markers use the reserved colours.
- Sparklines on ticker cards and strategy cards.

### Motion

Quick, purposeful motion that always serves the data. Planned in full in the next section, Motion, loading and engagement.

### Screen sizes

Desktop is the main workstation, but every device gets a professionally designed layout. Planned in full in Devices and responsiveness.

### What to avoid

- Frosted glass and blur on every card (hero card only).
- Purple/neon gradients and 3D objects on working screens.
- Faint, low-contrast text.
- Green or red used decoratively.
- Overlapping multi-line “neon” charts.

### References

- **Home control (smart home dashboard):** the base. Card structure, title-left/controls-right pattern, pill toggles, status dots, ring gauge.
- **Vision UI dashboard (Figma template):** the “Welcome back” hero card, the KPI strip, the gradient-filled area chart and arc gauges.
- **Cryptocurrency dashboard (Figma template):** the row of ticker cards with sparklines.

## Motion, loading and engagement

Motion is what turns the portal from a set of static screens into a tool that feels alive. Every animation does a job: it shows what changed, where you came from, or that the tool is working. The Look and feel principles still apply: an instrument, not a showcase.

### Motion principles

- **Purposeful:** every animation explains a change (new data, navigation, a state change). Nothing moves just to move.
- **Fast:** most motion lasts 150–300ms and never blocks a click. Longer animations only cover real loading.
- **One motion language:** shared durations and easing used everywhere: *quick* 150ms (hovers, presses), *standard* 250ms (panels, tabs, fades), *emphasis* 400–600ms (charts drawing in, unlocks). Ease-out when things enter, ease-in when they leave, a gentle spring for toggles and dragged items.
- **Smooth:** only position, scale and opacity are animated, so it holds 60fps; animations off-screen or in a hidden tab pause.
- **Respectful:** follows the device’s reduced-motion setting, plus a Motion setting in the app (Full / Reduced / Off). In Reduced, movement becomes simple fades.

### Fades and page transitions

- **Page to page:** the sidebar and top bar stay still while the content area cross-fades with a slight 8–12px rise, so moving between tools feels like one app rather than separate pages.
- **Shared-element transitions:** the thing you click grows into what it opens. A strategy card expands into the strategy page, a trade row into the trade detail, a ticker card into the instrument view, a calendar event into its detail. Going back reverses it.
- **Staggered entrance:** on first load of a screen, cards fade and rise in sequence (30–50ms apart). Only on first load, not every revisit.
- **Tabs and toggles:** the active pill slides under the selected option (Ideal / Backtest / Compare), the content cross-fades, and charts morph to the new data rather than redrawing.
- **Drawers and modals:** the background dims and the panel slides in from the right. The trade entry form opens as a side drawer so the trade list stays visible behind it.

### Loading screens and states

- **Portal intro:** after login, a short branded intro (about 1s) where the logo mark draws in as a price line or candlestick, then dissolves into the Hub. Plays once per day; returning later goes straight in.
- **Launch islands (see 1.3):** Replay Journal plays a “rewind” (candles draw in right to left as a playhead sweeps back); News Room plays a radar pulse or ticker-tape sweep. Each has a short minimum (\~600ms) so it never flickers, loops smoothly if loading takes longer, and exits as soon as the tool is ready.
- **Skeleton screens:** inside the tools, cards show placeholders in the shape of their content (a chart outline, table rows) with a faint shimmer, then the real content fades in. No spinners in the main content area.
- **Step-by-step progress for long jobs:** a CSV import shows its stages (Reading file → Matching trades → Calculating stats → Done) with a progress bar and counts, ending with “10 trades imported”. Screenshot uploads show each thumbnail filling as it uploads.
- **Instant actions:** marking a task done, adding a tag or moving a task happens on screen immediately, with a quiet undo toast; it quietly rolls back only if the save fails.
- **Empty states:** small line illustrations in the portal’s style with one clear next step, e.g. “No ideal trades yet – log your first winner.”
- **Stale and paused data:** out-of-date figures fade slightly with a “last updated” badge; the “daily limit reached” banner slides in rather than appearing abruptly.

### Live data in motion

- **Price ticks:** changed digits roll like an odometer, and the price briefly flashes green or red, fading over about 600ms.
- **Sparklines** extend smoothly as new points arrive instead of redrawing.
- **Live indicator:** a softly pulsing dot on any card fed by live data; it turns grey and stops when updates are paused.
- **News countdown:** the ring gauge for the next high-impact event depletes as the time runs down, turns orange then red in the final 15 minutes with a gentle pulse, and when the figure is released the actual value flips in, coloured by surprise.
- **Trading-day timeline (see 3.2):** a “now” line moves across the day, the current session is softly highlighted, and news windows shade in as they approach.
- **Meters** (credits used, coverage, progress) fill smoothly rather than jumping.

### Charts that animate

- **First view:** lines draw in left to right (the equity curve over about 600ms), bars grow up from the baseline in sequence, gauges sweep to their value, and headline numbers count up.
- **Filter changes:** charts morph between states (bars resize, lines bend to the new values) so you can see what changed, instead of flickering to a new chart.
- **Hover:** the crosshair snaps to the nearest point, the tooltip fades in, and the hovered series stays bright while others dim.
- **Heatmaps:** cells fade in by intensity, so the busiest entry times appear first.

### Micro-interactions

- **Buttons:** a slight press-down on click and an accent glow on hover.
- **Toggles and checkboxes:** toggles slide with a small spring; ticks draw themselves in.
- **Cards:** lift about 2px and the border brightens on hover.
- **Drag and drop:** calendar tasks and screenshots lift with a shadow when picked up, the drop target lights up, and the item settles into place.
- **Pasting a screenshot:** the thumbnail drops into the trade’s gallery with a quick scale-in.
- **Copy and export:** the icon morphs into a tick when done.
- **Toasts:** slide up from the bottom corner, then fade out; undo where it makes sense.
- **Command palette:** Cmd+K opens a quick search with a fade-and-scale, to jump to any strategy, trade, instrument or action (e.g. “New ideal trade”).

### Engaging touches

These reward process and discipline, never profit alone, so the portal encourages good habits rather than overtrading.

- **Time-of-day ambience:** the greeting card’s gradient shifts through dawn, day, dusk and night, and subtly reflects the active session (Asia, London, New York). Weekends get a calmer, dimmer “markets closed” state.
- **Backtest unlock:** when a strategy reaches 6 months of ideal-trade coverage, the lock on the Backtest tab opens with a short animation, the tab lights up and a toast confirms it.
- **Session recap:** after a CSV import, a recap card animates in: trades, win rate, total R, rules followed, how it compares with the strategy profile, and the best trade’s screenshot.
- **Week behind / week ahead:** on Sunday evening, a recap of the past week sits alongside the Week ahead view (see 3.4).
- **Process streaks:** a quiet streak for consistent work (e.g. days with a session logged or a review done), shown on the Hub. Rewards showing up, not winning.
- **Personal bests:** a small badge for milestones such as best month in R or longest run of rule-following trades. One restrained celebration for big milestones; no confetti on individual winning trades.
- **Mates (later):** presence dots showing who’s online and a light activity feed (“Sam logged 8 trades on Strategy X”).
- **Sound (optional, off by default):** a soft chime for news alerts only.

### What to avoid

- Animations that delay reading the data, or loading screens longer than the real load.
- Looping or attention-grabbing motion at the edge of the screen while you’re working.
- Celebrating profit or individual wins in a way that nudges towards overtrading.
- Different timings and styles in different tools.

### Build notes

- Define the durations and easing curves once as shared design tokens, used by every tool.
- Use CSS transitions and the browser’s View Transitions API for page fades and shared-element transitions.
- Use a small animation library (e.g. Motion, or GSAP) for number rolls, chart morphs and the launch sequences; SVG or Lottie for the intro, loaders and empty-state illustrations.
- Choose a chart library with built-in transitions (e.g. Apache ECharts) and test it against large backtests.
- Build order: (1) motion tokens, skeletons, fades and micro-interactions; (2) live data motion and chart animations; (3) launch transitions and the portal intro; (4) engaging touches.

## Devices and responsiveness

The portal will mostly be used on an iMac, desktop monitors and laptops, but it will also be used on phones. Every device gets a properly designed layout, not a squashed version of the desktop. The data, look and feel are the same everywhere; the layout, navigation and interactions are tailored to each screen and to how it’s used.

### What each device is for

| Device | Screen width | Main use | Priority |
| --- | --- | --- | --- |
| iMac / large monitor | 1440px and up (to 5K) | Deep backtesting, analytics, multi-panel work | Primary |
| Laptop | 1024–1439px | Same as desktop, slightly more compact | Primary |
| Tablet (iPad) | 600–1023px | Reviewing trades and analytics, planning the calendar | Secondary |
| Phone | under 600px | Today’s news and countdowns, prices, tasks, glancing at stats, quick ideal-trade logging, alerts | Companion, fully designed |

### Layout and breakpoints

- **Five sizes:** phone (under 600px), tablet (600–1023px), laptop (1024–1439px), desktop (1440–1919px) and large desktop / iMac (1920px and up). Each key screen is designed at phone, tablet and desktop size before it’s built.
- **Grid:** 12 columns on desktop and laptop, 8 on tablet, 4 on phone, with 16px side margins on phone.
- **Using big screens properly:** on an iMac the extra width shows extra panels (e.g. Analytics with filters, chart and trade list side by side) rather than stretching cards. Reading content keeps a comfortable maximum width.
- **Fluid sizing:** text and spacing scale smoothly between sizes rather than jumping at breakpoints.
- **Self-adjusting cards:** each card adapts to its own width, so the same card works in a dashboard grid, a side panel or full width on a phone.

### Navigation by device

- **Desktop:** full left sidebar and top bar, keyboard shortcuts and the Cmd+K quick search.
- **Laptop:** the sidebar collapses to icons on smaller widths, expandable on hover or click.
- **Tablet:** a slim icon rail; filters open in a side drawer.
- **Phone:** a bottom tab bar (Hub, Journal, News, Calendar, More) within thumb reach, a simple top bar with the page title and one action, a floating “+” button for quick logging, and filters and options in bottom sheets.

### Key screens on mobile

- **Hub:** a compact greeting; the news card collapsed to the headline plus top 3 events (see 1.6); the launch islands as two side-by-side tiles; the calendar as a day or 3-day agenda list instead of a week grid; the watchlist as a row of ticker cards you swipe through.
- **Replay Journal:** strategy cards in a single column; Ideal / Backtest / Analytics as a segmented control at the top; trades as cards rather than table rows; trade detail full screen with a swipeable, pinch-to-zoom screenshot gallery.
- **Quick log on the phone:** a one-handed ideal-trade form with the strategy’s defaults filled in, screenshots added from the camera roll or share sheet, and the right keyboard for each field (numbers for prices). CSV import is designed for desktop but still works from the Files app.
- **Analytics:** headline stats as a 2×2 grid of tiles; one full-width chart per row; filters in a bottom sheet; wide tables either scroll sideways with the first column pinned or switch to a card view.
- **News Room:** the calendar as a list grouped by time; the trading-day timeline scrolls sideways with “now” centred; the next-event countdown pinned at the top; event detail full screen.

### Touch, mouse and keyboard

- **Tap targets** at least 44px, with enough spacing to avoid mis-taps.
- **Nothing relies on hover:** every hover effect has a touch equivalent. On charts, press and hold for the crosshair and tap a point to pin its tooltip.
- **Gestures as shortcuts, never the only way:** swipe between tabs, pull to refresh, swipe a task to complete it, always with a visible button that does the same.
- **Keyboard on desktop:** full keyboard navigation, shortcuts for common actions and clear focus rings.
- **Screenshots:** paste or drag and drop on desktop; camera roll, files or share sheet on mobile.
- **Native pickers** for dates and times on mobile.

### High-resolution screens

- Icons as SVG and charts drawn at the screen’s full pixel density, so everything stays sharp on Retina and 5K displays; 1px lines stay crisp.
- Trade screenshots load as light thumbnails first and open at full resolution when zoomed.
- Images are sized for each device, so phones aren’t downloading desktop-sized files.

### Accessibility

- **Target:** WCAG 2.2 AA, the recognised standard for accessible web apps. Text contrast at least 4.5:1, interface elements at least 3:1.
- **Colour is never the only signal:** wins and losses also carry a +/− sign or icon; news impact also shows a label (High / Med / Low). This also covers colour-blind users, especially for green/red; a colour-blind-friendly palette option can be added in settings.
- **Screen readers:** proper labels on every control, and each chart has a short text summary and an underlying data table.
- **Text size:** layouts hold up with text enlarged to 200% and respect the phone’s own text-size setting.
- **Motion:** follows the reduced-motion setting (see Motion, loading and engagement).

### On the phone like an app

- **Installable to the home screen** as a Progressive Web App: full screen, its own icon, and a launch screen that matches the portal intro, with no App Store needed.
- **Push notifications** for news alerts on iPhone and Android once installed to the home screen.
- **Fits the phone properly:** content stays clear of the notch, Dynamic Island and home bar, and the status bar matches the dark theme.
- **Light offline mode:** the last-loaded Hub, prices and today’s events stay viewable without signal, clearly marked as offline.

### Speed on mobile

- Each screen loads only what it needs, with charts and heavier tools loaded on demand, so it’s quick on 4G.
- Live prices refresh less often on mobile and pause when the app is in the background, which also saves Twelve Data credits.
- Long trade lists load as you scroll rather than all at once.

### Testing and sign-off

- **Test devices:** iMac, MacBook, iPad, a small iPhone and a large iPhone, in Safari and Chrome (plus Firefox on desktop, and an Android phone if any of the mates use one).
- **Definition of done:** a feature is only finished once it has been checked on desktop, tablet and phone.
- **Automated checks:** screenshot tests at each screen size (e.g. with Playwright) catch layouts that break when something changes.

## 1. Homepage: the Trading Hub

The homepage is the first screen after login and the launch point for everything else. It answers three questions in order: what’s happening in the markets today, which tool do I want to open, and what’s coming up this week. It follows the Look and feel section above, as do the Replay Journal and News Room, so the whole portal feels like one product.

### 1.1 Personal greeting header

- A time-of-day greeting: “Good morning, Jamie” before 12:00, “Good afternoon” until 17:00, “Good evening” after that. “Welcome back, Jamie” on the first login after a gap of a day or more.
- The full date underneath, e.g. “Today is Friday 17th October”, in UK time with a small live clock.
- An optional status line, e.g. “London session opens in 1h 20m” or “Markets closed – weekend”.

### 1.2 Today’s news overview

- A summary card of the day’s scheduled economic events, pulled from the same feed that powers News Room.
- Each event shows the time (UK), currency, event name, impact level (high/medium/low as coloured markers), and forecast vs previous figures.
- Filtered by default to what we trade: FX major currencies, USD for gold and BTC, and EUR/DE events for GER40.
- A one-line headline at the top, e.g. “3 high-impact events today – USD CPI at 13:30”, so the key risk is clear at a glance.
- Empty state on quiet days: “No high-impact news today.”
- Tapping the card opens the full News Room.

### 1.3 App launch islands

- Two large, equal-weight cards side by side (stacked on mobile): **ReplayJournal** and **News Room**.
- Each card has its own icon, a short subtitle and a live mini-stat, e.g. “Last session: 10 trades · Strategy X” on ReplayJournal and “Next event: USD CPI in 2h” on News Room.
- Hover/press effects: a slight lift, a glow in the app’s accent colour, and an animated icon.
- On click, a custom transition plays before the tool loads: ReplayJournal could use a “rewind” sweep or candlesticks drawing in; News Room a ticker-tape or radar-pulse effect.
- The transition lasts about 1–1.5s and doubles as the real loading screen, so it never feels like a fake delay.

### 1.4 Team calendar (Teamup-style)

- Sits below the app islands. Defaults to week view, with day and month views available.
- Add a task by tapping a day or using a “+ New task” button. Fields: title; date and time (or all-day); owner (from a list of users, shown as a coloured tag); repeat (none, daily, weekdays, weekly, monthly, custom); description/notes; optional category (e.g. Backtesting, Review, Admin).
- Each owner gets their own colour, with filter chips to show or hide owners.
- Tasks can be marked done, edited, or dragged to another day. Recurring tasks ask whether a change applies to this occurrence or the whole series.
- Optionally, high-impact news events show as faint markers on the calendar, so tasks aren’t planned on top of events like NFP.
- Owners mean the app needs simple multi-user support: built for solo use first, but structured so mates can be added later.

### 1.5 Live market data

The last section of the homepage is a live market panel, using the same approach as the Platinum Edge tool: a Twelve Data API key on the free plan, with a daily allowance of 800 credits.

- **Instrument search:** a search bar with autocomplete by symbol or name (e.g. EUR/USD, XAUUSD, BTC/USD, GER40), so any instrument can be looked up on demand.
- **Price card per instrument:** live price, change and % change on the day, day high/low, a small intraday sparkline, and a “last updated” time.
- **Pinned watchlist:** each user pins the instruments they follow (e.g. FX majors, gold, BTC, GER40) and can add or remove them.
- **API key kept server-side:** the key lives as a fly.io secret and every request goes through the app’s backend, never from the browser.
- **Shared cache:** prices are cached on the server for a short window, so if several of us view the same instrument it costs one call, not one each.
- **Credit budget:** most providers charge one credit per symbol per request, so refresh rate matters. As a guide, 5 pinned instruments refreshed every 10 minutes over 12 hours uses about 360 credits, leaving plenty for searches. Refreshing pauses when the tab isn’t visible.
- **Rate limits:** Twelve Data’s free plan also caps requests at 8 per minute, so the backend queues requests rather than firing them all at once.
- **Usage meter:** a small indicator showing credits used today, with a clear fallback message when the allowance runs out, e.g. “Live data paused – daily limit reached”, showing the last known prices instead.
- **Later option:** move to a paid plan or websocket streaming if the free allowance proves too tight once mates are using it.

### 1.6 Layout order

Top to bottom: greeting → today’s news → app islands → calendar → live market data. On mobile everything stacks in the same order, with the news card collapsed to the headline plus the top 3 events.

## 2. Replay Journal

The Replay Journal will be an enhanced, cleaned-up and more practical version of the current build, organised around strategies. It keeps what already works well – logging backtests efficiently, CSV import, screenshots per trade, and keeping all the data secure – and adds the Ideal Trades catalogue, which is how the journal is mainly being used right now. Each strategy moves through two stages: first an Ideal Trades catalogue of winners, logged quickly by hand, then a full Backtest once there’s enough data to define the rules. An Analytics tab sits across both.

### 2.1 Strategy overview (landing screen)

- Opening the Replay Journal shows a grid of the strategies we’ve created, each as a card with its own headline statistics.
- Each card shows: strategy name and creator; current stage (Ideal Trades, Ready to backtest, or Backtesting); number of ideal trades and the date range they cover; backtest headline stats once available (win rate, average R, total R, profit factor, max drawdown); and last updated.
- A progress bar shows how close the strategy is to 6 months of ideal-trade coverage.
- A “+ New strategy” button creates a strategy with: name, instrument(s), timeframe(s), a short description of the idea, and its entry models.
- Opening a strategy shows three tabs: Ideal Trades, Backtest and Analytics.

### 2.2 Ideal Trades tab

- Purpose: a catalogue of winners only – the textbook examples of the setup. Logging only winners keeps this stage quick to do manually.
- Each ideal trade records: date, instrument, entry time and session, direction, entry model, entry price, SL and TP (in pips/points and as R), trade duration, screenshot(s), short reasoning notes, and tags.
- The entry form is built for speed: sensible defaults from the strategy, recent values remembered, and screenshots added by paste or drag-and-drop.
- A coverage tracker shows months covered against the 6-month target, plus trade count.
- Once 6 months are complete, the tool reviews the whole catalogue and generates that strategy’s **strategy profile**: average TP and SL distances, average R, typical duration, most common entry times and sessions, entry model frequency, day-of-week spread, and the most common sources and confluences noted on the trades.

### 2.3 Backtest tab

- Unlocks once the Ideal Trades catalogue covers 6 consecutive months, with at least one ideal trade in each month. Until then it shows as locked with the coverage progress, but can be opened early with a warning – useful for strategies that trade rarely or need a quick check.
- The strategy profile from the ideal trades is shown at the top as the reference rules (average TP/SL, entry time window, entry models, typical duration), so the backtest is run with consistent parameters.
- Every valid setup is logged – wins, losses and breakevens – via CSV import from FX Replay or manual entry, keeping screenshots and reasoning per trade from the current build.
- Each backtest trade records the ideal-trade fields plus outcome, R multiple, P&L, and whether the strategy rules were followed.

### 2.4 Analytics tab

- A data source switch at the top: **Ideal Trades**, **Backtest**, or **Compare**.
- Filters: date range, instrument, session, entry time window, day of week, entry model, direction, tags, outcome (backtest only), and who logged the trade.
- Ideal Trades views: TP and SL size distributions, duration, an entry-time heatmap, and entry model breakdown – what a typical winner looks like.
- Backtest views: win rate, average R, expectancy, profit factor, equity curve in R, max drawdown, win/loss streaks, and breakdowns by session, entry model and day of week.
- Compare view: the backtest’s real results set against the ideal profile, e.g. how much of the ideal average R is actually captured, and which entry times or models hold up.
- Export of filtered data and charts (CSV / PDF).

## 3. News Room

The News Room is where we see what’s scheduled, what’s just been released, and how it has moved the markets we trade. Its job is practical: avoid getting caught by news, understand how each event typically moves our instruments, and feed that knowledge back into the Replay Journal. It also powers the “Today’s news” card on the homepage.

### 3.1 Economic calendar

- Day and week views, all times in UK time, with today shown by default.
- Each event shows: time, currency, event name, impact (high / medium / low), and actual vs forecast vs previous.
- Once released, the actual figure is coloured by surprise: better or worse than forecast, and by how much.
- A countdown to the next high-impact event is pinned at the top.
- Filters: currency, impact level, and “my instruments only”.
- Each event is mapped to the instruments it affects, e.g. USD events → XAUUSD, BTC/USD, EUR/USD; EUR and German events → GER40, EUR/USD. Users choose which instruments they follow.

### 3.2 Trading-day timeline

- A horizontal timeline of the day showing the Asia, London and New York sessions, with news events marked on it.
- **News windows:** a shaded no-trade zone around each high-impact event (e.g. 15 minutes either side, adjustable per user).
- Makes it obvious at a glance which parts of the day are clean to trade and which are risky.

### 3.3 Event detail

Tapping an event opens a detail page:

- A plain-English explanation of what the event is and why it matters.
- A history table of past releases: actual, forecast, previous and surprise.
- **Price reaction history:** how our instruments moved in the 5, 15 and 60 minutes after past releases (range in pips/points and direction), using Twelve Data price history. Reactions are calculated once and stored, so they don’t eat into the daily credits.
- A short summary line, e.g. “US CPI: XAUUSD has averaged a 180-point range in the first 15 minutes over the last 12 releases.”

### 3.4 Week ahead

- A “Week ahead” summary, available from Sunday evening, listing the key high-impact events by day and the instruments they affect.
- Doubles as a planning view for the homepage calendar, so backtesting or review tasks can be placed on quieter days.

### 3.5 Alerts

- Optional reminders before high-impact events (e.g. 15 minutes before), set per user and per currency.
- Browser notifications first; a shared group alert (e.g. Telegram or Discord) could come later for the mates.

### 3.6 Link to the Replay Journal

- Trades logged in the Replay Journal are automatically tagged if they fall inside a news window, with the event name.
- Adds a “News” filter to the Analytics tab: inside vs outside news windows, and by event type.
- Answers the practical question: does this strategy perform better, worse, or the same around news?

### 3.7 Data and build notes

The News Room uses two free sources together, with the backend storing everything it fetches so we build our own history over time.

- **Schedule – Forex Factory weekly JSON feed:** free, no API key, and widely used by MT4/MT5 news filters. Covers the current Sunday–Saturday week with time, currency, impact, forecast and previous, but no released actuals. Powers the homepage news card, week ahead view and news windows. Refreshed by the server at most hourly and cached.
- **Actuals and history – JBlanked News API:** free with an API key, built on the MQL5 calendar (Forex Factory and FXStreet also selectable as sources). Returns actual, forecast and previous plus per-event history. The free tier allows one request every 5 minutes, so the backend fetches at most once every 5 minutes while the portal is in use, and shares the result with all users.
- **Our own database:** every event and released actual is stored as it arrives, along with the price reactions calculated from Twelve Data. Over a few months this builds the release history behind the event detail pages, at no extra cost.
- **Reliability:** both feeds run side by side, so if one fails the other still shows the schedule. The News Room shows a “last updated” time, and failed fetches are logged so we notice if a feed changes.
- **Avoid:** scraping the forexfactory.com calendar page directly – it’s fragile (Cloudflare challenges) and against the site’s terms.
- **Optional backfill:** if we want a few years of historical actuals from day one, a paid scraper (e.g. an Apify Forex Factory actor, roughly $10 per 1,000 event rows) could be used once to backfill high-impact events for our currencies.
- **Later option:** a headlines feed of breaking market news filtered to our instruments, once the calendar side is solid.

## 4. Platform foundations

### 4.1 Users, roles and sharing

- Each mate has their own account, created by the admin (no public sign-up).
- Everything in the portal has an owner: strategies, ideal trades, backtest trades, calendar tasks and watchlists.
- All users can see everyone’s data.
- **Member role:** full control of their own work; view-only access to everyone else’s.
- **Admin role (Jamie):** can view and edit everything, and manages users and roles.
- **View toggle** at the top of each tool: Personal (my work only) · **Combined** (everyone – the default, in the middle) · Shared (other users’ work).
- The owner is shown on every strategy card, trade and task, and analytics can be filtered by owner.

### 4.2 Tech stack and hosting

- Reuse the Replay Journal’s current setup (framework, database, screenshot storage and fly.io deployment) wherever possible. Start fresh only if that setup can’t support multiple users cleanly.
- Goal: free, or as close to free as possible, and easy to run – like the Replay Journal today.
- **No always-on machine:** rather than a background poller, data refreshes on demand. When someone opens the portal and the cached data is older than its refresh interval, the backend fetches fresh data. The app can keep scaling to zero when nobody is using it.
- Trade-off: alerts before news events need something running in the background, so they stay a later option (or use a free scheduled trigger).

### 4.3 One shared Twelve Data budget

- A single Twelve Data API key with 800 credits a day, shared across all users and every feature: homepage prices, instrument search and News Room price reactions.
- The backend tracks credits used and prioritises them: watchlist refreshes and searches first, price-reaction calculations only with credits left over.
- The homepage usage meter shows the shared total for everyone.
- Still to check (Jamie): Twelve Data free plan coverage of GER40 and XAUUSD, and whether Twelve Data’s and JBlanked’s terms allow a shared app.
