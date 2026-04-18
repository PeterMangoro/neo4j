# Assumptions and limits (Day 1)

## Scope locked for this project

- **Data:** Single source workbook [`2020_dataset_OfAutomotiveProductionNetwork.xlsb`](../../2020_dataset_OfAutomotiveProductionNetwork.xlsb) (Moetz et al., 2020) and derived canonical CSV exports under `data_export/` (see runbook).
- **Horizon:** Planning periods as in the dataset (e.g., demand and capacity rows use `period_t`; initial flows may reference earlier periods). Exact ranges are validated on Day 2–3.
- **Intent:** Research-style analysis and graph-based EDA aligned with the optimization paper’s *structure* (items, groups, arcs, BOM, operations)—not a full CPLEX replication unless explicitly added later.
- **Deliverable type:** Research report with methods, findings, and limitations—not a production scheduling system.

## Modeling assumptions

- **Time granularity:** One period = one day unless the data dictionary states otherwise (matches paper case study convention).
- **Facility graph:** Nodes and arcs in the workbook are treated as the authoritative network; supplier tiers are inferred from naming and path length, not from a separate master list.
- **BOM:** Mother–child links and quantities support explosion and traceability; optional codes may appear in BOM but not as rows in `products` (documented as INFO in validation, not discarded silently).
- **Transportation:** `transportation_size_s` in `products` is interpreted per paper semantics when used in flow/capacity reasoning.

## Data generating process (DGP) — high level

Per the embedded case study and dataset documentation:

- Network parameters and demand patterns are derived from **industry-style exports and case study** work; some series are **simulated or completed** for consistency (see paper §4.7).
- Treat findings as **structural and tactical insights** on this instance, not as universal empirical facts about a named OEM’s live ERP.

## Known limits (to refine during validation)

- Initial inventories and flows may be partially synthetic; sensitivity of results to those rows should be noted in the final report.
- Graph centrality alone does not prove operational criticality without capacity/lead-time context.

## Revision log

| Date | Change |
|------|--------|
| Day 1 | Initial scope and assumptions frozen |
| Day 4 | Expanded DGP and KPI limits in [docs/day4/data_reliability_note.md](../day4/data_reliability_note.md) |
