# Capstone — Graph-based hybrid movie recommender

This folder is the **movie recommender capstone**: a small **user–movie** dataset in **Neo4j**, enriched with **genre** and **director** as graph nodes, then **Graph Data Science (GDS)** pipelines for similarity, embeddings, hybrid scoring, and community detection.

**Team:** Bekithemba Nkomo, Peter Mangoro, Masheia Dzimba (see notebooks for full attribution).

## What it was about

We built a **hybrid recommender** on top of a property graph instead of a flat utility matrix. We **loaded and enriched** users, movies, and ratings from CSV, then walked through **EDA**, **analytical questions**, and **GDS**: comparing **Jaccard-style** overlap with **FastRP + kNN**, layering **content signals** (genre, director) on top of collaborative edges, and using **Louvain** to surface taste communities. We worked in **Jupyter** with the **Python driver** and **pandas**, with `NEO4J_*` env vars for the database connection—same pattern as [Assignment 2](../ass2/README.md), but tuned for recommendation experiments and extensions (cold-start, cutoff sensitivity, director affinity, etc.).

## Key takeaways

- We learned that **materializing `Genre` and `Director` as nodes** (not just movie properties) made hybrid and explainable paths natural: traverse shared genres or directors when collaborative overlap is thin.
- **Sparsity dominated the toy dataset** (~20 users, ~25 movies, ~101 ratings), so we had to be honest about what similarity and kNN could estimate—and where **content-based hops** helped cold-start–style cases.
- **GDS projections** were the hinge between “nice Cypher” and algorithms: we had to choose **node sets, relationship types, and sometimes weights** carefully before `gds.*` calls matched our intent.
- **Jaccard vs FastRP + kNN** behaved differently when ratings carried **magnitude** and disagreement; comparing them in the notebook grounded our narrative in actual numbers, not only definitions.
- **Louvain on a user–user similarity view** gave us interpretable **communities of taste** that complemented top-N recommendation lists.

## Main deliverables

| Artifact | Description |
|----------|-------------|
| [P_Mangoro_recommender_project.ipynb](P_Mangoro_recommender_project.ipynb) | Full capstone: load, EDA, analytics, GDS, hybrid recommender, extensions, references |
| [Movie_Recommender_Approach.ipynb](Movie_Recommender_Approach.ipynb) | Earlier **approach / plan** notebook (layered methodology, graph design rationale) |
| [recommenderSummary.pdf](recommenderSummary.pdf) | Summary export (source: `recommenderSummary.odt`) |
| [Movie_Recommender_Project-1.pdf](Movie_Recommender_Project-1.pdf) | Project brief / rubric-style PDF from the course |

## Data files (CSV)

| File | Contents |
|------|----------|
| [users.csv](users.csv) | `userId`, demographics (age, gender, occupation, …) |
| [movies.csv](movies.csv) | `movieId`, title, year, genres, director, `avgRating`, … |
| [ratings.csv](ratings.csv) | `userId`, `movieId`, `rating`, `timestamp` |

Import paths in the notebook assume Neo4j can read these files (e.g. from the DB **import** directory or `file:///` URLs you configure).

## Graph model (summary)

- **Nodes:** `User`, `Movie`, `Genre`, `Director` (with constraints on ids/names as in the notebook).
- **Relationships:** `(:User)-[:RATED {rating, timestamp}]->(:Movie)`, `(:Movie)-[:IN_GENRE]->(:Genre)`, `(:Movie)-[:DIRECTED_BY]->(:Director)`.

## Prerequisites

- **Neo4j** with the **GDS** library installed (for algorithm sections).
- **Python 3** with `neo4j`, `pandas`, `jupyter` (versions as used in the notebook).
- Environment variables: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.

## Related coursework

- [Assignment 1](../ass1/README.md) — building a graph from CSVs (constraints, `MERGE`, load order).
- [Assignment 2](../ass2/README.md) — Cypher + GDS on a healthcare graph.
- Repository overview: [root README](../../README.md).
