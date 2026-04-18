# Data reliability note (Day 4)

This note applies concepts from [DGP_EDA_Beginner_Guide.md](../../DGP_EDA_Beginner_Guide.md) (data generating process, missing data, pitfalls) to **this** project. Evidence from automated checks is in [docs/day3/profile_integrity_summary.md](../day3/profile_integrity_summary.md).

## 1. Data generating process (DGP)

**Source.** The workbook is the Moetz, Quetschlich & Otto (2020) Mendeley dataset published with *Optimisation model for multi-item multi-echelon supply chains with nested multi-level products* (Quetschlich et al., EJOR 2020). The paper’s case study §4.7 states that practical series were combined with **simulation and completion** so that initial inventories and flows are **not** a complete live ERP snapshot: the goal is a **consistent tactical instance** for modeling, not a census of a real plant’s state on a given day.

**Implication.** Findings should be framed as **structural and tactical insights on this network instance**—network topology, BOM shape, capacity and lead-time layering—not as universal empirical facts about an unnamed OEM’s production system.

## 2. Sampling and coverage

**What is included.** The extract covers **12 facilities**, **11 directed arcs**, **28,049** product rows, **87,059** BOM edges (mothers to children), **28,000** demand rows, and time-varying capacity on arcs. Demand is concentrated at a single demand node (`node_n` distinct = 1 in `demands.csv` per Day 3 profile).

**What is excluded.** The dataset is a **slice** of a multi-echelon story: not all real-world suppliers, products, or periods exist here. External demand drivers (macro, promotions) are not observed; only the tabular demand series is.

**Bias risk.** Any analysis that generalizes from this slice to “the automotive industry” without stating boundaries is **over-claiming**. Prefer language: “in this instance / under these parameters.”

## 3. Measurement and identifiers

- **Products:** `products.product_p` is stored as string in the extract; **28,049** distinct values, **7** `group_g` values. `transportation_size_s` shows **1** distinct value in this snapshot (limited variation for transport modeling in this extract).
- **BOM:** **49** distinct `child` codes vs **28,049** `mother` keys. Day 3 integrity reported **INFO**: child codes need not appear as rows in `products` (part codes vs catalog rows)—model as separate part identities where needed.
- **Facilities:** String node IDs (`node_n`, arc endpoints) are the authoritative keys; referential checks passed with **no WARN** in Day 3 (INFO only).
- **Time:** `period_t` is integer. Observed ranges (Day 3): `demands` and `capacity_at_arc` **61 … 74**; `initial_flows` **39 … 60**; `initial_inventories` fixed at **60**; `max_flow_*` **61 … 70**. Mixed horizons are **intentional** (history vs planning window), not a data entry bug by itself.

## 4. Missing data

**Tabular nulls.** Full-file profile shows **no nulls** in any exported column for this snapshot (see Day 3 “Null counts: none” for each table).

**Hidden missingness.** “No NA” does not mean “complete real-world information.” Unobserved suppliers, products, and shocks are still **missing by design** relative to reality. Do not equate absence of NA cells with absence of model risk.

**Mechanism.** We **cannot** reliably classify MCAR/MAR/MNAR for latent industry processes from this extract alone. Treat missing **context** as a **limitation** in the report, not as a fitted missing-data model unless you add external evidence.

## 5. Outliers and extremes

**Statistical outliers.** No automated IQR/z-score pass is in scope for Day 4. Week 2 EDA may flag extreme `capacity_c_ijt`, `planned_flow`, or `initial_flow` relative to demand.

**Operational “outliers.”** Single-period shocks or shortages are **scenario constructs** (paper §4) rather than rows labeled “event” in the CSV. Scenario design should document assumptions explicitly.

## 6. Misuse risks (pitfalls)

- **Graph centrality alone:** High PageRank (or degree) does not prove operational criticality without **capacity** and **lead time** context ([research_questions.md](../day1/research_questions.md) KPI table).
- **BOM vs product catalog:** Treating every `BOM.child` as a `products.product_p` row would be **wrong** for this dataset (Day 3 INFO).
- **Demand uniqueness:** **28,000** distinct `product_p` in `demands` with **demand_d_npt** = 1 distinct value in profile—interpret demand volume patterns carefully (structure is order-level / unit-level as defined by the generator).

## 7. Implications for research questions and KPIs

| Question / KPI | What we can claim strongly | What to qualify |
|----------------|---------------------------|-----------------|
| Q1 Propagation | Paths and BOM structure **on this network** | Full industry coverage |
| Q2 Binding constraints | Comparisons using `l_ij`, `c_ijt`, caps in tables | Unmodeled operational rules |
| Q3 Mitigation | Scenario deltas **under stated assumptions** | Optimality vs real dispatch systems |
| Arc utilization / bottlenecks | Relative stress **from given capacities and demand** | True spare capacity off-network |
| Centrality | Relative structural importance **in this graph** | Revenue or risk without weighting |

## 8. Relation to Day 1 assumptions

This note **grounds** [assumptions_and_limits.md](../day1/assumptions_and_limits.md): synthetic/completed series, tactical scope, and BOM–product quirks are consistent with Day 3 **INFO** lines and paper §4.7.

## Revision log

| Date | Change |
|------|--------|
| Day 4 | Initial data reliability note |
