# Supply Chain Optimization with Graph Data - Complete Course Guide

## 📚 Course Overview

**Duration:** 60 minutes  
**Level:** Intermediate (Data Science students)  
**Tools:** Neo4j, Python, Cypher Query Language  
**Outcome:** Build and optimize a supply chain network using graph database technology

---

## 🎯 Learning Objectives

By the end of this course, you will:
- Understand why graph databases are ideal for supply chain modeling
- Model supply chain networks as nodes and relationships
- Implement a supply chain network in Neo4j
- Write Cypher queries for optimization and analysis
- Apply graph algorithms to solve real-world supply chain problems

---

## 📊 Course Structure (60 Minutes)

### Module 1: Introduction to Supply Chain Networks (0-10 min)

#### What is a Supply Chain?

A supply chain is a network of organizations, people, activities, and resources involved in moving a product from supplier to customer. Traditional relational databases struggle with:
- Multi-hop queries (finding paths through multiple levels)
- Network analysis (identifying bottlenecks and critical nodes)
- Relationship-rich data modeling

#### Why Graph Databases?

Graph databases excel at:
- **Native relationship storage** - relationships are first-class citizens
- **Path finding** - efficient traversal through connected data
- **Network analysis** - built-in algorithms for centrality, community detection
- **Flexible schema** - easy to add new node types or relationships
- **Query performance** - constant time relationship traversal vs JOIN operations

#### Key Graph Concepts

- **Nodes (Vertices)**: Entities in your network (Suppliers, Warehouses, Retailers)
- **Edges (Relationships)**: Connections between nodes (SUPPLIES_TO, SHIPS_TO)
- **Properties**: Attributes of nodes or relationships (cost, lead_time, capacity)
- **Labels**: Categories for nodes (Supplier, Warehouse)

---

### Module 2: Graph Data Modeling (10-20 min)

#### Node Types in Supply Chain

Our sample network includes four node types:

1. **Supplier** - Raw material and component providers
   - Properties: id, name, location, capacity, type

2. **Warehouse** - Storage facilities
   - Properties: id, name, location, storage_capacity

3. **Distribution Center** - Regional distribution hubs
   - Properties: id, name, location

4. **Retailer** - End customer-facing stores
   - Properties: id, name, location, daily_demand

#### Relationship Types

1. **SUPPLIES_TO** (Supplier → Warehouse)
   - Properties: cost, lead_time, distance

2. **SHIPS_TO** (Warehouse → Distribution Center)
   - Properties: cost, lead_time, distance

3. **DELIVERS_TO** (Distribution Center → Retailer)
   - Properties: cost, lead_time, distance

#### Data Model Diagram

```
[Supplier] --SUPPLIES_TO--> [Warehouse] --SHIPS_TO--> [DC] --DELIVERS_TO--> [Retailer]

Properties on relationships:
- cost_usd
- lead_time_days
- distance_miles
```

---

### Module 3: Neo4j Implementation (20-35 min)

#### Setting Up Neo4j

**Option 1: Neo4j Desktop** (Recommended for learning)
- Download from neo4j.com/download
- Create a new project and database
- Start the database and open Neo4j Browser

**Option 2: Neo4j Aura** (Cloud-based, free tier)
- Visit aura.neo4j.io
- Create free account and database instance

**Option 3: Docker**
```bash
docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

#### Creating Nodes

**Step 1: Create Suppliers**
```cypher
CREATE (s1:Supplier {
  id: 'S001',
  name: 'Raw Materials Inc',
  location: 'China',
  capacity: 50000,
  type: 'Raw Materials'
})

CREATE (s2:Supplier {
  id: 'S002',
  name: 'Component Corp',
  location: 'Vietnam',
  capacity: 30000,
  type: 'Components'
})

CREATE (s3:Supplier {
  id: 'S003',
  name: 'Parts Plus',
  location: 'Mexico',
  capacity: 40000,
  type: 'Parts'
})

CREATE (s4:Supplier {
  id: 'S004',
  name: 'Tech Supplies Ltd',
  location: 'Taiwan',
  capacity: 25000,
  type: 'Electronics'
})

