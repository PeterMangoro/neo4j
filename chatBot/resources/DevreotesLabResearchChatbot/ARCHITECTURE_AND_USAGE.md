# Devreotes Lab Research Chatbot — Architecture & Usage (Plain-English Guide)

This document explains **what the system does**, **how the pieces connect**, **what lives in the graph database**, **which technologies are used and why**, and **how to run the project**. It is written so non-specialists can follow along; technical terms are introduced with everyday analogies.

---

## 1. What problem does this solve?

Imagine a **stack of PDF research papers** from Prof. Peter Devreotes’ lab. A user asks a question in natural language, for example: *“Which papers talk about PTEN?”* or *“What are the most-mentioned genes across the corpus?”*

The system must:

1. **Stay grounded** — answers should come from *those papers*, not from the model’s general internet-like knowledge.
2. **Point to evidence** — answers cite numbered passages (chunks) so readers can verify.
3. **Use the right “lens”** — sometimes the best answer is *semantic search*, sometimes *filter by gene or author*, sometimes a *simple statistic* over the graph.

This project implements **GraphRAG**: a **graph** (Neo4j) stores papers, chunks, genes, authors, and optional entities; **retrieval** finds relevant text; a **large language model (LLM)** writes the final answer using only what was retrieved.

---

## 2. Big picture: flow from PDF to answer

Think of the pipeline like a **library with a smart index**:

| Stage | Plain analogy |
|--------|----------------|
| **PDFs on disk** | Books on a shelf (`papers/`) |
| **Text extraction** | Typing each book into plain text (`extracted/*.json`) |
| **Neo4j graph** | Card catalog + cross-references: which paper, which chunk, which gene |
| **Embeddings** | “Semantic sticky notes” on each chunk so *similar meaning* can be found by vector search |
| **Question → route** | Librarian decides: *gene shelf*, *author shelf*, *statistics*, or *general similarity* |
| **LLM** | A careful writer who may only quote from the pages you slid across the desk |

```mermaid
flowchart LR
  subgraph ingest["Offline: build the library"]
    PDF[papers/*.pdf]
    EXT[extract_pdfs.py]
    JSON[extracted/*.json]
    ING[ingest_papers.py]
    NEO[(Neo4j graph)]
    EMB[create_embeddings.py]
    PDF --> EXT --> JSON --> ING --> NEO
    NEO --> EMB
  end
  subgraph online["Online: answer a question"]
    Q[User question]
    R[router.py]
    RET[retrieval.py]
    CB[chatbot.py + OpenAI]
    Q --> R --> RET --> CB --> A[Answer + citations]
  end
  NEO --> RET
```

---

## 3. Step-by-step: what runs when (offline vs online)

### A. Offline — “building the library” (run once, then again when you change rules or papers)

1. **HGNC gene dictionary** (`run_download_hgnc.py`)  
   - **Layman:** A standard **phone book for human gene symbols** (official symbols and aliases).  
   - **Why:** So when text says “PTEN” or an alias, we link to **one** canonical gene node instead of guessing.

2. **Extract PDFs** (`run_extract_pdfs.py`)  
   - Reads each PDF, pulls text and best-effort metadata (title, DOI, year, journal hints, PDF author/subject when present).  
   - **Layman:** OCR-free **photocopying the words** into JSON files under `extracted/`.

3. **Neo4j schema** (`run_setup_schema.py`)  
   - Creates **unique IDs** and **indexes** (including a **vector index** on chunk embeddings).  
   - **Layman:** Library **rules** (“every chunk has one ID”) and a **fast index** for search.

4. **Ingest** (`run_ingest_papers.py`)  
   - Creates **Paper**, **Chunk**, links genes and authors, optional **Claim** snippets, and **Entity** nodes for genes/authors as used in the original design.  
   - **Layman:** **Filing cards**: this paper has these paragraphs; these paragraphs mention these genes.

5. **Embeddings** (`run_create_embeddings.py`)  
   - Computes a **vector** (list of numbers) per chunk using a biomedical sentence model.  
   - **Layman:** Each paragraph gets a **fingerprint of meaning**, so “chemotaxis” and “cell movement” can match even if words differ.

6. **Optional: LLM graph enrichment** (`run_llm_graph_extract.py`)  
   - Calls a small/cheap model to label **topics, pathways, methods**, etc., and optional relationships.  
   - **Layman:** A **second pass of highlighting** with structured labels—not required for basic Q&A.

