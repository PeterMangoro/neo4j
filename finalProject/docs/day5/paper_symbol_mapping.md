# Workbook columns to paper symbols (Day 5)

**Paper:** Quetschlich, Moetz & Otto, *Optimisation model for multi-item multi-echelon supply chains with nested multi-level products* (European Journal of Operational Research; open access). **Section 3** defines sets, parameters, and the core MILP.

**Workbook:** Moetz et al. (2020) Mendeley dataset — column names match [`docs/day2/extraction_manifest.md`](../day2/extraction_manifest.md).

This document maps **tabular columns → paper notation**. It does **not** replace the Neo4j label/relationship design (see Week 2 Day 6 and `AutomotiveSupplyChain_Merged_Submission.ipynb`); it ensures **one semantic story** from CSV → math → graph properties.

---

## 1. Sets (paper → CSV role)

| Paper set | Meaning | How it appears in CSV |
|-----------|---------|------------------------|
| \(N\) | Nodes (facilities / locations) | `nodes.node_n`; endpoints in `arcs`, `capacity_at_arc`, flows, etc. |
| \(A\) | Directed arcs \((i,j)\) | Distinct pairs from `starting_node_i`, `ending_node_j` in `arcs` (and repeated per period in time-varying tables). |
| \(P\) | Items (products, parts, transport equipment as items) | `products.product_p`; `BOM.mother` / `child`; demand and flow `product_p` where present. |
| \(G\) | Item groups | `products.group_g`; `arcs.group_g`; `operations` input/output group fields; `max_flow_group_per_arc.group_g`. |
| \(T\) | Time periods \(t = 1,2,\ldots\) | Integer `period_t` in `demands`, `capacity_at_arc`, `initial_*`, `max_flow_*`. |
| \(B\) | Variant BOM tuples \((m,c)\) | `BOM`: `mother` → \(m\), `child` → \(c\), `individual_input_quantity_q_mc` → \(q_{mc}\). |
| \(O\) | Operations \((n,x,y)\) | `operations`: node \(n\), input group \(x\), output group \(y\) with quantities. |
| \(F\) | Allowed flows \((i,j,p)\) | Implied by arcs and products that may use an arc (import/load design); not a separate sheet. |

---

## 2. Master column map (every exported column)

