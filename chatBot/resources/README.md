# `resources/` — data files for the GraphRAG project

## PDF corpus

- **`PublicationsforAndy/`** — project PDFs (Prof. Devreotes publications). This is the **only** allowed answer-evidence source for the chatbot.

## HGNC (human gene nomenclature) — optional reference

- **File:** `hgnc_complete_set.txt` (not committed; see repo root `.gitignore`)
- **Purpose:** Offline **lexicon** for normalizing human **gene symbols** and aliases when you build GraphRAG **`Entity`** nodes (`type`: `Gene` / `Protein`) — merge duplicates, validate symbols, optional stable IDs on nodes.
- **Does not replace** chunk retrieval or PDF evidence; answers must still cite **chunks/papers**.

### Download

Official complete set (tab-separated):

```bash
curl -fsSL "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt" \
  -o chatBot/resources/hgnc_complete_set.txt
```

### Columns (high level)

Includes `hgnc_id`, `symbol`, `name`, `status`, `alias_symbol`, `prev_symbol`, `entrez_id`, `ensembl_gene_id`, and others — see the header row in the file.

### Attribution / terms

HGNC is curated by the [HUGO Gene Nomenclature Committee](https://www.genenames.org/). Use their data according to [Genenames.org](https://www.genenames.org/) terms and citation guidance when you publish or ship a demo.

### Implementation note

No loader is required until **Phase 5** (entity extraction + normalization). When implemented, prefer building a symbol/alias → row index in memory or a small SQLite sidecar; optional Neo4j properties are documented in `planning/GraphRAG_Schema_v1.md`.