### B. Online — “asking the library a question”

1. User submits a question (Gradio `app.py` or Nuxt UI → Python **bridge** → `chatbot.py`).
2. **Router** (`router.py`) classifies: *themes / author / gene / semantic*.
3. **Retrieval** (`retrieval.py`) runs vector search and/or Cypher filters (e.g., only chunks from papers that *mention* gene X).
4. **Chatbot** (`chatbot.py`) builds a prompt: system rules + numbered passages + user question; the **LLM** streams or returns an answer with `[1]`, `[2]`-style citations.

---

## 4. Graph: main nodes and relationships

Neo4j stores **nodes** (things) and **relationships** (edges). Below is the **mental model** this project uses.

### Nodes (the “nouns”)

| Label | Plain meaning | Typical properties |
|--------|----------------|----------------------|
| **Paper** | One publication in the corpus | `paper_id`, `title`, `filename`, optional `doi`, `year`, `journal`, PDF metadata hints |
| **Chunk** | A slice of text from a paper (searchable unit) | `chunk_id`, `text`, `chunk_index`, **embedding** (vector) |
| **Gene** | A human gene from HGNC | `hgnc_id`, `official_symbol` |
| **Author** | A person (as extracted) | `author_key`, `name` |
| **Entity** | Generic tagged concept (gene/topic/author as entity, etc.) | `entity_key`, `type`, `name` |
| **Claim** | A short extracted sentence-like unit (for grounding) | `claim_id`, `text` |

### Relationships (the “verbs”)

| Pattern | Plain meaning |
|---------|----------------|
| `(:Paper)-[:HAS_CHUNK]->(:Chunk)` | This paper **contains** this paragraph. |
| `(:Author)-[:AUTHORED]->(:Paper)` | This person **wrote** this paper. |
| `(:Paper)-[:MENTIONS]->(:Gene)` | This paper **mentions** this gene (corpus-level link). |
| `(:Chunk)-[:MENTIONS]->(:Entity)` | This paragraph **mentions** this entity (chunk-level). |
| `(:Paper)-[:HAS_TOPIC]->(:Entity)` | Paper-level **topic** link (e.g., for “Topic” entities). |
| `(:Entity)-[:RELATED_TO]->(:Entity)` | Optional **semantic link** between entities (Phase 5). |
| `(:Claim)-[:SUPPORTS]->(:Chunk)` | A short claim **supported by** this chunk. |

**Layman analogy:**  
- **Paper** = book. **Chunk** = page or paragraph. **Gene/Author** = index entries. **Embedding** = invisible tag that helps “find similar paragraphs.”

---

## 5. Tech stack — what each part is and why it was chosen

| Piece | Role | Why it fits this project |
|--------|------|---------------------------|
| **Neo4j** | Graph database | Papers, chunks, and “mentions” are naturally **networks**. Cypher can **filter by gene/author** and combine with vector search. |
| **PyMuPDF (`fitz`)** | PDF text extraction | Fast, local, no cloud OCR required for text-based PDFs. |
| **scispaCy + `en_core_sci_lg`** | Biomedical NLP | Good at spotting **gene-like spans** in running text during ingest. |
| **HGNC JSON** | Gene normalization | **Community standard** for human gene symbols and aliases—reduces duplicate or wrong gene nodes. |
| **SentenceTransformers + PubMed-tuned model** | Chunk embeddings | **Same embedding space** for question and chunks → meaningful cosine / vector index similarity in biomedicine. |
| **Neo4j vector index** | Approximate nearest-neighbor search | Lets you ask “what passages are *semantically* closest to my question?” at scale. |
| **LangChain + OpenAI (`gpt-4o`)** | Answer generation | Strong instruction-following for **citations** and **refusal** when context is weak. |
| **Gradio (`app.py`)** | Quick local UI | Minimal setup for demos and debugging without a JS build. |
| **Nuxt + AI SDK + Nuxt UI** | Production-style chat UI | **Streaming** answers, modern UX, CSRF-aware API routes. |
| **Python bridge (`devreotes_bridge.py`)** | Subprocess from Node | Reuses the **same** `chatbot.py` logic for the Nuxt app without rewriting retrieval in TypeScript. |

Nothing here is “magic”: each tool solves one layer—**storage**, **text**, **biology naming**, **meaning vectors**, **routing**, **generation**, **UI**.

