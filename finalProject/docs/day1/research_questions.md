# Research questions and KPIs (Day 1)

Aligned with Quetschlich, Moetz & Otto (*European Journal of Operational Research*, 2020) and the Moetz et al. (2020) Mendeley dataset.

## Definition of done (business outcome)

**Done means** we can quantify how a supply-side shock propagates through the BOM and facility network, identify the periods and arcs where feasibility or service stress concentrates, and evaluate at least one mitigation strategy (e.g., rescheduling vs baseline) with explicit trade-offs—not merely produce charts without operational interpretation.

Reproducibility of notebooks and CSV exports is a **quality gate**, not the headline success criterion.

---

## Core research questions

1. **Propagation** — When upstream availability or capacity is constrained, which product families and facilities are affected, and through which BOM and arc paths does the effect travel?

2. **Binding constraints** — For each planning period, is stress driven primarily by lead times (`l_ij`), arc capacities (`c_ijt`), product/group flow limits, or upstream inventory/flow state?

3. **Mitigation** — Compared to a baseline plan, does a defined reaction (e.g., postponement, rebalancing flow across periods) improve feasible service or line utilization, and at what cost in delay or shortfall?

---

## KPIs and metrics

| KPI | Meaning | Primary sources (workbook / paper) |
|-----|---------|-----------------------------------|
| **Arc utilization** | Flow or implied load vs `capacity_c_ijt` (and product/group caps where relevant) | `capacity_at_arc`, `max_flow_*`, flows |
| **Demand coverage** | Realized or implied satisfaction of `demand_d_npt` vs planned/actual flow to demand node | `demands`, arcs to OEM |
| **Shortfall / delay** (scenario layer) | Gap between promised period and achieved flow, if modeled like the paper’s case study | Paper §4.6 (`os_pt`, `of_pt`); adapt to available columns |
| **Critical path length** | Cumulative `process_lead_time_l_ij` along worst-case paths Tier-2 → OEM | `arcs` |
| **BOM depth / fan-out** | Structural exposure: depth to finished vehicle, number of distinct components | `BOM` |
| **Centrality (secondary)** | Which nodes appear on many shortest paths or rank high on PageRank—**interpreted with** capacity/lead time, not alone | Neo4j GDS |

---

## Success criteria for the 2-week sprint

- **Primary:** Written answers to Q1–Q3 above, each supported by at least one table, figure, or query result tied to the dataset.
- **Secondary:** One baseline vs one mitigation scenario comparison documented with KPI deltas.
- **Quality:** Data dictionary and integrity notes explain limitations; conclusions state scope (tactical network excerpt, simulated/aggregated where applicable).
