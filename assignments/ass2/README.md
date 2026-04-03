# Assignment 2 — Analyzing a Neo4j graph with Cypher + GDS

This folder holds **Course 2 / Capstone Assignment 2**: explore and analyze a **healthcare (FAERS-inspired)** graph in Neo4j using **Cypher**, then apply **Graph Data Science (GDS)** procedures.

## What it was about

I worked on a **FAERS-style healthcare graph** (drugs, cases, reactions, outcomes, and related entities) that I **restored from a Neo4j dump**, then I **explored it in three passes**: broad **Cypher EDA** to learn what labels, properties, and relationships actually existed; **deeper analytical questions** with richer patterns and aggregations; and finally **GDS**—projecting subgraphs into the graph catalog and running algorithms where the brief called for similarity or structural analysis. I drove most of the work from **Jupyter** with the **Python driver** and **pandas** so I could iterate on queries and keep results in tables I could interpret and paste back into the write-up.

## Key takeaways

- I could not rely on a perfect data dictionary, so I **discovered the schema as I queried**: start wide (`MATCH` / counts / `LIMIT`), note what comes back, then tighten filters and joins once I trusted names and directions.
- **Cypher first, GDS second** made sense: once I understood how cases tied to drugs and reactions, I knew what to **project** and which algorithm actually matched the question instead of running GDS in the dark.
- **GDS is a different workflow** from ad-hoc reads: I had to think in terms of **projections**, possibly undirected or weighted views, dropping or recreating graphs when I changed my mind, and reading algorithm output back into my narrative.
- From Python I learned to treat **`NEO4J_URI` / user / password** as prerequisites for every session and to wrap repeated **`session.run`** patterns so exploratory cells stayed short and consistent.
- For **node similarity**, I compared options (neighbor-based vs KNN / property-heavy approaches) in my notes so I could justify **which GDS path** fit “similar drugs” or “similar cases” in this graph—see [cursor_node_algorithms_.md](cursor_node_algorithms_.md).

## Main deliverable

- **[P_Mangoro_C2_assn.ipynb](P_Mangoro_C2_assn.ipynb)** — approach, exploratory queries, analytical questions, and GDS workflows (runs against a live Neo4j database via the Python driver).

## Dataset

- **[healthcare-analytics-50.dump](healthcare-analytics-50.dump)** — Neo4j database dump to **restore** into your instance (Neo4j Admin `load` / `neo4j-admin database load`, or your Neo4j version’s equivalent). The graph models FDA Adverse Event Reporting System (FAERS)–style entities.

**Node types** (as used in the notebook) include: `Drug`, `Case`, `Reaction`, `ReportSource`, `Outcome`, `Therapy`, `Manufacturer`, `AgeGroup`. Relationship types are discovered through EDA in the notebook.

> The repo `.gitignore` may exclude `*.dump` files; if the dump is missing after clone, obtain it from course materials or regenerate from the assignment source.

## Reference

- **[Analyzing a Neo4j Graph Database via Cypher + GDS.pdf](Analyzing%20a%20Neo4j%20Graph%20Database%20via%20Cypher%20%2B%20GDS.pdf)** — assignment brief / rubric

## Running the notebook

1. Restore **`healthcare-analytics-50.dump`** into Neo4j and start the DB.
2. Install Python deps (e.g. `neo4j`, `pandas`, `jupyter`) in your environment.
3. Export connection settings:

   - `NEO4J_URI` (e.g. `bolt://localhost:7687`)
   - `NEO4J_USER`
   - `NEO4J_PASSWORD`

4. Ensure the **GDS library** is available on the server if you run GDS cells (`CALL gds.*`).

## Prerequisites

- **Neo4j** with the healthcare graph loaded from the dump
- **Neo4j GDS** plugin (for graph algorithm sections)
- **Python 3** + Jupyter (or VS Code) for `P_Mangoro_C2_assn.ipynb`

Repository overview: [root README](../../README.md). Assignment 1 (graph build): [../ass1/README.md](../ass1/README.md).
