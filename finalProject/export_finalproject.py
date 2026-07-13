#!/usr/bin/env python3
"""Generate static JSON payloads for the /supply-chain demo.

Pure-Python mirror of P_Mangoro_AutomotiveSupplyChain.ipynb: reads the Moetz
et al. (2020) workbook directly (no live Neo4j required), reproduces EDA +
deeper analytics + NetworkX PageRank/Louvain equivalents, and writes curated
subgraphs (never the full 28k-node BOM).

Writes into nuxt_neo4j/public/data/supply-chain/:
    stats.json, queries.json, pagerank.json, communities.json,
    product_index.json, graph_facility.json, graph_bom_<slug>.json

Usage:
    python export_finalproject.py [--out DIR] [--xlsx PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
from networkx.algorithms.community import louvain_communities

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "nuxt_neo4j" / "public" / "data" / "supply-chain"
DEFAULT_XLSX = HERE / "2020_dataset_OfAutomotiveProductionNetwork.xlsx"

EXPECTED_PRODUCTS = 28_049
EXPECTED_REQUIRES = 87_059
EXPECTED_FACILITIES = 12
EXPECTED_SHIPS_TO = 11
EXPECTED_DEMAND_FACTS = 28_000
GRAPH_NODE_CAP = 220
BOM_DEPTH = 3
EDA_7_PERIOD = 61
HOLDS_PERIOD = 60

COMMUNITIES_INTRO = (
    "Louvain communities on the undirected Product–REQUIRES graph (weighted by "
    "BOM quantity) surface large, car-dominant dependency modules — module-level "
    "risk zones instead of one undifferentiated BOM."
)

PRODUCT_SEEDS: list[tuple[str, str]] = [
    ("Q4H", "pagerank"),
    ("G0K", "pagerank"),
    ("Q2J", "pagerank"),
    ("G1C", "pagerank"),
    ("componment_seat2", "pagerank"),
    ("64002", "fanout"),
    ("64099", "fanout"),
    ("componment_battery1", "risk"),
    ("componment_seat1", "risk"),
    ("DN4", "pagerank"),
]


def slugify(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", pid.strip()).strip("_")[:80] or "product"


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.name} ({path.stat().st_size:,} bytes)")


def query_entry(
    qid: str,
    title: str,
    description: str,
    cypher: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    cols: list[str] = []
    for row in rows:
        for k in row:
            if k not in cols:
                cols.append(k)
    return {
        "id": qid,
        "title": title,
        "description": description,
        "cypher": cypher.strip(),
        "columns": cols,
        "rows": [{k: jsonable(v) for k, v in row.items()} for row in rows],
        "count": len(rows),
    }


class SupplyChainData:
    def __init__(self, xlsx: Path) -> None:
        self.xlsx = xlsx
        self.products = pd.read_excel(xlsx, sheet_name="products")
        self.bom = pd.read_excel(xlsx, sheet_name="BOM")
        self.nodes = pd.read_excel(xlsx, sheet_name="nodes")
        self.arcs = pd.read_excel(xlsx, sheet_name="arcs")
        self.nodes_inflow = pd.read_excel(xlsx, sheet_name="nodes_inflow")
        self.demands = pd.read_excel(xlsx, sheet_name="demands")
        self.capacity = pd.read_excel(xlsx, sheet_name="capacity_at_arc")
        self.inventories = pd.read_excel(xlsx, sheet_name="initial_inventories")

        self.products["product_p"] = self.products["product_p"].astype(str).str.strip()
        self.products["group_g"] = self.products["group_g"].astype(str).str.strip()
        self.bom["mother"] = self.bom["mother"].astype(str).str.strip()
        self.bom["child"] = self.bom["child"].astype(str).str.strip()
        self.bom["qty"] = pd.to_numeric(
            self.bom["individual_input_quantity_q_mc"], errors="coerce"
        ).fillna(1.0)

        self.product_group: dict[str, str] = dict(
            zip(self.products["product_p"], self.products["group_g"])
        )
        self.groups = sorted(self.products["group_g"].unique())

        self.children: dict[str, list[tuple[str, float]]] = defaultdict(list)
        self.parents: dict[str, set[str]] = defaultdict(set)
        for _, r in self.bom.iterrows():
            m, c, q = r["mother"], r["child"], float(r["qty"])
            self.children[m].append((c, q))
            self.parents[c].add(m)

        self.requires_dag = nx.DiGraph()
        for _, r in self.bom.iterrows():
            self.requires_dag.add_edge(r["mother"], r["child"], weight=float(r["qty"]))

        self.car_ids = [p for p, g in self.product_group.items() if g == "car"]
        print("  precomputing BOM reachability …")
        self._ancestors = {
            n: nx.ancestors(self.requires_dag, n) for n in self.requires_dag.nodes
        }
        self._car_desc = {
            car: nx.descendants(self.requires_dag, car) for car in self.car_ids
        }

        self.facilities = [str(x).strip() for x in self.nodes["node_n"].tolist()]
        self.oem = {"zp7", "zp8"}

        self.arcs_rows: list[dict[str, Any]] = []
        for _, r in self.arcs.iterrows():
            si = str(r["starting_node_i"]).strip()
            ej = str(r["ending_node_j"]).strip()
            self.arcs_rows.append({
                "fromNode": si,
                "toNode": ej,
                "arcKey": f"{si}|{ej}",
                "productGroup": str(r["group_g"]).strip(),
                "leadTime": int(pd.to_numeric(r["process_lead_time_l_ij"], errors="coerce") or 0),
            })

        self.producers: dict[str, set[str]] = defaultdict(set)
        for _, r in self.nodes_inflow.iterrows():
            self.producers[str(r["product_p"]).strip()].add(str(r["node_n"]).strip())

    # --- stats / EDA -------------------------------------------------------

    def build_stats(self) -> dict[str, Any]:
        node_counts = [
            {"label": "Facility", "count": len(self.facilities)},
            {"label": "Product", "count": len(self.products)},
            {"label": "ProductGroup", "count": len(self.groups)},
            {"label": "Period", "count": int(self.demands["period_t"].nunique())},
            {"label": "DemandFact", "count": len(self.demands)},
            {"label": "Customer", "count": 1},
        ]
        rel_counts = [
            {"type": "REQUIRES", "count": len(self.bom)},
            {"type": "SHIPS_TO", "count": len(self.arcs)},
            {"type": "BELONGS_TO", "count": len(self.products)},
            {"type": "PRODUCES", "count": len(self.nodes_inflow)},
            {"type": "HAS_DEMAND", "count": len(self.demands)},
        ]
        highlights = [
            {"label": "Products", "value": len(self.products)},
            {"label": "BOM edges (REQUIRES)", "value": len(self.bom)},
            {"label": "Facilities", "value": len(self.facilities)},
            {"label": "Supplier lanes (SHIPS_TO)", "value": len(self.arcs)},
            {"label": "Demand lines", "value": len(self.demands)},
            {"label": "Top OEM chokepoint", "value": "zp8 / zp7"},
        ]
        return {"nodeCounts": node_counts, "relCounts": rel_counts, "highlights": highlights}

    def eda_queries(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        layers = [
            ("Facility", len(self.facilities)),
            ("Product", len(self.products)),
            ("ProductGroup", len(self.groups)),
            ("Period", int(self.demands["period_t"].nunique())),
            ("DemandFact", len(self.demands)),
            ("Customer", 1),
        ]
        out.append(query_entry(
            "eda-layers",
            "Entity layers",
            "Major node layers in the loaded automotive network.",
            "MATCH (n) … RETURN layer, count(n)",
            [{"layer": k, "cnt": v} for k, v in layers],
        ))

        rel_types = [
            ("REQUIRES", len(self.bom)),
            ("SHIPS_TO", len(self.arcs)),
            ("BELONGS_TO", len(self.products)),
            ("PRODUCES", len(self.nodes_inflow)),
            ("HAS_DEMAND", len(self.demands)),
        ]
        out.append(query_entry(
            "eda-rel-types",
            "Relationship families",
            "BOM-heavy graph with a compact facility lane network.",
            "MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count DESC",
            [{"relationshipType": t, "cnt": c} for t, c in rel_types],
        ))

        # EDA 2: group fan-out
        group_stats: dict[str, dict[str, Any]] = {}
        for pid, grp in self.product_group.items():
            n_ch = len(self.children.get(pid, []))
            g = group_stats.setdefault(grp, {"nProducts": 0, "children": []})
            g["nProducts"] += 1
            g["children"].append(n_ch)
        eda2 = []
        for grp, g in group_stats.items():
            ch = g["children"]
            eda2.append({
                "groupName": grp,
                "nProducts": g["nProducts"],
                "avgRequiresChildren": round(sum(ch) / len(ch), 2) if ch else 0,
                "maxRequiresChildren": max(ch) if ch else 0,
            })
        eda2.sort(key=lambda x: x["nProducts"], reverse=True)
        out.append(query_entry(
            "eda-group-fanout",
            "BOM width by product group",
            "Average and max direct REQUIRES children per ProductGroup.",
            "MATCH (pg:ProductGroup)<-[:BELONGS_TO]-(p:Product) …",
            eda2,
        ))

        # EDA 3: top fan-out products
        fanout = []
        for pid in self.product_group:
            fanout.append({
                "productId": pid,
                "groupName": self.product_group[pid],
                "nDirectComponents": len(self.children.get(pid, [])),
            })
        fanout.sort(key=lambda x: (-x["nDirectComponents"], x["productId"]))
        out.append(query_entry(
            "eda-top-products",
            "Top products by tier-1 fan-out",
            "Car SKUs with the widest direct BOM (4 components each in this extract).",
            "MATCH (p:Product) … ORDER BY nDirectComponents DESC LIMIT 5",
            fanout[:5],
        ))

        # EDA 4: car composition by child group
        car_ids = [p for p, g in self.product_group.items() if g == "car"]
        comp_by_group: Counter[str] = Counter()
        for car in car_ids:
            for child, _ in self.children.get(car, []):
                cg = self.product_group.get(child, "unassigned")
                comp_by_group[cg] += 1
        eda4 = [
            {"childGroup": g, "nRequiresEdges": c}
            for g, c in comp_by_group.most_common()
        ]
        out.append(query_entry(
            "eda-car-components",
            "Finished-car BOM by child group",
            "Tier-1 component groups required across all car products.",
            "MATCH (car:Product)-[:BELONGS_TO]->(:ProductGroup {groupName:'car'}) …",
            eda4,
        ))

        out.append(query_entry(
            "eda-lanes",
            "Supplier lanes (SHIPS_TO)",
            "Directed logistics arcs with lead time and product group.",
            "MATCH (a:Facility)-[s:SHIPS_TO]->(b:Facility) … ORDER BY leadTime DESC",
            sorted(self.arcs_rows, key=lambda x: (-x["leadTime"], x["fromNode"])),
        ))

        # EDA 7: tightest capacity at t=61
        cap61 = self.capacity[self.capacity["period_t"] == EDA_7_PERIOD].copy()
        cap61["capacity"] = pd.to_numeric(cap61["capacity_c_ijt"], errors="coerce")
        cap61 = cap61[cap61["capacity"] > 0]
        arc_lookup = {a["arcKey"]: a for a in self.arcs_rows}
        eda7 = []
        for _, r in cap61.sort_values("capacity_c_ijt").iterrows():
            si = str(r["starting_node_i"]).strip()
            ej = str(r["ending_node_j"]).strip()
            key = f"{si}|{ej}"
            meta = arc_lookup.get(key, {})
            eda7.append({
                "arcKey": key,
                "fromNode": si,
                "toNode": ej,
                "leadTime": meta.get("leadTime", 0),
                "shipsProductGroup": meta.get("productGroup", "unknown"),
                "capacity": int(r["capacity"]),
            })
        out.append(query_entry(
            "eda-tight-capacity",
            f"Tightest lane capacity (period {EDA_7_PERIOD})",
            "Lanes with the lowest positive capacity at the start of the demand horizon.",
            f"MATCH … WHERE c.periodId = {EDA_7_PERIOD} … ORDER BY capacity ASC",
            eda7,
        ))

        # EDA 10: component spread across cars
        total_cars = len(self.car_ids)
        comp_to_cars: dict[str, set[str]] = defaultdict(set)
        comp_paths: Counter[str] = Counter()
        for car, desc in self._car_desc.items():
            for comp in desc:
                comp_to_cars[comp].add(car)
                comp_paths[comp] += 1
        spread = [
            {
                "componentId": comp,
                "componentGroup": self.product_group.get(comp, "unassigned"),
                "nCarProductsUsingComponent": len(cars),
                "pctOfCarPortfolio": round(100.0 * len(cars) / max(total_cars, 1), 2),
                "nDependencyPaths": comp_paths[comp],
            }
            for comp, cars in comp_to_cars.items()
            if comp not in self.car_ids
        ]
        spread.sort(key=lambda x: (-x["nCarProductsUsingComponent"], -x["nDependencyPaths"]))
        out.append(query_entry(
            "eda-component-spread",
            "Components spanning the car portfolio",
            "Parts used by the largest share of finished car SKUs (blast-radius signal).",
            "MATCH (car)-[:REQUIRES*1..]->(comp) … ORDER BY nCarProductsUsingComponent DESC LIMIT 10",
            spread[:10],
        ))

        return out

    def analytics_queries(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        # Analytical 1: concentration
        conc: list[dict[str, Any]] = []
        for comp in self.product_group:
            anc = self._ancestors.get(comp, set())
            if not anc:
                continue
            conc.append({
                "componentId": comp,
                "componentGroup": self.product_group.get(comp, "unassigned"),
                "upstreamProductsDependingOnIt": len(anc),
                "totalDependencyPaths": sum(len(self.children.get(a, [])) for a in anc),
            })
        conc.sort(key=lambda x: (-x["upstreamProductsDependingOnIt"], -x["totalDependencyPaths"]))
        out.append(query_entry(
            "analytics-concentration",
            "Component concentration risk map",
            "Components ranked by how many upstream products depend on them through the BOM.",
            "MATCH (parent)-[:REQUIRES*1..]->(comp) … ORDER BY upstreamProductsDependingOnIt DESC LIMIT 10",
            conc[:10],
        ))

        # Analytical 2: arc fragility
        cap = self.capacity.copy()
        cap["period_t"] = pd.to_numeric(cap["period_t"], errors="coerce")
        cap = cap[(cap["period_t"] >= 61) & (cap["period_t"] <= 74)]
        cap["capacity"] = pd.to_numeric(cap["capacity_c_ijt"], errors="coerce")
        cap_agg = cap.groupby(["starting_node_i", "ending_node_j"]).agg(
            minCapacity=("capacity", "min"),
            avgCapacity=("capacity", "mean"),
            nCapacityPeriods=("capacity", "count"),
        ).reset_index()

        inv = self.inventories[self.inventories["period_t"] == HOLDS_PERIOD].copy()
        inv["initial_inventory_I_np0"] = pd.to_numeric(
            inv["initial_inventory_I_np0"], errors="coerce"
        ).fillna(0)
        dest_inv = inv.groupby("node_n")["initial_inventory_I_np0"].sum().to_dict()

        frag = []
        for arc in self.arcs_rows:
            key = arc["arcKey"]
            si, ej = arc["fromNode"], arc["toNode"]
            cap_row = cap_agg[
                (cap_agg["starting_node_i"].astype(str).str.strip() == si)
                & (cap_agg["ending_node_j"].astype(str).str.strip() == ej)
            ]
            min_cap = float(cap_row["minCapacity"].iloc[0]) if len(cap_row) else 0.0
            avg_cap = float(cap_row["avgCapacity"].iloc[0]) if len(cap_row) else 0.0
            n_per = int(cap_row["nCapacityPeriods"].iloc[0]) if len(cap_row) else 0
            dest_open = float(dest_inv.get(ej, 0))
            lt = float(arc["leadTime"])
            score = round(
                0.45 * lt
                + 0.35 * (1.0 / (1.0 + min_cap / 1000.0))
                + 0.20 * (1.0 / (1.0 + dest_open / 1000.0)),
                4,
            )
            frag.append({
                "arcKey": key,
                "fromNode": si,
                "toNode": ej,
                "shipsProductGroup": arc["productGroup"],
                "leadTime": int(lt),
                "minCapacity": int(min_cap),
                "avgCapacity": round(avg_cap, 1),
                "nCapacityPeriods": n_per,
                "destOpeningInventory_t60": int(dest_open),
                "structuralFragilityScore": score,
            })
        frag.sort(key=lambda x: (-x["structuralFragilityScore"], -x["leadTime"], x["minCapacity"]))
        out.append(query_entry(
            "analytics-fragility",
            "Arc structural fragility",
            "Lanes scored by lead time, tight capacity, and destination opening inventory.",
            "MATCH (a)-[s:SHIPS_TO]->(b) … structuralFragilityScore … LIMIT 25",
            frag[:25],
        ))

        # Analytical 3: risk-adjusted priority (reuse descendant cache)
        risk_rows = []
        arc_by_from = {a["fromNode"]: a for a in self.arcs_rows}
        for comp in self.product_group:
            anc = self._ancestors.get(comp, set())
            users = [p for p in anc if p != comp]
            if not users:
                continue
            upstream = len(users)
            producers = self.producers.get(comp, set())
            supplier_count = len(producers)
            max_frag = 0.0
            for p in producers:
                arc = arc_by_from.get(p)
                if not arc:
                    continue
                si, ej = arc["fromNode"], arc["toNode"]
                cap_row = cap_agg[
                    (cap_agg["starting_node_i"].astype(str).str.strip() == si)
                    & (cap_agg["ending_node_j"].astype(str).str.strip() == ej)
                ]
                min_cap = float(cap_row["minCapacity"].iloc[0]) if len(cap_row) else 0.0
                lt = float(arc["leadTime"])
                frag_score = 0.6 * lt + 0.4 * (1.0 / (1.0 + min_cap / 1000.0))
                max_frag = max(max_frag, frag_score)
            supplier_factor = (
                1.2 if supplier_count == 0 else (1.0 if supplier_count == 1 else 1.0 / supplier_count)
            )
            score = round(
                0.55 * math.log10(1.0 + upstream)
                + 0.30 * supplier_factor
                + 0.15 * max_frag,
                4,
            )
            if upstream == 0:
                continue
            risk_rows.append({
                "componentId": comp,
                "componentGroup": self.product_group.get(comp, "unassigned"),
                "upstreamProductsDependingOnIt": upstream,
                "supplierCount": supplier_count,
                "maxSupplierArcFragility": round(max_frag, 4),
                "riskAdjustedPriorityScore": score,
            })
        risk_rows.sort(
            key=lambda x: (-x["riskAdjustedPriorityScore"], -x["upstreamProductsDependingOnIt"])
        )
        out.append(query_entry(
            "analytics-risk-priority",
            "Supply risk-adjusted component priority",
            "Integrates BOM reach, single-source exposure, and lane fragility.",
            "MATCH (parent)-[:REQUIRES*1..]->(comp) … riskAdjustedPriorityScore … LIMIT 10",
            risk_rows[:10],
        ))

        return out

    # --- GDS equivalents ---------------------------------------------------

    def build_pagerank(self) -> dict[str, Any]:
        g = nx.DiGraph()
        for grp in self.groups:
            g.add_node(f"pg:{grp}", ntype="ProductGroup", name=grp)
        for pid, grp in self.product_group.items():
            g.add_node(f"p:{pid}", ntype="Product", name=pid)
            g.add_edge(f"p:{pid}", f"pg:{grp}", type="BELONGS_TO")
        for f in self.facilities:
            g.add_node(f"f:{f}", ntype="Facility", name=f)
        for _, r in self.bom.iterrows():
            g.add_edge(f"p:{r['mother']}", f"p:{r['child']}", type="REQUIRES")
        for arc in self.arcs_rows:
            g.add_edge(f"f:{arc['fromNode']}", f"f:{arc['toNode']}", type="SHIPS_TO")
        for _, r in self.nodes_inflow.iterrows():
            g.add_edge(f"f:{str(r['node_n']).strip()}", f"p:{str(r['product_p']).strip()}", type="PRODUCES")
        # Demand wiring (compact)
        g.add_node("cust:market", ntype="Customer", name="market")
        periods = sorted(self.demands["period_t"].unique())
        for pt in periods:
            g.add_node(f"t:{pt}", ntype="Period", name=str(pt))
        for i, (_, r) in enumerate(self.demands.iterrows()):
            if i > 5000:
                break  # sample for speed; facility pagerank unaffected
            nn = str(r["node_n"]).strip()
            pid = str(r["product_p"]).strip()
            pt = r["period_t"]
            fk = f"df:{nn}::{pid}::{pt}"
            g.add_node(fk, ntype="DemandFact", name=fk)
            g.add_edge("cust:market", fk, type="ORDERS")
            g.add_edge(f"f:{nn}", fk, type="HAS_DEMAND")
            g.add_edge(fk, f"p:{pid}", type="FOR_PRODUCT")
            g.add_edge(fk, f"t:{pt}", type="IN_PERIOD")

        scores = nx.pagerank(g, alpha=0.85, max_iter=50)
        node_rows = []
        for nid, score in sorted(scores.items(), key=lambda x: -x[1]):
            data = g.nodes[nid]
            ntype = data.get("ntype", "Node")
            node_rows.append({
                "nodeName": data.get("name", nid),
                "nodeType": [ntype],
                "score": round(score, 10),
            })
        facility_rows = []
        for nid, score in sorted(scores.items(), key=lambda x: -x[1]):
            data = g.nodes[nid]
            if data.get("ntype") != "Facility":
                continue
            name = data.get("name", nid)
            roles = []
            if name in self.oem:
                roles.append("OEM")
            else:
                roles.append("SupplierSite")
            if name.endswith("_prod"):
                roles.append("Production")
            if name.endswith("_inv"):
                roles.append("Inventory")
            facility_rows.append({
                "nodeName": name,
                "roleLabels": roles,
                "nodeType": ["Facility"],
                "score": round(score, 10),
            })

        return {
            "projection": {
                "name": "automotive-network",
                "nodeCount": g.number_of_nodes(),
                "relationshipCount": g.number_of_edges(),
            },
            "topNodes": node_rows[:20],
            "topFacilities": facility_rows[:12],
        }

    def build_communities(self) -> dict[str, Any]:
        ug = nx.Graph()
        for _, r in self.bom.iterrows():
            u, v, w = r["mother"], r["child"], float(r["qty"])
            if ug.has_edge(u, v):
                ug[u][v]["weight"] += w
            else:
                ug.add_edge(u, v, weight=w)

        comms = louvain_communities(ug, weight="weight", seed=9)
        rows = []
        for i, members in enumerate(comms):
            comp: Counter[str] = Counter()
            for pid in members:
                comp[self.product_group.get(pid, "unassigned")] += 1
            composition = [
                {"group": g, "count": c}
                for g, c in comp.most_common()
            ]
            total = len(members)
            car_share = next((x["count"] for x in composition if x["group"] == "car"), 0) / max(total, 1)
            commentary = (
                f"Largest car-dominant BOM module ({car_share:.0%} car SKUs)."
                if car_share > 0.9
                else f"Mixed module: {composition[0]['group']} ({composition[0]['count']} of {total})."
                if composition
                else f"Module of {total} products."
            )
            rows.append({
                "id": i,
                "size": total,
                "composition": composition,
                "commentary": commentary,
            })
        rows.sort(key=lambda x: -x["size"])

        return {
            "communityCount": len(rows),
            "intro": COMMUNITIES_INTRO,
            "communities": rows[:12],
        }

    # --- Curated graphs ----------------------------------------------------

    def export_facility_graph(self, pagerank: dict[str, Any]) -> dict[str, Any]:
        pr_map = {r["nodeName"]: r["score"] for r in pagerank["topFacilities"]}
        nodes = []
        for f in self.facilities:
            roles = ["OEM"] if f in self.oem else ["SupplierSite"]
            if f.endswith("_prod"):
                roles.append("Production")
            if f.endswith("_inv"):
                roles.append("Inventory")
            nodes.append({
                "id": f"Facility:{f}",
                "caption": f,
                "labels": ["Facility", *roles],
                "score": pr_map.get(f, 0.3),
            })
        rels = []
        for i, arc in enumerate(self.arcs_rows):
            rels.append({
                "id": f"SHIPS:{i}",
                "from": f"Facility:{arc['fromNode']}",
                "to": f"Facility:{arc['toNode']}",
                "type": "SHIPS_TO",
                "leadTime": arc["leadTime"],
                "productGroup": arc["productGroup"],
            })
        return {
            "nodes": nodes,
            "relationships": rels,
            "meta": {
                "nodeCount": len(nodes),
                "relCount": len(rels),
                "oemNodes": sorted(self.oem),
            },
        }

    def export_bom_graph(self, root_id: str) -> dict[str, Any]:
        nodes: dict[str, dict] = {}
        rels: dict[str, dict] = {}
        rel_i = 0

        def add_node(pid: str, score: float = 0.5) -> None:
            if pid in nodes:
                return
            grp = self.product_group.get(pid, "unassigned")
            nodes[pid] = {
                "id": f"Product:{pid}",
                "caption": pid,
                "labels": ["Product", grp],
                "score": score,
            }
            gn = f"ProductGroup:{grp}"
            if gn not in nodes:
                nodes[gn] = {
                    "id": gn,
                    "caption": grp,
                    "labels": ["ProductGroup"],
                    "score": 0.35,
                }

        def add_rel(frm: str, to: str, typ: str) -> None:
            nonlocal rel_i
            rel_i += 1
            rels[f"{typ}:{rel_i}"] = {
                "id": f"{typ}:{rel_i}",
                "from": frm,
                "to": to,
                "type": typ,
            }

        add_node(root_id, 1.0)
        visited = {root_id}
        frontier = {root_id}
        for _ in range(BOM_DEPTH):
            nxt: set[str] = set()
            for pid in frontier:
                grp = self.product_group.get(pid, "unassigned")
                add_rel(f"Product:{pid}", f"ProductGroup:{grp}", "BELONGS_TO")
                for child, _ in self.children.get(pid, []):
                    if child not in visited:
                        visited.add(child)
                        nxt.add(child)
                    add_node(child)
                    add_rel(f"Product:{pid}", f"Product:{child}", "REQUIRES")
                for parent in self.parents.get(pid, set()):
                    if parent not in visited:
                        visited.add(parent)
                        nxt.add(parent)
                    add_node(parent)
                    add_rel(f"Product:{parent}", f"Product:{pid}", "REQUIRES")
                for fac in self.producers.get(pid, set()):
                    fn = f"Facility:{fac}"
                    if fn not in nodes:
                        nodes[fn] = {
                            "id": fn,
                            "caption": fac,
                            "labels": ["Facility"],
                            "score": 0.6,
                        }
                    add_rel(fn, f"Product:{pid}", "PRODUCES")
            frontier = nxt

        node_list = list(nodes.values())
        rel_list = list(rels.values())
        capped = False
        if len(node_list) > GRAPH_NODE_CAP:
            capped = True
            keep = {f"Product:{root_id}"}
            for n in sorted(node_list, key=lambda x: x.get("score", 0), reverse=True):
                if len(keep) >= GRAPH_NODE_CAP:
                    break
                keep.add(n["id"])
            node_list = [n for n in node_list if n["id"] in keep]
            keep_ids = {n["id"] for n in node_list}
            rel_list = [r for r in rel_list if r["from"] in keep_ids and r["to"] in keep_ids]

        return {
            "nodes": node_list,
            "relationships": rel_list,
            "meta": {
                "focusProduct": root_id,
                "nodeCount": len(node_list),
                "relCount": len(rel_list),
                "capped": capped,
            },
        }


def assert_counts(stats: dict, pagerank: dict, data: SupplyChainData) -> None:
    products = next(c["count"] for c in stats["nodeCounts"] if c["label"] == "Product")
    requires = next(c["count"] for c in stats["relCounts"] if c["type"] == "REQUIRES")
    facilities = next(c["count"] for c in stats["nodeCounts"] if c["label"] == "Facility")
    ships = next(c["count"] for c in stats["relCounts"] if c["type"] == "SHIPS_TO")
    assert products == EXPECTED_PRODUCTS, f"products {products}"
    assert requires == EXPECTED_REQUIRES, f"requires {requires}"
    assert facilities == EXPECTED_FACILITIES, f"facilities {facilities}"
    assert ships == EXPECTED_SHIPS_TO, f"ships_to {ships}"
    assert len(pagerank["topFacilities"]) >= 2
    assert pagerank["topFacilities"][0]["nodeName"] in {"zp8", "zp7"}
    print("  asserts OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()

    if not args.xlsx.exists():
        raise SystemExit(f"Workbook not found: {args.xlsx}")

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.xlsx.name} …")
    data = SupplyChainData(args.xlsx)

    print("Building stats …")
    stats = data.build_stats()
    write_json(out / "stats.json", stats)

    print("Building queries …")
    queries = data.eda_queries() + data.analytics_queries()
    write_json(out / "queries.json", queries)

    print("Building PageRank …")
    pagerank = data.build_pagerank()
    write_json(out / "pagerank.json", pagerank)

    print("Building communities (Louvain) …")
    communities = data.build_communities()
    write_json(out / "communities.json", communities)

    print("Building facility graph …")
    facility_graph = data.export_facility_graph(pagerank)
    write_json(out / "graph_facility.json", facility_graph)

    product_index: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pid, source in PRODUCT_SEEDS:
        if pid not in data.product_group or pid in seen:
            continue
        seen.add(pid)
        product_index.append({
            "productId": pid,
            "groupName": data.product_group[pid],
            "slug": slugify(pid),
            "source": source,
        })
        g = data.export_bom_graph(pid)
        write_json(out / f"graph_bom_{slugify(pid)}.json", g)

    write_json(out / "product_index.json", product_index)

    assert_counts(stats, pagerank, data)
    print(f"Done → {out}")


if __name__ == "__main__":
    main()