CREATE (s5:Supplier {
  id: 'S005',
  name: 'Global Materials',
  location: 'India',
  capacity: 60000,
  type: 'Raw Materials'
})
```

**Step 2: Create Warehouses**
```cypher
CREATE (w1:Warehouse {
  id: 'W001',
  name: 'Central Warehouse',
  location: 'California',
  storage_capacity: 100000
})

CREATE (w2:Warehouse {
  id: 'W002',
  name: 'East Coast Depot',
  location: 'New Jersey',
  storage_capacity: 80000
})

CREATE (w3:Warehouse {
  id: 'W003',
  name: 'Midwest Hub',
  location: 'Illinois',
  storage_capacity: 90000
})

CREATE (w4:Warehouse {
  id: 'W004',
  name: 'South Regional',
  location: 'Texas',
  storage_capacity: 75000
})
```

**Step 3: Create Distribution Centers**
```cypher
CREATE (dc1:DistributionCenter {
  id: 'DC001',
  name: 'Northwest Distribution',
  location: 'Washington'
})

CREATE (dc2:DistributionCenter {
  id: 'DC002',
  name: 'Southwest Distribution',
  location: 'Arizona'
})

CREATE (dc3:DistributionCenter {
  id: 'DC003',
  name: 'Northeast Distribution',
  location: 'New York'
})

CREATE (dc4:DistributionCenter {
  id: 'DC004',
  name: 'Southeast Distribution',
  location: 'Florida'
})
```

**Step 4: Create Retailers**
```cypher
CREATE (r1:Retailer {
  id: 'R001',
  name: 'MegaMart Store 1',
  location: 'Seattle',
  daily_demand: 500
})

CREATE (r2:Retailer {
  id: 'R002',
  name: 'MegaMart Store 2',
  location: 'Phoenix',
  daily_demand: 450
})

CREATE (r3:Retailer {
  id: 'R003',
  name: 'MegaMart Store 3',
  location: 'New York',
  daily_demand: 600
})

CREATE (r4:Retailer {
  id: 'R004',
  name: 'MegaMart Store 4',
  location: 'Miami',
  daily_demand: 400
})

CREATE (r5:Retailer {
  id: 'R005',
  name: 'QuickShop Market 1',
  location: 'Los Angeles',
  daily_demand: 350
})

CREATE (r6:Retailer {
  id: 'R006',
  name: 'QuickShop Market 2',
  location: 'Chicago',
  daily_demand: 380
})
```

#### Creating Relationships

**Supplier to Warehouse Connections**
```cypher
MATCH (s:Supplier {id: 'S001'}), (w:Warehouse {id: 'W001'})
CREATE (s)-[:SUPPLIES_TO {cost: 5000, lead_time: 14, distance: 6500}]->(w)

MATCH (s:Supplier {id: 'S001'}), (w:Warehouse {id: 'W003'})
CREATE (s)-[:SUPPLIES_TO {cost: 4800, lead_time: 15, distance: 7000}]->(w)

MATCH (s:Supplier {id: 'S002'}), (w:Warehouse {id: 'W002'})
CREATE (s)-[:SUPPLIES_TO {cost: 3500, lead_time: 12, distance: 5800}]->(w)

MATCH (s:Supplier {id: 'S003'}), (w:Warehouse {id: 'W004'})
CREATE (s)-[:SUPPLIES_TO {cost: 2000, lead_time: 7, distance: 1500}]->(w)

MATCH (s:Supplier {id: 'S004'}), (w:Warehouse {id: 'W001'})
CREATE (s)-[:SUPPLIES_TO {cost: 4200, lead_time: 13, distance: 6200}]->(w)

MATCH (s:Supplier {id: 'S005'}), (w:Warehouse {id: 'W002'})
CREATE (s)-[:SUPPLIES_TO {cost: 5500, lead_time: 16, distance: 8000}]->(w)
```

**Warehouse to Distribution Center Connections**
```cypher
MATCH (w:Warehouse {id: 'W001'}), (dc:DistributionCenter {id: 'DC001'})
CREATE (w)-[:SHIPS_TO {cost: 800, lead_time: 2, distance: 800}]->(dc)

