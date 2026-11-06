"""Analytics engine (F16): pure metric functions, breakdowns, insights, reconcile, query and export.

Everything below `metrics`, `breakdowns` and `insights` is plain Python over `Row` objects so it can be
tested against hand-computed numbers without a database. `query` loads rows and applies the 2.4 filters.
"""