| File | Column | Paper symbol / role |
|------|--------|---------------------|
| **products** | `product_p` | Item index \(p \in P\) (dataset stores as string; cast as needed). |
| | `group_g` | Group \(g_p\) assigning \(p\) to \(g \in G\). |
| | `transportation_size_s` | Transport size \(s_p\): for non-transport items, demand on transport capacity; for transport-class items, capacity (paper §3, constraint (6)). |
| **nodes** | `node_n` | Node id \(n \in N\). |
| **nodes_inflow** | `node_n` | Production / inflow site \(n\). |
| | `product_p` | Item \(p\) produced or entering at \(n\) (import schema links to `PRODUCES`-style edges). |
| **arcs** | `starting_node_i` | Arc tail \(i\) for \((i,j) \in A\). |
| | `ending_node_j` | Arc head \(j\). |
| | `process_lead_time_l_ij` | Lead time \(l_{ij}\) (periods from start on edge to arrival). |
| | `group_g` | Item group carried or classified on that arc (dataset-specific; ties to capacity semantics). |
| **capacity_at_arc** | `starting_node_i`, `ending_node_j` | Arc \((i,j)\) for capacity \(c_{ijt}\). |
| | `period_t` | \(t \in T\). |
| | `capacity_c_ijt` | Aggregate flow capacity on \((i,j)\) in period \(t\) (paper \(c_{ijt}\) in (2)). |
| **demands** | `node_n` | Demand location \(n\) (typically OEM) for \(d_{npt}\). |
| | `product_p` | Item \(p\) demanded. |
| | `demand_d_npt` | \(d_{npt}\) (external demand in inventory balance (4)). |
| | `period_t` | \(t\). |
| **initial_inventories** | `node_n` | \(n\) for initial inventory \(inv_{np}\) at \(t=0\) / snapshot period. |
| | `product_p` | \(p\) (may be alphanumeric part id; see Day 3 INFO). |
| | `initial_inventory_I_np0` | Initial stock level (paper \(inv_{np}\) at baseline). |
| | `safety_stock` | Extra modeling field (not in minimal generic MILP; use in extensions). |
| | `max_inventory` | Upper bound / slot size (extension). |
| | `period_t` | Snapshot period for the row (here single-period baseline). |
| **initial_flows** | `starting_node_i`, `ending_node_j` | Arc for historical flow before main horizon. |
| | `product_p` | Item flowing. |
| | `period_t` | Historical \(t\) (e.g. 39–60). |
| | `initial_flow` | Magnitude of flow in that period (initial condition for rolling horizon / warm start narratives). |
| **BOM** | `mother` | \(m\) in \((m,c) \in B\). |
| | `child` | \(c\) (component / sub-item). |
| | `individual_input_quantity_q_mc` | \(q_{mc}\) when variant BOM applies (paper Table 2 style). |
| **operations** | `node_n` | Operation location \(n\) for \(o=(n,x,y)\). |
| | `input_product_group_x` | Input group \(x\) (paper \(x\) in \(O\)). |
| | `output_product_group_y` | Output group \(y\). |
| | `input_quantity_in_nxy` | \(in_{nxy}\) (inputs per batch of operation). |
| | `output_quantity_out_nxy` | \(out_{nxy}\). |
| | `alpha_nxy` | \(\alpha_{ny}\): tie simultaneous output groups sharing the same \(\alpha\) (paper Fig. 6, constraint (5) style). |
| | `beta_nxy` | \(\beta_{nxy}\): 0 = use group quantities \(in_{nxy}, out_{nxy}\); 1 = use variant BOM \(q_{mc}\) for assembly options. |
| **max_flow_product_per_arc** | `starting_node_i`, `ending_node_j`, `product_p`, `period_t` | Tighter per-item cap on \(f_{ijpt}\) (implementation extension beyond single \(c_{ijt}\) sum). |
| | `planned_flow` | Upper bound value for that tuple. |
| **max_flow_group_per_arc** | `starting_node_i`, `ending_node_j`, `group_g`, `period_t` | Group-aggregate cap on flows for \(g\) on \((i,j,t)\). |
| | `planned_flow` | Upper bound. |

---

## 3. Core decision variables (paper — not CSV columns)

These are **solved** in the MILP, not stored as input CSVs:

| Symbol | Meaning |
|--------|---------|
| \(f_{ijpt}\) | Flow of item \(p\) on arc \((i,j)\) starting in period \(t\). |
| \(inv_{npt}\) | Inventory of \(p\) at \(n\) at **beginning** of period \(t\) (paper timing convention). |

Your dataset supplies **parameters** that constrain or initialize these (capacities, demands, initial inventories, flows).

---

## 4. Operations: \(\alpha\) and \(\beta\) (paper semantics)

- **\(\beta_{nxy}\)** (here `beta_nxy`): If **0**, operation \((n,x,y)\) consumes inputs and produces outputs using the **group-level** ratios \(in_{nxy}\) / \(out_{nxy}\). If **1**, the operation uses **variant BOM** entries \(q_{mc}\) for specific mother–child pairs (paper §3, Tables 1–2 and inventory balance (4)).
- **\(\alpha_{ny}\)** (here `alpha_nxy` aligned to output side): Groups of output item groups that must leave the node **simultaneously** (same \(\alpha\) value), e.g. paired parts from one process (paper Fig. 6–7, constraint (5)).

When importing into a graph DB, store these as **properties on operation edges or nodes** so Cypher can filter “option BOM” vs “fixed recipe” logic.

---

## 5. Relation to Day 4

Measurement caveats (BOM children not all in `products`, mixed period horizons) are in [data_reliability_note.md](../day4/data_reliability_note.md). This mapping is **notation-consistent** with the paper; empirical interpretation still follows Day 4.

## Revision log

| Date | Change |
|------|--------|
| Day 5 | Initial paper ↔ workbook mapping |
