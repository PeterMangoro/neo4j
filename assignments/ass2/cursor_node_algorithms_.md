# Node similarity algorithms in Neo4j
_Exported on 3/1/2026 at 16:11:14 EST from Cursor (2.5.26)_

---

**User**

can you compare the available node similarity algorithms in neo4j

---

**Cursor**

### High-level comparison

Neo4j’s Graph Data Science (GDS) library doesn’t have a huge list of totally separate “node similarity algorithms”; instead it has:

- a **Node Similarity** algorithm (neighbors-based)
- a **K-Nearest Neighbors (KNN)** algorithm (property / vector-based)
- several **similarity functions** (Jaccard, Overlap, Cosine, Pearson, etc.) that these algorithms can use under the hood

Below is a concise comparison focused on how you’d choose between them.

---

### 1. Node Similarity (neighbors-based)

- **What it does**: Compares nodes based on **their neighbors** (e.g. two users are similar if they interact with many of the same items / people).
- **Typical use-case**: “Users who viewed similar products”, “authors with similar co-authors”, “papers citing similar papers”.
- **How it works**:  
  - Builds neighbor sets (optionally weighted) from relationships.  
  - Computes pairwise similarity, typically sparsified (top-k or threshold).
- **Available similarity metrics**:
  - **Jaccard** (set-based): intersection / union of neighbor sets.
  - **Overlap coefficient**: intersection / min(|A|, |B|); favors nodes with smaller degree but strong shared neighbors.
  - **Cosine similarity**: treats neighbor weights as vectors; best when relationships have **weights** (e.g. rating counts, interaction frequency).
- **When to use**:
  - Your notion of similarity is “share many neighbors”.
  - You already have a bipartite or general interaction graph.
  - You want relationships like `(:User)-[:SIMILAR_TO]->(:User)` based on shared items.

---

### 2. K-Nearest Neighbors (KNN) (property/vector-based)

- **What it does**: Compares nodes by **numeric properties or embedding vectors** (e.g. feature vectors, FastRP / Node2Vec / GraphSAGE embeddings).
- **Typical use-case**: “Find similar products by embedding vector”, “similar documents by text embedding”, “similar users by feature vector”.
- **How it works**:
  - Reads one or more numeric properties (often an embedding array).
  - Uses a distance/similarity function to find each node’s **k nearest neighbors**.
  - Creates relationships like `(:Item)-[:SIMILAR_TO {score}]->(:Item)`.
- **Available similarity/distance measures** (via similarity functions):
  - **Cosine similarity** (most common for embeddings).
  - **Euclidean distance / Euclidean similarity**.
  - **Pearson** (for correlation-style similarity on numeric vectors).
- **When to use**:
  - You already have or plan to compute **embeddings** (FastRP, Node2Vec, GraphSAGE, external ML).
  - Similarity should reflect **latent structure** or rich features, not just shared neighbors.
  - You need a fixed **k** similar nodes per node, e.g. for recommendation or ANN-style queries.

---

### 3. Standalone similarity functions (arrays / properties)

These are lower-level **functions** that can be used directly or inside custom pipelines:

- **Categorical / set-based**:
  - **Jaccard**: for overlap between sets (IDs, categories, tags).
  - **Overlap coefficient**: emphasizes strong overlap when one set is much smaller.
- **Numeric / vector-based**:
  - **Cosine**: angle between vectors; ideal for high-dimensional embeddings.
  - **Pearson**: correlation; good when you care about shape/trend rather than absolute values.
  - **Euclidean distance / similarity**: direct geometric distance.

They’re the building blocks behind `gds.nodeSimilarity` and `gds.knn`.

---

### Choosing between them

- **You have a graph of interactions / co-occurrences** (e.g. users–items, authors–papers):
  - **Use `gds.nodeSimilarity`** with:
    - **Jaccard / Overlap** for unweighted edges and pure “co-occurrence” style similarity.
    - **Cosine** if relationships are **weighted**.

- **You have feature vectors or embeddings on nodes**:
  - **Use `gds.knn`** on a vector property, with:
    - **Cosine** for embeddings (most standard).
    - **Euclidean** when your feature space is naturally Euclidean.

- **You’re building a custom scoring logic in Cypher or a GDS pipeline**:
  - Use **similarity functions** (Jaccard, Cosine, Pearson, etc.) directly on arrays or vectors.

---

If you tell me your specific use-case (e.g. “I have students and courses and I want similar students” or “I have article embeddings”), I can recommend a precise algorithm + config and sketch the Cypher / GDS calls for it.

---

**User**

great work, lets also compare community detection algorithms

---

**Cursor**

### Overview

Neo4j GDS has several core **community detection** algorithms, each with different trade-offs in speed, quality, and assumptions about communities.

---

### 1. Leiden

- **Goal**: High-quality, well-connected communities via **modularity optimization**, improving on Louvain.
- **Strengths**:
  - **Better community quality** and fewer “broken” communities than Louvain.
  - Handles large graphs; hierarchical (can give communities at multiple resolutions).
- **Weaknesses**:
  - More complex than Label Propagation; a bit heavier than LPA.
- **Use when**:  
  - You care about **community quality** and **well-connectedness**.
  - You’re okay with a bit more compute for better structure.

---

### 2. Louvain

- **Goal**: Detect communities by **maximizing modularity**.
- **Strengths**:
  - Well-known, widely used; good quality vs performance.
  - Hierarchical: gives multiple levels of communities.
- **Weaknesses**:
  - Can produce communities that are **not well connected internally** (one reason Leiden was introduced).
- **Use when**:
  - You want modularity-based clustering and don’t need Leiden’s extra guarantees.
  - You want a good default and performance is more important than the last bit of quality.

---

### 3. Label Propagation (LPA)

- **Goal**: Very fast, approximate communities by **propagating labels** among neighbors.
- **Strengths**:
  - **Very fast and scalable**, simple to run.
  - No need to set an objective like modularity.
- **Weaknesses**:
  - More **unstable** (results can vary run-to-run).
  - Community quality generally lower than Louvain/Leiden; can give very coarse or noisy partitions.
- **Use when**:
  - You need a **quick, cheap** community detection.
  - You want a first-pass structure, then maybe refine with another method.

---

### 4. Connected Components (WCC / SCC)

- **Goal**: Find **connected subgraphs**, not “communities” in the modularity sense.
  - **WCC**: Weakly Connected Components (ignores edge direction).
  - **SCC**: Strongly Connected Components (direction-respecting, each node reachable from each other).
- **Strengths**:
  - Extremely **fast and simple**.
  - Gives a hard partition based solely on connectivity.
- **Weaknesses**:
  - Doesn’t consider density or modularity; large components may still contain many sub-communities.
- **Use when**:
  - You need the **basic connectivity structure**: which nodes are in the same “island”.
  - As a **preprocessing** step (e.g., run Louvain/Leiden/LPA inside each WCC).

---

### How to choose (rule of thumb)

- **Best overall quality**: **Leiden**  
- **Balanced & classic**: **Louvain**
- **Fastest approximate grouping**: **Label Propagation**
- **Pure connectivity partitioning**: **Connected Components (WCC/SCC)**

If you describe your graph (directed/undirected, size, and what “community” means in your assignment), I can suggest a specific algorithm and show the exact GDS calls you’d use.

