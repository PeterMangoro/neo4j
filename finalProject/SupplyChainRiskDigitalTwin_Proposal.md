# Brainstorming Template (Proposal) — Topic #1

## Topic #1: Supply Chain Risk Digital Twin (Neo4j + Cypher + GDS)

This project builds a **graph-based “digital twin”** of a supply chain using a supply-chain risk and performance dataset. The goal is to represent suppliers, products, and supplier geography as a knowledge graph and then use **Cypher** and **Neo4j Graph Data Science (GDS)** to identify **high-risk suppliers**, **risk-concentrated products** (single points of failure), and **risk clusters** by geography. The desired outcome is an interpretable, network-based view of supply chain vulnerability that supports scenario-style questions such as “which suppliers/products should be prioritized for mitigation?” and “where are systemic risks concentrated?”. The solution will be implemented in Neo4j (Desktop), queried in Cypher, and analyzed with at least one GDS workflow in a Jupyter Notebook deliverable.

---

## Impact

- **Operational impact**: Helps prioritize supplier risk mitigation (e.g., diversification, audits, buffer inventory) by highlighting supplier/product nodes that concentrate high delay/disruption risk.
- **Business impact**: Supports better sourcing decisions and reduced disruption costs by identifying “critical” suppliers (network centrality) and high-risk supplier communities.
- **Analytical impact**: Demonstrates how graph modeling improves explainability for supply chain risk compared to purely tabular views (relationships are the signal).

---

## Project Goals

- **Learning goal**: Demonstrate competence in building a knowledge graph in Neo4j and answering graph EDA questions using Cypher.
- **Project goal**: Create a supplier–product–country graph model and produce an analytic notebook with interpretable risk insights (rankings, segments/clusters, and vulnerability patterns).
- **GDS goal (minimum)**: Execute at least one GDS algorithm end-to-end (projection → estimate → run → interpret) to identify critical nodes or clusters in the supply chain risk network.

---

## Literature Review / Environmental Scan / Market Research

Provide at least three sources related to supply chain risk and graph/network methods:

1. Neo4j Graph Data Science Documentation (algorithms and workflow):  
   `https://neo4j.com/docs/graph-data-science/current/`

2. Supply chain resilience overview (background + motivations):  
   Ivanov, D. (2020). “Viable supply chain model…” (resilience under disruptions).  
   `https://doi.org/10.1016/j.ijpe.2020.107747`

3. Network science perspective on supply chains / systemic risk:  
   (General reference for using network structure to study systemic vulnerabilities.)  
   Barabási, A.-L. (2016). *Network Science* (open online book).  
   `http://networksciencebook.com/`

Optional additional sources (if needed):
- Neo4j Cypher manual: `https://neo4j.com/docs/cypher-manual/current/`
- Community detection background: `https://neo4j.com/docs/graph-data-science/current/algorithms/louvain/`

---

## Datasets

Primary dataset (selected for the graph build):

- **Supply Chain Risk and Performance Indicators (with supplier country)**  
  Kaggle link: `https://www.kaggle.com/datasets/natasha0786/supply-chain-dataset/data`  
  Local file: `finalProject/dynamic_supply_chain_logistics_dataset_with_country.csv`  
  Notes:
  - ~113k rows
  - Contains stable identifiers: `supplier_id`, `product_id`, `supplier_country`
  - Contains risk/performance metrics: `delay_probability`, `disruption_likelihood_score`, `risk_classification`, `lead_time_days`, `shipping_costs`, `delivery_time_deviation`, etc.

---

## Design concepts

The design is a **knowledge graph** that models how suppliers connect to products and how supplier geography relates to risk outcomes. Rather than analyzing each row as an isolated “instance,” the graph emphasizes **shared suppliers and shared products**, enabling network-style insights such as dependency concentration (many products tied to a few suppliers) and risk clustering (groups of suppliers with similar risk profiles and shared product coverage). The output will include Cypher-based EDA, deeper analytical queries, and at least one GDS-based ranking or clustering result with narrative interpretation.

---

## Conceptual architecture

- **Services/tools**
  - Neo4j Desktop (local DBMS)
  - APOC (schema exploration convenience)
  - Neo4j Graph Data Science (GDS)
  - Jupyter Notebook + Python driver (or `graphdatascience` client) for reproducible execution and charts

- **Data + database considerations**
  - Create uniqueness constraints for `:Supplier(id)` and `:Product(id)` to ensure clean MERGE ingestion.
  - Store row-level risk metrics primarily on relationships `(:Supplier)-[:SUPPLIES]->(:Product)` to represent the risk/performance of that supplier–product pairing.
  - Create `:Country(name)` nodes and connect suppliers via `(:Supplier)-[:LOCATED_IN]->(:Country)` for geography-based analysis.

