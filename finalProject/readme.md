## Phase 0 — Environment

- **Python:** virtual environment at `finalProject/.venv`. Refresh packages:  
  `cd finalProject && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- **Jupyter:** choose kernel **Python (finalProject supply chain)** (registered from this venv). If missing, run once:  
  `.venv/bin/python -m ipykernel install --user --name=finalproject-supply-chain --display-name="Python (finalProject supply chain)"`
- **Neo4j:** place the CSV in the database **import** directory; `LOAD CSV` uses `file:///your_filename.csv` (filename only, no full host path).
- **Driver credentials (next phases):** export `NEO4J_URI` (e.g. `bolt://localhost:7687`), `NEO4J_USER`, `NEO4J_PASSWORD` before running connection cells.
- **Paths:** start Jupyter from `finalProject` (or set the notebook’s working directory there) so relative files like `supply_chain_map.html` load correctly.
