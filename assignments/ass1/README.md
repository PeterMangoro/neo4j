# Assignment 1 — Design & build a Neo4j knowledge graph

This folder holds **Course 1, Assignment 1**: import Chinook-style relational data into **Neo4j**, define constraints and relationships, validate the graph, and answer required questions with **Cypher**.

## What it was about

I **designed a graph schema** for a music store from Chinook-style CSVs, **loaded the data in dependency order** using Cypher (`LOAD CSV`, `MERGE`, and explicit typing), then **connected** artists, albums, tracks, genres, media types, and composers with the relationships the domain implied. I **checked** the structure in the browser and wrote **six required read queries** to show the model answered the assignment. For me, this was the full path from relational tables to a property graph I could actually traverse and query.

## Key takeaways

- I learned to **decide the model and constraints before bulk loading**: picking labels, relationship types, and stable IDs, then adding **uniqueness constraints** early so `MERGE` stayed idempotent and I did not accumulate duplicate nodes on re-runs.
- I saw that **load order is not optional**: I put reference and independent entities first and only then albums, tracks, and relationship creation—otherwise matches fail or I would have to patch the graph afterward.
- **Real CSVs pushed back**: I had to handle **missing composer values**, **fields that contained commas inside quotes**, and **case-sensitive** string filters where a small capitalization mismatch broke a query.
- After constraints, I added **indexes** on the names and titles I filtered on most, which kept both exploration and the graded queries from feeling sluggish.
- I **promoted composer from a track property to `Composer` nodes** linked with `COMPOSED_BY`, which made reuse and querying clearer than leaving composer as a bare string on every track.

## Main deliverable

- **[P_Mangoro_C1_assn.ipynb](P_Mangoro_C1_assn.ipynb)** — write-up (approach, schema, load order, challenges) and executable Cypher via the notebook.

## Data files (CSV)

Source tables for the graph:

| File | Role |
|------|------|
| [Artist.csv](Artist.csv) | Artist nodes |
| [Album.csv](Album.csv) | Album nodes |
| [Track.csv](Track.csv) | Track nodes and composer text (used to derive Composer nodes) |
| [Genre.csv](Genre.csv) | Genre nodes |
| [MediaType.csv](MediaType.csv) | MediaType nodes |

Place CSVs where your Neo4j instance can read them (e.g. `import/` folder) and use `LOAD CSV WITH HEADERS` as in the notebook.

## Graph model

- Nodes: `Artist`, `Album`, `Track`, `Genre`, `MediaType`, `Composer`
- Relationships: e.g. `RELEASED`, `CONTAINS`, `IN_GENRE`, `OF_MEDIA_TYPE`, `COMPOSED_BY` (see the notebook for the full specification)

## Reference and extras

- **[Neo4j Design  + Build + Query.pdf](Neo4j%20Design%20%20+%20Build%20+%20Query.pdf)** — assignment/reference PDF
- Screenshots (`*.png`), walkthrough video (`*.mp4`), and `DETAILED_VIDEO_SCRIPT.md` may be present for documentation or submission; some of these are listed in the repo `.gitignore` and might not appear in every clone.

## Prerequisites

- A running **Neo4j** instance (Browser or Aura) with import access to the CSV paths you configure
- Jupyter or VS Code with a notebook kernel if you want to run cells from the `.ipynb` locally

Repository overview: [root README](../../README.md).