- **Processing/server architecture**
  - Local single-node Neo4j instance is sufficient (dataset size is moderate).
  - Use batching in `LOAD CSV` to avoid memory spikes.

- **Presentation layer**
  - Notebook tables + plots (bar charts of risk by country, top-k supplier rankings)
  - Optional Neo4j Browser/Bloom screenshots for a small subgraph (high-risk suppliers and their products).

---

## Analytical Design

- **Metrics and signals**
  - Supplier risk: mean/median `delay_probability`, mean `disruption_likelihood_score`, distribution of `risk_classification`
  - Product exposure: number of distinct suppliers per product (dependency diversification) and risk-weighted exposure
  - Geography: aggregate risk by `supplier_country`
  - Network criticality: centrality scores (e.g., degree/PageRank/betweenness) in projections such as Supplier–Product or Supplier–Supplier similarity

- **Audience**
  - Supply chain analysts / operations leadership (risk mitigation planning)
  - Data/analytics stakeholders evaluating where to invest in resilience improvements

- **Outputs and display**
  - Ranked lists (top risky suppliers, most exposed products, highest-risk countries)
  - Distribution plots (risk classification mix by country; supplier reliability vs delay probability)
  - GDS outputs (top nodes by centrality; communities with risk profiles)

Example question set (for the final project notebook):
- **EDA (≥8)** examples:
  - Counts of nodes/relationships after ingestion; distinct labels and rel types
  - How many suppliers, products, countries?
  - Top 10 suppliers by number of products supplied
  - Risk classification distribution overall and by country
  - Summary stats of `lead_time_days`, `shipping_costs`, `delay_probability`
  - Products with the fewest suppliers (single-sourcing risk)
  - Countries with highest average disruption likelihood
  - Correlation-style inspection: supplier reliability vs delay probability (bucketed)

- **Deeper Cypher (Option 1: ≥4)** examples:
  - Identify “critical suppliers”: suppliers that supply many products AND have high delay/disruption metrics
  - Identify “high-exposure products”: products whose supplier set is small and/or skewed toward high-risk suppliers
  - Country vulnerability: countries where high-risk suppliers dominate critical products
  - Risk concentration: find product groups that share many of the same suppliers (dependency clusters)

- **GDS (Option 2: ≥1 algorithm)** candidate:
  - **PageRank** or **Degree** on a projected Supplier–Product graph (or Supplier–Supplier co-supply graph) using `delay_probability` or `shipping_costs` as weights, to rank the most “influential/critical” suppliers in the dependency network.
  - Alternative: **Louvain** community detection to find clusters of suppliers/products; compare community risk profiles.

---

## Data Exchange/Processing Framework

- **Processing steps**
  1. Validate CSV schema and data types (numeric parsing, categorical fields).
  2. Ingest into Neo4j using `LOAD CSV WITH HEADERS`:
     - `MERGE` suppliers, products, countries
     - `MERGE`/`CREATE` `SUPPLIES` relationships with risk/performance properties
  3. Run EDA queries to verify schema correctness and scale.
  4. Run deeper Cypher questions and capture outputs.
  5. Run at least one GDS workflow (estimate → run → interpret), write results back (optional), and report findings.

- **Data flow**
  CSV → Neo4j (constraints + ingestion) → Cypher EDA/analytics → GDS projection/algorithm → Notebook tables/plots + interpretation.

---

## Additional Comments

- The dataset is “instance-based,” so the graph model will treat each row as evidence of a supplier–product relationship with associated risk/performance properties. Where multiple rows exist per supplier–product pair, relationship properties will be aggregated (e.g., mean delay probability, mean disruption likelihood, count of observations).
- This topic is designed to be deliverable within the capstone timeline while still producing a professional, interpretable graph analytics artifact aligned with supply chain resilience themes.

---

## References and Hyperlinks

- Neo4j Graph Data Science docs: `https://neo4j.com/docs/graph-data-science/current/`
- Neo4j Cypher manual: `https://neo4j.com/docs/cypher-manual/current/`
- Kaggle dataset: `https://www.kaggle.com/datasets/natasha0786/supply-chain-dataset/data`
- Barabási, A.-L. Network Science (open book): `http://networksciencebook.com/`
- Ivanov (2020) supply chain resilience paper (DOI): `https://doi.org/10.1016/j.ijpe.2020.107747`

