# Final project — Automotive supply-chain knowledge graph

This directory supports a **self-defined capstone**: model a **multi-echelon automotive production network** in **Neo4j**, explore it with **Cypher**, and use **Graph Data Science (GDS)** for dependency, bottleneck, and risk-style analysis. The topic and dataset are documented in [Brainstorming_Template.ipynb](Brainstorming_Template.ipynb).

**Students (proposal notebook):** Bekithemba Nkomo, Masheia Dzimba, Peter Mangoro.

## Contents

| Item | Role |
|------|------|
| [Brainstorming_Template.ipynb](Brainstorming_Template.ipynb) | Proposal / brainstorming: topic, impact, data citation, research questions (Neo4j + Cypher + GDS notebook deliverable) |
| [AutomotiveSupplyChain_Work.ipynb](AutomotiveSupplyChain_Work.ipynb) | **Main build + analysis** notebook: extract → profile → Neo4j → EDA → deep Cypher → GDS (Phase 1 scaffold onward) |
| [2020_dataset_OfAutomotiveProductionNetwork.xlsb](2020_dataset_OfAutomotiveProductionNetwork.xlsb) | Primary data: Moetz et al. (2020) multi-echelon supply-chain network (Excel binary; ingest via pandas / export to CSV for `LOAD CSV` as your pipeline defines) |
| [selfDefinedProject.md](selfDefinedProject.md) | Official **minimum requirements** for the self-defined final (EDA count, deeper questions, Option 1 vs 2, GDS write-up expectations) |
| [requirements.txt](requirements.txt) | Python stack: Neo4j driver, Jupyter, pandas, plotting, `python-dotenv` |
| [.env.example](.env.example) | Template for Bolt + optional `NEO4J_DATABASE` (isolate graph) + optional `NEO4J_IMPORT_DIR` for `LOAD CSV` (copy to `.env`) |
| [scripts/verify_phase0.py](scripts/verify_phase0.py) | Phase 0 sanity check: imports + optional Bolt connectivity |

## Data reference