MATCH (w:Warehouse {id: 'W001'}), (dc:DistributionCenter {id: 'DC002'})
CREATE (w)-[:SHIPS_TO {cost: 1200, lead_time: 3, distance: 1200}]->(dc)

MATCH (w:Warehouse {id: 'W002'}), (dc:DistributionCenter {id: 'DC003'})
CREATE (w)-[:SHIPS_TO {cost: 600, lead_time: 1, distance: 500}]->(dc)

MATCH (w:Warehouse {id: 'W002'}), (dc:DistributionCenter {id: 'DC004'})
CREATE (w)-[:SHIPS_TO {cost: 1100, lead_time: 3, distance: 1300}]->(dc)

MATCH (w:Warehouse {id: 'W003'}), (dc:DistributionCenter {id: 'DC001'})
CREATE (w)-[:SHIPS_TO {cost: 1500, lead_time: 4, distance: 1800}]->(dc)

MATCH (w:Warehouse {id: 'W003'}), (dc:DistributionCenter {id: 'DC003'})
CREATE (w)-[:SHIPS_TO {cost: 700, lead_time: 2, distance: 700}]->(dc)

MATCH (w:Warehouse {id: 'W004'}), (dc:DistributionCenter {id: 'DC002'})
CREATE (w)-[:SHIPS_TO {cost: 900, lead_time: 2, distance: 900}]->(dc)

MATCH (w:Warehouse {id: 'W004'}), (dc:DistributionCenter {id: 'DC004'})
CREATE (w)-[:SHIPS_TO {cost: 500, lead_time: 1, distance: 400}]->(dc)
```

**Distribution Center to Retailer Connections**
```cypher
MATCH (dc:DistributionCenter {id: 'DC001'}), (r:Retailer {id: 'R001'})
CREATE (dc)-[:DELIVERS_TO {cost: 200, lead_time: 1, distance: 150}]->(r)

MATCH (dc:DistributionCenter {id: 'DC002'}), (r:Retailer {id: 'R002'})
CREATE (dc)-[:DELIVERS_TO {cost: 150, lead_time: 1, distance: 100}]->(r)

MATCH (dc:DistributionCenter {id: 'DC003'}), (r:Retailer {id: 'R003'})
CREATE (dc)-[:DELIVERS_TO {cost: 180, lead_time: 1, distance: 120}]->(r)

MATCH (dc:DistributionCenter {id: 'DC004'}), (r:Retailer {id: 'R004'})
CREATE (dc)-[:DELIVERS_TO {cost: 160, lead_time: 1, distance: 110}]->(r)

MATCH (dc:DistributionCenter {id: 'DC001'}), (r:Retailer {id: 'R005'})
CREATE (dc)-[:DELIVERS_TO {cost: 250, lead_time: 1, distance: 200}]->(r)

MATCH (dc:DistributionCenter {id: 'DC003'}), (r:Retailer {id: 'R006'})
CREATE (dc)-[:DELIVERS_TO {cost: 190, lead_time: 1, distance: 140}]->(r)
```

---

### Module 4: Optimization Techniques (35-50 min)

#### Finding Shortest Path

**Find shortest path from S001 to R001**
```cypher
MATCH path = shortestPath(
  (s:Supplier {id: 'S001'})-[*]-(r:Retailer {id: 'R001'})
)
RETURN path
```

#### Calculating Total Cost

**Total cost for a specific path**
```cypher
MATCH path = (s:Supplier {id: 'S001'})-[rels*]->(r:Retailer {id: 'R001'})
RETURN path,
  reduce(total = 0, rel in rels | total + rel.cost) AS total_cost,
  reduce(time = 0, rel in rels | time + rel.lead_time) AS total_time
ORDER BY total_cost
LIMIT 1
```

#### Finding All Possible Paths

```cypher
MATCH path = (s:Supplier)-[*]->(r:Retailer {id: 'R003'})
RETURN path,
  reduce(cost = 0, rel in relationships(path) | cost + rel.cost) AS total_cost,
  reduce(time = 0, rel in relationships(path) | time + rel.lead_time) AS total_time,
  length(path) as hops