---

## 6. The “organs” of the system (how they work together)

### Router (`router.py`)

- **Job:** Guess *what kind of question* this is.  
- **Layman:** The **receptionist** who sends you to “gene desk,” “author desk,” “statistics desk,” or “general reading room.”  
- **Why it matters:** Asking “which kinases are *most mentioned*?” should not be treated the same as “what does *PTEN* do in chemotaxis?”—different desks, different tools.

### Retrieval (`retrieval.py`)

- **Job:** Return ranked **chunks** (and sometimes aggregate **gene counts**).  
- **Layman:** The **librarian** who pulls books off the shelf *and* photocopies the right pages.  
- **Extras:** Per-paper diversity (not ten chunks from one paper), optional rerank, optional **graph expansion** (extra chunks in the same paper that share extracted entities).

### Chatbot (`chatbot.py`)

- **Job:** If confidence is too low, **say so**; otherwise assemble context and call the LLM.  
- **Layman:** The **editor**: you only get an article built from supplied quotes, with citation numbers.

### Optional Phase 5 (`llm_chunk_extract.py`)

- **Job:** Add richer **Entity** nodes and relationships from LLM JSON.  
- **Layman:** Optional **second round of indexing** for topics and links—not required for baseline Q&A.

---

## 7. Two ways to use the UI

| Interface | Command | Audience |
|-----------|-----------|----------|
| **Gradio** | `python app.py` | Fast local demo, single-user. |
| **Nuxt** | `cd nuxt-chat-interface && pnpm dev` | Richer chat UI, **streaming** responses; set `DEVREOTES_PYTHON` to your venv’s `python` if needed. |

Both ultimately call the same Python **brain** (`backend/app/chatbot.py`) for answers.

---

## 8. Usage checklist (short)

1. Copy `.env.example` → `.env` and set **Neo4j** and **OpenAI** keys.  
2. Run scripts in order: **HGNC → extract → schema → ingest → embeddings** → *(optional)* **LLM extract**.  
3. Start **Gradio** or **Nuxt** as above.

Full command list and environment table: see **`structure.md`** in this folder.

---

## 9. End-to-end example (layman walkthrough)

**Question:** *“What does the corpus say about PTEN?”*

1. **Router** notices “PTEN” and gene-related language → **gene route** (if PTEN resolves in HGNC).  
2. **Retrieval** finds chunks from papers whose graph says they **mention PTEN**, ranked by **vector similarity** to the question.  
3. **Chatbot** builds a prompt: numbered excerpts only.  
4. **LLM** answers and cites `[1]`, `[2]` matching those excerpts.  
5. If nothing clears the minimum similarity score, the system **abstains** instead of inventing facts—by design.

**Question:** *“Which genes appear in the most papers?”*

1. **Router** sends this toward the **themes** path (gene-mention **counts** over the graph).  
2. **Retrieval** returns a **table-like summary** (genes × paper counts), not long prose from one paper.  
3. The LLM is instructed **not** to invent qualitative “themes” beyond those counts.

---

## 10. Design principles (why things are the way they are)

1. **Corpus-grounded:** The LLM is a **writer**, not the **source of truth**—the graph and chunks are.  
2. **Explainable:** Chunks and scores can be inspected; citations tie answers to **specific text**.  
3. **Biomedical realism:** HGNC + scispaCy + PubMed-flavored embeddings match how **genes and papers** are discussed.  
4. **Pragmatic graph:** Not every possible ontology is modeled—only what helps **search**, **filters**, and **stats** for this capstone scope.

---

## 11. Where to look in the repo

| Topic | Location |
|--------|----------|
| Extract PDFs | `backend/app/extract_pdfs.py` |
| Ingest / graph writes | `backend/app/ingest_papers.py` |
| Schema / indexes | `backend/app/setup_schema.py` |
| Embeddings | `backend/app/create_embeddings.py` |
| Search & routes | `backend/app/retrieval.py`, `backend/app/router.py` |
| Q&A + streaming path | `backend/app/chatbot.py` |
| Nuxt → Python | `nuxt-chat-interface/server/python/devreotes_bridge.py` |
| Env template | `.env.example` |
| Run order | `structure.md` |

---

*This guide reflects the Devreotes Lab Research Chatbot layout under `backend/app/` and the Nuxt bridge. If you change ingest rules or schema, re-run the offline pipeline so the database matches the code.*
