# Day 3 — Profiling and integrity

Run **Week 1 — Day 3** in [AutomotiveSupplyChain_TwoWeekPlan.ipynb](../../AutomotiveSupplyChain_TwoWeekPlan.ipynb) after `data_export/*.csv` exists (Day 2).

**Output (committed):**

- [`profile_integrity_summary.md`](profile_integrity_summary.md) — full-row profiles (dtypes, nulls, distinct counts, `period_t` ranges) and cross-table checks vs `nodes` / `products`.

**Interpretation:** WARN lines need review before Neo4j load; INFO lines document known catalog quirks (e.g. BOM child codes not duplicated in `products`).
