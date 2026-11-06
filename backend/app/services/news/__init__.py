"""News Room services: the two feeds (Forex Factory, JBlanked), the store, tagging and the read side.

Modules:
  parse      figures as published ("0.3%", "185K") → numbers, and back
  catalogue  title normalisation and event-type matching (aliases seeded by migration 0008)
  ff         Forex Factory weekly JSON
  jblanked   JBlanked News API (actuals and history; strict rate and daily budget)
  store      upserts, the FF + JBlanked merge, coverage ranges
  jobs       the scheduler's `refresh_feeds(db, now)`
  tagging    trade news tags and `retag_if_coverage_grew(db, now)`
  queries    EventOut and every read the News Room API serves
  backfill   resumable month-by-month history load (`make news-backfill`)
  synthetic  dev-only synthetic week for seed-dev and the smoke suite
"""
