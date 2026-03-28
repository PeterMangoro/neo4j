# Cypher query comparison for Tom Hanks
_Exported on 2/11/2026 at 01:05:12 EST from Cursor (2.4.27)_

---

**User**

match (p:Person) -[:ACTED_IN]->(m:Movie) where p.name = 'Tom Hanks' and exists {(p)-[:DIRECTED]->(m)} 
vs
match (p:Person) -[:ACTED_IN]->(m:Movie) <-[:DIRECTED]-(p) where p.name = 'Tom Hanks' 
vs
match (p:Person {name:'Tom Hanks'}) -[:ACTED_IN]->(m:Movie) <-[:DIRECTED]-(p) 
explain to me how these  3 queries are different and which one is better

---

**Cursor**


All three queries return the same result: **movies that Tom Hanks both acted in and directed**. The differences are in how they express that and how the planner can optimize them.

---

## What each query does

| Query | Logic |
|-------|--------|
| **1** | Find `(p:Person)-[:ACTED_IN]->(m:Movie)`, then keep only rows where `p.name = 'Tom Hanks'` and where the subquery `(p)-[:DIRECTED]->(m)` exists. |
| **2** | Find `(p:Person)-[:ACTED_IN]->(m:Movie)<-[:DIRECTED]-(p)` (same person acted in and directed the same movie), then filter by `p.name = 'Tom Hanks'`. |
| **3** | Same pattern as 2, but the person is fixed in the pattern as `(p:Person {name:'Tom Hanks'})`, so no `WHERE` is needed. |

So logically they are equivalent; the difference is style and optimization.

---

## Differences

### 1. Where the “Tom Hanks” filter is applied

- **Query 1 & 2:** `WHERE p.name = 'Tom Hanks'`  
  The engine can start by scanning `Person` and then filter by name, or use an index on `Person(name)` if available.

- **Query 3:** `(p:Person {name:'Tom Hanks'})`  
  The filter is part of the pattern. This makes it explicit that you start from a specific person and makes it very natural for the planner to use an index on `Person(name)` first, then expand only from that node.

### 2. How “acted in and directed the same movie” is expressed

- **Query 1:** `exists {(p)-[:DIRECTED]->(m)}`  
  The “directed” part is a separate subquery predicate. Same result, but the plan may treat it as an extra existence check after the main pattern.

- **Query 2 & 3:** `(p)-[:ACTED_IN]->(m)<-[:DIRECTED]-(p)`  
  “Acted in” and “directed” are in one pattern. The planner can optimize this as a single graph traversal (e.g., from `p` follow both relationship types to the same `m`).

### 3. Readability

- **Query 3** is usually the clearest: “Start from the person named Tom Hanks; find movies he both acted in and directed,” with no `WHERE`.
- **Query 2** is the same idea with the name in `WHERE`.
- **Query 1** is a bit more indirect because of the `exists` subquery.

---

## Which one is better?

**Query 3 is generally the best choice:**

1. **Index use:** Putting `name:'Tom Hanks'` in the pattern encourages the planner to use an index on `Person(name)` and start from one (or few) nodes, instead of scanning many persons and filtering later.
2. **Single pattern:** Expressing both ACTED_IN and DIRECTED in the same `MATCH` is easy to optimize and matches how you think about the question (“movies where this person has both relationships”).
3. **Simpler:** No `WHERE`; the intent is clear from the pattern alone.

**Query 2** is equivalent in result and still good; it’s just slightly less optimal if the planner doesn’t push the `WHERE` into an index lookup as early as in Query 3.

**Query 1** is correct but typically less efficient and less clear: the `exists` subquery is an extra predicate and may lead to a less efficient plan than a single pattern match.

**Summary:** Prefer **Query 3**. Use **Query 2** if you prefer keeping the name in a `WHERE` clause; avoid **Query 1** for this use case when you can express the same with a single pattern like in 2 or 3.