ORDER BY total_cost
```

#### Multi-Criteria Optimization

**Weighted score: minimize both cost and time**
```cypher
MATCH path = (s:Supplier {id: 'S002'})-[rels*]->(r:Retailer {id: 'R004'})
WITH path, rels,
  reduce(cost = 0, r in rels | cost + r.cost) AS total_cost,
  reduce(time = 0, r in rels | time + r.lead_time) AS total_time
RETURN path,
  total_cost,
  total_time,
  (total_cost + total_time * 100) AS weighted_score
ORDER BY weighted_score
LIMIT 5
```

#### Identifying Bottlenecks

**Find nodes with most connections (potential bottlenecks)**
```cypher
MATCH (n)
WITH n,
  size((n)-->()) as outgoing,
  size((n)<--()) as incoming
RETURN n.id, n.location, outgoing, incoming, (outgoing + incoming) as total_connections
ORDER BY total_connections DESC
```

#### What-If Analysis

**Find alternative routes if W001 goes offline**
```cypher
MATCH path = (s:Supplier {id: 'S001'})-[rels*]->(r:Retailer {id: 'R001'})
WHERE NONE(node IN nodes(path) WHERE node.id = 'W001')
RETURN path,
  reduce(cost = 0, rel in rels | cost + rel.cost) AS total_cost
ORDER BY total_cost
LIMIT 3
```

#### Constraint-Based Optimization

**Find routes where each leg costs less than $2000**
```cypher
MATCH path = (s:Supplier {id: 'S001'})-[rels*..5]-(r:Retailer {id: 'R001'})
WHERE ALL(rel in rels WHERE rel.cost < 2000)
RETURN path,
  reduce(cost = 0, rel in rels | cost + rel.cost) AS total_cost
ORDER BY total_cost
```

---

### Module 5: Advanced Graph Algorithms (45-55 min)

#### Using Graph Data Science Library

**Install GDS Plugin** (if not already installed)
- In Neo4j Desktop, go to your project
- Click "Add Plugin" → Graph Data Science
- Click "Install"

**Create a graph projection**
```cypher
CALL gds.graph.project(
  'supply-chain-network',
  ['Supplier', 'Warehouse', 'DistributionCenter', 'Retailer'],
  {
    SUPPLIES_TO: {properties: 'cost'},
    SHIPS_TO: {properties: 'cost'},
    DELIVERS_TO: {properties: 'cost'}
  }
)
```

**PageRank - Identify most critical nodes**
```cypher
CALL gds.pageRank.stream('supply-chain-network')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).id AS node_id,
       gds.util.asNode(nodeId).name AS node_name,
       score
ORDER BY score DESC
LIMIT 10
```

**Dijkstra's Algorithm - Shortest weighted path**
```cypher
MATCH (source:Supplier {id: 'S001'}), (target:Retailer {id: 'R003'})
CALL gds.shortestPath.dijkstra.stream('supply-chain-network', {
  sourceNode: source,
  targetNode: target,
  relationshipWeightProperty: 'cost'
})
YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path
RETURN
  gds.util.asNode(sourceNode).id AS from,
  gds.util.asNode(targetNode).id AS to,
  totalCost,
  [nodeId IN nodeIds | gds.util.asNode(nodeId).id] AS route
```

**Community Detection - Find clusters**
```cypher
CALL gds.louvain.stream('supply-chain-network')
YIELD nodeId, communityId
RETURN communityId,
       collect(gds.util.asNode(nodeId).id) AS members,
       count(*) AS size
ORDER BY size DESC
```

---

### Module 6: Python Integration (Optional - 55-60 min)

#### Installing Neo4j Python Driver

```bash
pip install neo4j pandas
```

#### Connecting to Neo4j

```python
from neo4j import GraphDatabase
import pandas as pd

