# Day 1 runbook — environment and reproducibility

All paths relative to repository root `finalProject/` unless noted.

## 1. Python environment

```bash
cd finalProject
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

**Pinned stack (from [requirements.txt](../../requirements.txt)):** `neo4j`, `pandas`, `jupyter`, `ipykernel`, `matplotlib`, `seaborn`, `python-dotenv`, `pyxlsb`.

Optional Jupyter kernel:

```bash
.venv/bin/python -m ipykernel install --user --name=finalproject-supply-chain --display-name="Python (finalProject supply chain)"
```

## 2. Neo4j credentials

```bash
cp .env.example .env
# Edit .env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
# Optional: NEO4J_DATABASE, NEO4J_IMPORT_DIR for LOAD CSV
```

## 3. Connectivity check

With Neo4j running:

```bash
.venv/bin/python scripts/verify_phase0.py
```

Expect OK for imports and Bolt when the database is up.

## 4. Notebook entrypoint (canonical analysis pipeline)

- **Primary (2-week plan):** [`AutomotiveSupplyChain_TwoWeekPlan.ipynb`](../../AutomotiveSupplyChain_TwoWeekPlan.ipynb) — extraction, manifest, quick profile, placeholders for Days 4–10. Paths assume **current working directory = `finalProject`**.
- **Reference / legacy:** [`AutomotiveSupplyChain_Merged_Submission.ipynb`](../../AutomotiveSupplyChain_Merged_Submission.ipynb) — full Neo4j `LOAD CSV`, GDS, and deep analysis cells to copy from when filling Week 2 sections.
- **Alternate work notebook:** [`AutomotiveSupplyChain_Work.ipynb`](../../AutomotiveSupplyChain_Work.ipynb) per [readme.md](../../readme.md).

Run order for a clean rerun (after Day 2 extraction exists):

1. Paths + workbook check  
2. Extract `.xlsb` → `data_export/*.csv` (`pyxlsb`)  
3. Write `docs/day2/extraction_manifest.md`  
4. Profile and validate CSVs  
5. Neo4j load sections (Week 2 — use merged notebook as needed)

## 5. Canonical artifacts

| Artifact | Location |
|----------|----------|
| Raw workbook | `2020_dataset_OfAutomotiveProductionNetwork.xlsb` |
| Exported CSVs | `data_export/` (gitignored; create on Day 2) |
| Extraction manifest | `docs/day2/extraction_manifest.md` |
| Profile + integrity report | `docs/day3/profile_integrity_summary.md` |
| DGP / reliability note | `docs/day4/data_reliability_note.md` |
| Paper ↔ column mapping | `docs/day5/paper_symbol_mapping.md` |
| Day 1 docs | `docs/day1/` |

## 6. Day 1 “freeze” checklist

- [x] `requirements.txt` and `.env.example` reviewed  
- [x] Runbook documents venv + Neo4j + notebook CWD  
- [ ] Team confirms Neo4j version and Python version in report appendix (fill on first full run)
