# GraphRAG chatbot (Devreotes corpus)

## Quick start

0. **Virtual environment** (recommended), from repo root:

   ```bash
   python3 -m venv chatBot/.venv
   source chatBot/.venv/bin/activate   # Linux/macOS
   # chatBot\.venv\Scripts\activate    # Windows
   ```

1. Create `chatBot/.env` with at least:

   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

   Optional: `OLLAMA_HOST`, `OLLAMA_EMBED_MODEL`, **`OLLAMA_CHAT_MODEL`** (RAG answers), `RAG_TOP_K`, `RAG_MIN_SCORE`, `NEO4J_DATABASE`, `EMBEDDING_DIM` (must match embedding model / `Chunk.embedding`; default `DEFAULT_EMBEDDING_DIM` in `backend/app/constants.py`). See `chatBot/.env.example`.

2. Install dependencies (with the venv activated):

   ```bash
   pip install -r chatBot/requirements.txt
   ```

3. Start Neo4j and Ollama locally.

4. **Register the Jupyter kernel** (so Cursor/VS Code / Jupyter show `chatBot/.venv`):

   ```bash
   source chatBot/.venv/bin/activate
   pip install -r chatBot/requirements.txt
   python -m ipykernel install --user --name graphrag-chatbot --display-name "Python (chatBot .venv)"
   ```

   Then in the notebook: **Kernel / Select Kernel → Python (chatBot .venv)**.

   **Note:** `.env` is not a kernel. Kernels use the **Python interpreter** from `chatBot/.venv`. `python-dotenv` loads `chatBot/.env` when your code runs.

   **Alternative (Cursor/VS Code):** Command Palette → **Python: Select Interpreter** → choose  
   `.../neo4j/chatBot/.venv/bin/python`, then pick that interpreter for the notebook.

5. Open notebooks:

   ```bash
   jupyter notebook chatBot/notebooks/00_intro_and_setup.ipynb
   jupyter notebook chatBot/notebooks/01_baseline_rag.ipynb
   ```

## Project docs

| File | Purpose |
|------|---------|
| `planning/GraphRAG_Implementation_Phases.md` | Phases and status |
| `planning/GraphRAG_Schema_v1.md` | Neo4j labels, vocab, DDL |
| `planning/tech_stack.md` | Tools and models |
| `planning/GraphRAG_Evaluation_Question_Set.md` | Benchmark questions |

**Data in `resources/`:** see [`resources/README.md`](resources/README.md) — PDF corpus (`PublicationsforAndy/`), optional HGNC gene lexicon (`hgnc_complete_set.txt`, download locally; gitignored).

## Single source of truth (embedding dimension and DDL)

| What | Where |
|------|--------|
| Default embedding size (if `EMBEDDING_DIM` unset) | [`backend/app/constants.py`](backend/app/constants.py) — `DEFAULT_EMBEDDING_DIM` |
| Runtime value for all Python code | [`backend/app/config.py`](backend/app/config.py) — `config.embedding_dim` (reads `EMBEDDING_DIM` from `chatBot/.env`) |
| DDL statement list | [`backend/app/schema_ddl.py`](backend/app/schema_ddl.py) — `ddl_statements(embedding_dim, include_claim_constraint=...)` |
| Apply to Neo4j | `python chatBot/scripts/apply_neo4j_schema.py` or `PYTHONPATH=. python -m app.neo4j_schema` from `chatBot/backend` |
| Regenerate Browser Cypher file | `python chatBot/scripts/generate_schema_ddl_cypher.py` (writes `cypher/schema_ddl.cypher` using current `.env`) |

Graph labels / relationship types for ingestion code: [`backend/app/constants.py`](backend/app/constants.py) — `Label`, `RelType`.

## Neo4j schema (constraints + indexes + vector index)

With Neo4j running and `chatBot/.env` configured:

```bash
python chatBot/scripts/apply_neo4j_schema.py
```

Or: `cd chatBot/backend && PYTHONPATH=. python -m app.neo4j_schema`

- **Cypher for Neo4j Browser:** `cypher/schema_ddl.cypher` (regenerate with `generate_schema_ddl_cypher.py` after changing `EMBEDDING_DIM`).
- **Details:** `backend/README.md`.

## Pilot ingest (Phase 3)

After Neo4j schema is applied and the embedding model is pulled in Ollama (`ollama pull nomic-embed-text-v2-moe` or your `OLLAMA_EMBED_MODEL`):

```bash
source chatBot/.venv/bin/activate
pip install -r chatBot/requirements.txt
python chatBot/scripts/run_pilot_ingest.py --limit 10
```

Implementation: `backend/app/pilot_ingest.py` (PDF extract → chunk → `/api/embeddings` → one write transaction per paper).

## Baseline RAG (Phase 4)

After chunks exist in Neo4j, pull a **chat** model: `ollama pull llama3.2` (or set `OLLAMA_CHAT_MODEL` in `.env`).

```bash
python chatBot/scripts/run_rag_query.py "What methods appear in the corpus?"
# Stream tokens as Ollama generates (same retrieval + abstain rules):
python chatBot/scripts/run_rag_query.py --stream "What methods appear in the corpus?"
```

- **Code:** [`backend/app/baseline_rag.py`](backend/app/baseline_rag.py) — `retrieve_chunks`, `answer_question`, `stream_rag_answer` (vector search + Ollama OpenAI-compatible chat; optional streaming).  
- **Notebooks:** RAG settings use **env getters** (`get_ollama_chat_model()`, etc.) so a stale Jupyter `config` object does not break chat model / DB name / `RAG_*` after you edit `.env`. The `01_baseline_rag` notebook calls `load_dotenv(..., override=True)` first.

Answers only cover **ingested** PDFs (e.g. pilot subset until you run full ingest).

## Repo layout (chatBot/)

- `backend/app/` — config, Neo4j client, schema DDL, **pilot ingest**, embeddings, **baseline RAG**
- `cypher/schema_ddl.cypher` — generated DDL for Browser (regen via `scripts/generate_schema_ddl_cypher.py`)
- `notebooks/00_intro_and_setup.ipynb` — env + connectivity + Phase 3 pilot
- `notebooks/01_baseline_rag.ipynb` — Phase 4 RAG demo
- `planning/` — phases, schema doc, tech stack, evaluation questions
- `resources/` — PDF corpus, optional reference data (see `resources/README.md`)