class SupplyChainDB:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def find_cheapest_route(self, supplier_id, retailer_id):
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (s:Supplier {id: $supplier_id})-[rels*]->(r:Retailer {id: $retailer_id})
                RETURN path,
                  reduce(cost = 0, rel in rels | cost + rel.cost) AS total_cost,
                  reduce(time = 0, rel in rels | time + rel.lead_time) AS total_time
                ORDER BY total_cost
                LIMIT 1
            """, supplier_id=supplier_id, retailer_id=retailer_id)
            
            for record in result:
                return {
                    'path': record['path'],
                    'cost': record['total_cost'],
                    'time': record['total_time']
                }

# Usage
db = SupplyChainDB("bolt://localhost:7687", "neo4j", "password")
route = db.find_cheapest_route('S001', 'R001')
print(f"Cheapest route cost: ${route['cost']}, Time: {route['time']} days")
db.close()
```

---

## 🎓 Practice Exercises

### Exercise 1: Data Loading
Load all the data from the spreadsheet into Neo4j. Verify all nodes and relationships are created correctly.

### Exercise 2: Path Analysis
Find the cheapest path from Supplier S001 to Retailer R003. Calculate total cost and lead time.

### Exercise 3: Network Analysis
Identify which warehouse serves the most distribution centers. This indicates a critical node in the network.

### Exercise 4: Optimization Challenge
Create a multi-objective optimization that minimizes both cost and time. Use a weighted formula: Score = Cost + (Time × 100).

### Exercise 5: Resilience Testing
Test network resilience: If Warehouse W001 goes offline, what are the best alternative routes?

### Exercise 6: Capacity Planning
Calculate if current supplier capacities can meet total retailer demand. Sum daily demands and compare to supplier capacities.

### Exercise 7: Cost Efficiency
Calculate the average cost per mile for each relationship type. Which segment of the supply chain is most cost-efficient?

### Exercise 8: Graph Algorithms
Use PageRank to identify the most critical nodes. Discuss why these nodes are important.

### Exercise 9: What-If Scenarios
Create a scenario where demand at R003 increases by 50%. Which paths become overutilized?

### Exercise 10: Advanced Implementation
Build a Python script that loads data from the Excel file and creates the Neo4j graph automatically.

---

## 📚 Curated Resources

### YouTube Videos

1. **"Graph Databases Will Change Your Freakin Life"** by Fireship (15 min)
   - Best intro to graph databases
   - Explains why traditional DBs fail at relationships
   - Search: "Fireship graph database"

2. **"Neo4j in 100 Seconds"** by Fireship (2 min)
   - Quick Neo4j overview
   - Search: "Fireship Neo4j 100 seconds"

3. **"Introduction to Graph Databases and Neo4j"** by freeCodeCamp (2 hours)
   - Comprehensive tutorial
   - Covers Cypher in depth
   - Search: "freeCodeCamp Neo4j"

4. **"Neo4j Graph Data Science"** by Neo4j (30 min)
   - Graph algorithms explained
   - Real-world use cases
   - Search: "Neo4j Graph Data Science algorithms"

5. **"Supply Chain Optimization with Graphs"** (Various creators)
   - Search: "supply chain graph database optimization"
   - Look for videos showing logistics networks

### Medium Articles

Search on Medium for these topics:

1. **"Supply Chain Optimization using Graph Theory"**
   - Theoretical foundations
   - Real-world applications

2. **"Building a Supply Chain Network with Neo4j"**
   - Step-by-step implementation
   - Best practices

3. **"Graph Algorithms for Logistics and Supply Chain"**
   - Shortest path algorithms
   - Network flow optimization

4. **"From SQL to Cypher: A Supply Chain Migration Story"**
   - Migration patterns
   - Performance comparisons

### Towards Data Science Articles

Search on TowardsDataScience.com:

1. **"Network Analysis for Supply Chain Optimization"**
   - Python NetworkX + Neo4j
   - Visualization techniques

2. **"Graph Neural Networks for Supply Chain Forecasting"**
   - ML on graph data
   - Demand prediction

3. **"Introduction to Neo4j with Python"**
   - Python driver tutorial
   - Best practices

4. **"Shortest Path Algorithms Explained"**
   - Dijkstra, A*, Bellman-Ford
   - When to use each

5. **"PageRank Beyond Google: Supply Chain Applications"**
   - Identifying critical nodes
   - Risk assessment

### Neo4j Official Resources

1. **Neo4j GraphAcademy** (FREE)
   - https://graphacademy.neo4j.com/
   - Interactive courses with certificates
   - Highly recommended: "Neo4j Fundamentals" and "Cypher Fundamentals"

2. **Neo4j Cypher Manual**
   - https://neo4j.com/docs/cypher-manual/current/
   - Complete language reference
   - Query optimization guide

3. **Graph Data Science Library**
   - https://neo4j.com/docs/graph-data-science/current/
   - Algorithm documentation
   - Python integration examples

4. **Neo4j Python Driver**
   - https://neo4j.com/docs/python-manual/current/
   - Driver API reference
   - Best practices

5. **Neo4j Community Forum**
   - https://community.neo4j.com/
   - Ask questions
   - See real-world solutions

### GitHub Repositories

Search GitHub for:

1. **"neo4j supply chain examples"**
   - Working code examples
   - Jupyter notebooks

2. **"graph optimization logistics"**
   - Various implementations
   - Performance benchmarks

3. **"neo4j python data science"**
   - Integration patterns
   - Analysis workflows

### Online Courses

1. **"Graph Algorithms"** - Coursera (Stanford University)
   - Theoretical foundations
   - Algorithm design

2. **"Supply Chain Analytics"** - edX (MIT)
   - Supply chain modeling
   - Optimization techniques

3. **"Neo4j Certified Professional"** - Neo4j
   - Official certification
   - Comprehensive training

### Books and Papers

1. **"Graph Algorithms: Practical Examples in Apache Spark and Neo4j"**
   - Free O'Reilly eBook from Neo4j
   - Download from: neo4j.com/graph-algorithms-book/

2. **"Supply Chain Network Design: Understanding the Optimization Behind Logistics"**
   - Academic foundations
   - Mathematical models

3. **"The Practitioner's Guide to Graph Data"**
   - Neo4j best practices
   - Real-world patterns

---

## 💡 Key Takeaways

1. **Graph databases are natural for supply chains** - relationships are first-class citizens
2. **Cypher is powerful and readable** - query complexity doesn't scale linearly
3. **Path finding is built-in** - no need for recursive CTEs or complex JOINs
4. **Graph algorithms add value** - PageRank, community detection, centrality measures
5. **Multi-criteria optimization is possible** - combine cost, time, risk in queries
6. **What-if analysis is straightforward** - filter paths dynamically
7. **Python integration is seamless** - easy to combine with pandas and ML workflows

---

## 🚀 Next Steps

1. **Complete Neo4j GraphAcademy courses** - build strong fundamentals
2. **Implement the practice exercises** - hands-on learning is essential
3. **Extend the model** - add inventory levels, demand forecasts, risk factors
4. **Explore graph ML** - Graph Neural Networks for demand prediction
5. **Build a dashboard** - visualize your supply chain network
6. **Read case studies** - learn from real-world implementations
7. **Join the community** - Neo4j forums, conferences, meetups

---

## 📊 Sample Data Summary

The accompanying Excel file contains:

- **5 Suppliers** with varying capacities and locations
- **4 Warehouses** with different storage capacities
- **4 Distribution Centers** across regions
- **6 Retailers** with daily demand figures
- **20 Network relationships** with cost, time, and distance properties

This creates a realistic supply chain network with multiple paths and optimization opportunities.

---

## 🎯 Success Metrics

After completing this course, you should be able to:

✅ Model a supply chain as a property graph  
✅ Write Cypher queries for common supply chain questions  
✅ Use graph algorithms for network analysis  
✅ Implement multi-criteria optimization  
✅ Connect Neo4j to Python for data science workflows  
✅ Identify bottlenecks and critical paths  
✅ Perform what-if analysis on network changes  

---

**Happy Learning! 🎓**

For questions or issues, refer to the Neo4j Community Forum or Stack Overflow with the #neo4j tag.
