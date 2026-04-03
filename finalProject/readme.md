# Final project — Automotive supply-chain knowledge graph

This directory supports a **self-defined capstone**: model a **multi-echelon automotive production network** in **Neo4j**, explore it with **Cypher**, and use **Graph Data Science (GDS)** for dependency, bottleneck, and risk-style analysis. The topic and dataset are documented in [Brainstorming_Template.ipynb](Brainstorming_Template.ipynb).

**Students (proposal notebook):** Bekithemba Nkomo, Masheia Dzimba, Peter Mangoro.

## Contents

| Item | Role |
|------|------|
| [Brainstorming_Template.ipynb](Brainstorming_Template.ipynb) | Proposal / brainstorming: topic, impact, data citation, research questions (Neo4j + Cypher + GDS notebook deliverable) |
| [2020_dataset_OfAutomotiveProductionNetwork.xlsb](2020_dataset_OfAutomotiveProductionNetwork.xlsb) | Primary data: Moetz et al. (2020) multi-echelon supply-chain network (Excel binary; ingest via pandas / export to CSV for `LOAD CSV` as your pipeline defines) |
| [selfDefinedProject.md](selfDefinedProject.md) | Official **minimum requirements** for the self-defined final (EDA count, deeper questions, Option 1 vs 2, GDS write-up expectations) |
| [requirements.txt](requirements.txt) | Python stack: Neo4j driver, Jupyter, pandas, plotting, `python-dotenv` |

## Data reference

Dataset: Moetz, A., Quetschlich, M., & Otto, B. (2020). *Data for: Optimisation model for multi-item multi-echelon supply chains with nested multi-level products* (Version 1). Mendeley Data. [https://doi.org/10.17632/pr3sdy5vp3.1](https://doi.org/10.17632/pr3sdy5vp3.1)

The workbook describes an automotive-style network (OEM, tier-1/tier-2 suppliers, arcs, BOM-style structure, inventories, demand over time). Your graph schema and import notebooks should spell out which sheets become which nodes and relationships.

## Phase 0 — Environment

- **Python:** use a virtual environment in this folder, e.g. `finalProject/.venv`. Install deps:

  ```bash
  cd finalProject && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  ```

- **Jupyter:** register a kernel from this venv if you want a named kernel in the UI:

  ```bash
  .venv/bin/python -m ipykernel install --user --name=finalproject-supply-chain --display-name="Python (finalProject supply chain)"
  ```

- **Neo4j:** put CSVs the notebook generates under the database **import** directory when using `LOAD CSV`; use `file:///your_filename.csv` (filename only, not a full host path).

- **Driver credentials:** set `NEO4J_URI` (e.g. `bolt://localhost:7687`), `NEO4J_USER`, and `NEO4J_PASSWORD` before running connection cells (or load via `python-dotenv` if you add a local `.env` — do not commit secrets).

- **Working directory:** start Jupyter from `finalProject` (or set the notebook working directory here) so relative paths to data files and any generated assets (e.g. HTML maps) resolve correctly.

## Next steps (phases beyond 0)

Follow [selfDefinedProject.md](selfDefinedProject.md) for rubric alignment: knowledge graph build, ≥8 EDA questions with Cypher + outputs, then either four deeper Cypher-only questions **or** two deeper Cypher questions plus at least one GDS workflow with projection design and written interpretation.

Repository overview: [../README.md](../README.md).