Dataset: Moetz, A., Quetschlich, M., & Otto, B. (2020). *Data for: Optimisation model for multi-item multi-echelon supply chains with nested multi-level products* (Version 1). Mendeley Data. [https://doi.org/10.17632/pr3sdy5vp3.1](https://doi.org/10.17632/pr3sdy5vp3.1)

The workbook describes an automotive-style network (OEM, tier-1/tier-2 suppliers, arcs, BOM-style structure, inventories, demand over time). Your graph schema and import notebooks should spell out which sheets become which nodes and relationships.

## Phase 0 — Environment

**Goal:** Python venv with project deps, optional Jupyter kernel, Neo4j Bolt reachable, paths documented.

1. **Python:** create a virtual environment in this folder and install dependencies:

   ```bash
   cd finalProject && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt
   ```

2. **Neo4j credentials (local file):** copy the template and edit — **never commit** `.env` (it is gitignored repo-wide):

   ```bash
   cp .env.example .env
   # set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
   ```

3. **Quick check:** from `finalProject`, with Neo4j running:

   ```bash
   .venv/bin/python scripts/verify_phase0.py
   ```

   Expect `OK` lines for imports and Bolt connectivity. If Neo4j is off, fix the stack first; the script still confirms Python deps.

4. **Jupyter:** register a kernel from this venv if you want a named kernel in the UI:

   ```bash
   .venv/bin/python -m ipykernel install --user --name=finalproject-supply-chain --display-name="Python (finalProject supply chain)"
   ```

   Start Jupyter or open notebooks with **working directory** `finalProject` so relative paths to the workbook and exports resolve.

5. **`LOAD CSV`:** put CSVs Neo4j will read under the database **import** directory; in Cypher use `file:///your_filename.csv` (filename only, not a host filesystem path).

**Phase 0 done when:** `verify_phase0.py` reports OK for imports and (if DB is up) Bolt connectivity.

## Phase 1 — Work notebook + extraction scaffold

**Goal:** One notebook to carry the project through ingest and analytics; scripted `.xlsb` → CSV export.

- **Dependency:** `pyxlsb` is listed in [requirements.txt](requirements.txt) (re-run `pip install -r requirements.txt`).
- **Notebook:** open [AutomotiveSupplyChain_Work.ipynb](AutomotiveSupplyChain_Work.ipynb) from this folder, run top-down through the extraction and profiling cells once the Mendeley workbook is saved as `2020_dataset_OfAutomotiveProductionNetwork.xlsb`.
- **Exports:** CSVs are written to `data_export/` (gitignored). Copy the ones you need into your Neo4j **import** directory for `LOAD CSV`.
- **Phase 1 done when:** notebook runs through Section 4 without errors (or prints a clear missing-workbook message) and `verify_phase0.py` shows `OK: pyxlsb import`.

## Phase 2 — Tabular validation and data dictionary

**Goal:** Full counts, nulls, distinct values, and cross-table checks on `data_export/*.csv` before writing ingest Cypher.

- **Notebook:** in [AutomotiveSupplyChain_Work.ipynb](AutomotiveSupplyChain_Work.ipynb), run **Section 5** (Phase 2): two validation code cells, then review/update the **column → graph** table.
- **Phase 2 done when:** every expected CSV is profiled at full row count, node/product reference checks have been read (WARN/INFO addressed in your model notes), and the dictionary matches your column names.

## Phase 3 — Neo4j graph build (`LOAD CSV`)

Phase 3 is split into smaller steps in [AutomotiveSupplyChain_Work.ipynb](AutomotiveSupplyChain_Work.ipynb) §6–§7:

| Sub-phase | What |
|-----------|------|
| **3.1** | Import folder: optional `NEO4J_DATABASE` for a dedicated DB; optional `NEO4J_IMPORT_DIR` in `.env`; copy `data_export/*.csv` into Neo4j’s import directory (notebook helper cell); `LOAD CSV` runs **on the Neo4j server** |
| **3.2** | Constraints: notebook **§6** — optional full reset, create four `supply_*` uniqueness constraints, optional drop-only-`supply_*` cell |
| **3.3** | Notebook **§7**: copy CSVs to import dir, then `LOAD CSV` for `demands.csv` → `Period`, `products.csv` → `Product` / `ProductGroup` / `BELONGS_TO`, `BOM.csv` → `REQUIRES` |
| **3.4** | Notebook **§7** (Phase 3.4 cell): `nodes.csv` → `Node`; `arcs.csv` → `SHIPS_TO`; `nodes_inflow.csv` → `HANDLES`; `demands.csv` → `DemandFact` + `HAS_DEMAND` / `FOR_PRODUCT` / `IN_PERIOD`; `initial_inventories.csv` → `HOLDS`; `operations.csv` → `TRANSFORMS` |
| **3.5** | Notebook **§7** (Phase 3.5 cell): `capacity_at_arc.csv` → `CAPACITY_AT`; `max_flow_product_per_arc.csv` → `PLANNED_FLOW_TO`; `max_flow_group_per_arc.csv` → `GROUP_FLOW_TO`; `initial_flows.csv` → `INITIAL_FLOW_TO` |

**Phase 3.1 done when:** `NEO4J_IMPORT_DIR` points at your DB import folder (or you copy CSVs there manually) and `file:///your.csv` names match the files Neo4j can see.

## Next steps (phases beyond 3)

Follow [selfDefinedProject.md](selfDefinedProject.md) for rubric alignment: post-ingest checks (Phase 4), ≥8 EDA questions with Cypher + outputs, then either four deeper Cypher-only questions **or** two deeper Cypher questions plus at least one GDS workflow with projection design and written interpretation.

Repository overview: [../README.md](../README.md).
