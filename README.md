# Neo4j capstone workspace

This repository bundles Neo4j and graph-related coursework, Graph Academy exercises, and a capstone-style **GraphRAG** application. Each section below gives a **short summary** of what the linked README covers; open the README for setup, file lists, and full detail.

## Devreotes Lab Research Chatbot

**Summary (from [DevreotesLabResearchChatbot/README.md](DevreotesLabResearchChatbot/README.md)):** GraphRAG Q&A over a PDF corpus—papers and chunks in **Neo4j** with **vector search** on chunk embeddings; **OpenAI** produces grounded answers with citations. Optional **Nuxt** UI under `nuxt/`. Prerequisites include Python 3.12+, Neo4j (local or Aura), and API keys documented in `.env.example`.

- Setup and run: [DevreotesLabResearchChatbot/README.md](DevreotesLabResearchChatbot/README.md)
- Architecture and usage (plain-language, full system diagram): [ARCHITECTURE_AND_USAGE.md](ARCHITECTURE_AND_USAGE.md)

Copy `.env.example` to `.env` in that project and set `NEO4J_*` and `OPENAI_API_KEY` as documented there.

## Final project (`finalProject/`)

**Summary (from [finalProject/readme.md](finalProject/readme.md)):** Self-defined capstone for a **multi-echelon automotive supply-chain knowledge graph** in Neo4j—**Cypher** exploration and **GDS** for dependencies, bottlenecks, and risk-style questions. The **Moetz et al. (2020)** workbook drives the data model; [Brainstorming_Template.ipynb](finalProject/Brainstorming_Template.ipynb) captures the proposal, impact, and research questions. [selfDefinedProject.md](finalProject/selfDefinedProject.md) lists official minimum requirements (EDA count, deeper questions, GDS option).

- Environment and contents: [finalProject/readme.md](finalProject/readme.md)

## Assignments (`assignments/`)

### Assignment 1 — `ass1/`

**Summary (from [assignments/ass1/README.md](assignments/ass1/README.md)):** Build a **Chinook-style music graph** from CSV: schema design, constraints, **dependency-ordered** `LOAD CSV` / `MERGE`, relationships (including **Composer** as nodes), indexes, validation, and **six graded Cypher queries**. Write-up and queries live in `P_Mangoro_C1_assn.ipynb`.

- Full guide: [assignments/ass1/README.md](assignments/ass1/README.md)

### Assignment 2 — `ass2/`

**Summary (from [assignments/ass2/README.md](assignments/ass2/README.md)):** Analyze a **FAERS-style healthcare graph** restored from `**healthcare-analytics-50.dump`**: iterative **Cypher EDA** (schema discovery), deeper analytical questions, then **GDS** (projections, algorithms, interpretation). Jupyter + Python driver + **pandas**; dump may be gitignored—see folder README.

- Full guide: [assignments/ass2/README.md](assignments/ass2/README.md)

### Recommender capstone — `recommender/`

**Summary (from [assignments/recommender/README.md](assignments/recommender/README.md)):** **Hybrid movie recommender** on a sparse user–movie graph: **genre** and **director** as nodes for content + collaborative signals; **GDS** compares **Jaccard**-style similarity with **FastRP + kNN**, hybrid scoring, **Louvain** communities, and extensions (cold-start, cutoffs, etc.). Team project; main notebook `P_Mangoro_recommender_project.ipynb`.

- Full guide: [assignments/recommender/README.md](assignments/recommender/README.md)

## Graph Academy (`graphAcademy/`)

### `genaiFundamentals/`

**Summary (from [graphAcademy/genaiFundamentals/README.adoc](graphAcademy/genaiFundamentals/README.adoc)):** Course companion for [Neo4j & Generative AI Fundamentals](https://graphacademy.neo4j.com/courses/genai-fundamentals/) on Graph Academy—exercises and tests (Neo4j with `recommendations` dataset, embeddings/vector index setup, `pytest`). See the AsciiDoc file for Codespaces and test steps.

- Course README: [graphAcademy/genaiFundamentals/README.adoc](graphAcademy/genaiFundamentals/README.adoc)

### `demo_supply_chain/`

**Summary (from [graphAcademy/demo_supply_chain/README.md](graphAcademy/demo_supply_chain/README.md)):** Neo4j **pharmaceutical supply chain** demo—product flow, supplier dependencies, API links, risk and bottleneck patterns; upstream instructions on [neo4j.com developer demos](https://neo4j.com/developer/demos/supply_chain-demo). The [walkthrough README](graphAcademy/demo_supply_chain/walkthrough/README.md) walks use cases, queries, and AI-agent exploration.

- Demo README: [graphAcademy/demo_supply_chain/README.md](graphAcademy/demo_supply_chain/README.md)

Additional PDFs in `graphAcademy/` are reference material for those courses.



