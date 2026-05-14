# Final project — Automotive supply-chain knowledge graph

This directory supports a **self-defined capstone**: model a **multi-echelon automotive production network** in **Neo4j**, explore it with **Cypher**, and use **Graph Data Science (GDS)** for dependency, bottleneck, and risk-style analysis. The **submission notebook** is [P_Mangoro_AutomotiveSupplyChain.ipynb](P_Mangoro_AutomotiveSupplyChain.ipynb) (Option 2: deeper Cypher plus GDS workflows with interpretation).

**Team:** Bekithemba Nkomo, Masheia Dzimba, Peter Mangoro.

## Project summary

The capstone treats the Moetz et al. (2020) automotive production-network instance as an **OEM assembly-continuity** question: when a supplier lane, component family, or site is stressed, **which SKUs, programs, and periods are exposed first**, and where should mitigation focus? We ingest the published workbook into **Neo4j** (facilities, products, BOM `REQUIRES`, logistics `SHIPS_TO`, demand, inventory, and related operational edges), then analyze it with **Cypher** and **Neo4j Graph Data Science** (centrality and community detection on explicit projections).

**Deliverable:** [P_Mangoro_AutomotiveSupplyChain.ipynb](P_Mangoro_AutomotiveSupplyChain.ipynb) follows **Option 2**: deeper analytical questions in Cypher plus GDS workflows with projection design and written interpretation—not a full optimisation replication of the source paper.

## Key findings

Findings below are **for this published instance**, not a claim about the entire automotive industry (see [docs/day4/data_reliability_note.md](docs/day4/data_reliability_note.md)).

- **Graph scale:** 12 facilities across tier-style roles, **28,049** products, **87,059** BOM relationships (`REQUIRES`), **11** inter-facility lanes (`SHIPS_TO`), and **28,000** demand lines across the modeled planning horizon—enough depth for multi-hop dependency and lane-level reasoning in one model.
- **Structural risk:** Deep BOM chains and lane lead-time patterns imply **non-trivial cascade exposure**; the analysis highlights a large set of **single-sourced** components, i.e. concentrated sourcing vulnerability in this extract.
- **Centrality (PageRank):** Highest structural impact clusters on OEM-side chokepoints (**`zp8`**, **`zp7`**) and upstream feeding layers (including **seat** and **battery** corridors in the narrative of the notebook)—useful for **where to prioritize** monitoring, contingency inventory, and supplier governance before spreading effort uniformly.
- **Communities (Leiden):** On a product-only `REQUIRES` projection, Leiden surfaces **large, distinct dependency communities** (on the order of thousands of members each), mostly car-dominant but structurally different—supporting **module-level risk zones** instead of treating the BOM as one undifferentiated mass.
- **Executive story:** **Platform-common** families (engine, gear, seat, etc.) drive **broad portfolio exposure**; **battery**-related dependencies are more **program/variant-specific** and warrant targeted program-level actions in this dataset’s framing.
- **Method takeaway:** Graph-native storage plus Cypher makes **multi-hop impact and traceability** queries practical; GDS adds **ranking and segmentation** (centrality, communities) that are awkward to reproduce with hand-rolled relational recursion alone.

**Limitations (brief):** The workbook is a **research / tactical instance**, not live ERP data; results are for **relative prioritization** inside this graph unless extended with real-time capacity, quality, financial health, geography, and fuller supplier tiers. The notebook’s §10 expands limitations and future work (temporal graphs, additional algorithms, operational embedding).

## Contents

| Item | Role |
|------|------|
| [P_Mangoro_AutomotiveSupplyChain.ipynb](P_Mangoro_AutomotiveSupplyChain.ipynb) | **Main deliverable:** extract `.xlsx` → CSV → constraints → `LOAD CSV` → EDA → deeper Cypher → GDS (PageRank, Leiden) → validation and conclusions |
| [requirements.txt](requirements.txt) | Python stack: Neo4j driver, Jupyter, pandas, plotting, `python-dotenv`; optional `pyxlsb` if you use the `.xlsb` variant from Mendeley |
| [.env.example](.env.example) | Template for Bolt + optional `NEO4J_DATABASE` (isolate graph) + optional `NEO4J_IMPORT_DIR` for `LOAD CSV` (copy to `.env`) |



## Data reference

Dataset: Moetz, A., Quetschlich, M., & Otto, B. (2020). *Data for: Optimisation model for multi-item multi-echelon supply chains with nested multi-level products* (Version 1). Mendeley Data. [https://doi.org/10.17632/pr3sdy5vp3.1](https://doi.org/10.17632/pr3sdy5vp3.1)

The workbook describes an automotive-style network (OEM, tier-style suppliers, arcs, BOM structure, inventories, demand over time). The submission notebook documents which sheets become which labels and relationship types.

## Environment

**Goal:** Python venv with project deps, optional Jupyter kernel, Neo4j Bolt reachable, paths documented.

1. **Python:** create a virtual environment in this folder and install dependencies:

   ```bash
   cd finalProject && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt
   ```

2. **Excel engine:** the submission notebook reads **`.xlsx`** with `pandas.read_excel`. If pandas reports a missing engine, install **openpyxl** in the same venv (`pip install openpyxl`).

3. **Neo4j credentials (local file):** copy the template and edit — **never commit** `.env` (it is gitignored repo-wide):

   ```bash
   cp .env.example .env
   # set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
   ```

4. **Quick check:** from `finalProject`, with Neo4j running:

   ```bash
   .venv/bin/python scripts/verify_phase0.py
   ```

   Expect `OK` lines for imports and Bolt connectivity. If Neo4j is off, fix the stack first; the script still confirms Python deps.

5. **Jupyter:** register a kernel from this venv if you want a named kernel in the UI:

   ```bash
   .venv/bin/python -m ipykernel install --user --name=finalproject-supply-chain --display-name="Python (finalProject supply chain)"
   ```

   Open the submission notebook with **working directory** `finalProject` so relative paths to the workbook and `data_export/` resolve.

6. **`LOAD CSV`:** put CSVs Neo4j will read under the database **import** directory; in Cypher use `file:///your_filename.csv` (filename only, not a host filesystem path). The notebook writes exports under `data_export/` (typically gitignored); copy the files Neo4j needs into the import directory before running ingest cells.


## Workflow in the submission notebook

Run [P_Mangoro_AutomotiveSupplyChain.ipynb](P_Mangoro_AutomotiveSupplyChain.ipynb) top-down after placing `2020_dataset_OfAutomotiveProductionNetwork.xlsx` in `finalProject/`.

| Notebook section | What you do |
|------------------|-------------|
| **§2** Environment setup and imports | Configure paths, Neo4j driver, dependencies |
| **§3** Extract workbook tabs to CSV | Build `data_export/*.csv` used by `LOAD CSV` |
| **§4** Schema constraints | Uniqueness / keys before bulk load |
| **§5** Ingest | Stage `LOAD CSV` for facilities, products, BOM, demand, flows, etc. |
| **§6** Graph EDA | Exploratory Cypher and structural summaries |
| **§7** Deeper analytical questions | Option 2 “deeper” Cypher analyses |
| **§8** Graph Data Science | Projections, PageRank, Leiden (and written interpretation) |
| **§9–§11** Validation, conclusions, references | Count checks, scope limits, citations |


Repository overview: [../README.md](../README.md).
