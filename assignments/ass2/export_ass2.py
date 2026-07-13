#!/usr/bin/env python3
"""Generate static JSON payloads for the /healthcare demo.

Restores nothing itself — expects a live Neo4j+GDS instance with
healthcare-analytics-50.dump already loaded (see README). Mirrors the
Cypher + GDS workflow in P_Mangoro_C2_assn.ipynb and writes curated
subgraphs (full graph is too large to ship).

Writes into nuxt_neo4j/public/data/healthcare/:
    stats.json, queries.json, similarity.json, communities.json,
    community_index.json, drug_index.json,
    graph_community_<id>.json, graph_drug_<slug>.json

Usage:
    NEO4J_URI=bolt://localhost:7687 NEO4J_AUTH=none \\
      python export_ass2.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent.parent / "nuxt_neo4j" / "public" / "data" / "healthcare"

EXPECTED_NODES = 11381
EXPECTED_RELS = 61453
EXPECTED_REACTIONS = 2701
EXPECTED_COMMUNITIES = 20
GRAPH_NODE_CAP = 220
COMMUNITY_CASE_SAMPLE = 35
DRUG_CASE_CAP = 40
SIMILARITY_LIMIT = 10

SEVERE_OUTCOMES = [
    "Death",
    "Life-Threatening",
    "Disability",
    "Hospitalization - Initial or Prolonged",
]

DRUG_ROLE_RELS = [
    "IS_PRIMARY_SUSPECT",
    "IS_SECONDARY_SUSPECT",
    "IS_CONCOMITANT",
    "IS_INTERACTING",
]

# Notebook-style interpretations matched by reaction signature (GDS versions
# may renumber Leiden communityIds; sizes/signatures stay clinically similar).
COMMENTARY_BY_SIGNATURE: list[tuple[tuple[str, ...], str]] = [
    (("Pneumonia", "Diarrhoea"), "Largest respiratory/GI cluster — often older adults; surveillance for infection and GI events under immunosuppressive or oncology therapy."),
    (("Sinusitis", "Headache"), "Respiratory/infection and adherence cluster (sinusitis, headache, fatigue, dose-omission)."),
    (("Sepsis", "Febrile neutropenia"), "Severe infection / immunocompromised phenotype (sepsis, febrile neutropenia, cytokine-release–like signals)."),
    (("Febrile neutropenia", "Sepsis"), "Severe infection / immunocompromised phenotype (febrile neutropenia, sepsis)."),
    (("Pain", "Drug ineffective"), "Non-specific AE / polypharmacy-like cluster (pain, falls, dizziness, feeling abnormal)."),
    (("Alopecia", "Prostate cancer"), "Oncology sub-phenotype (alopecia, cancer diagnoses, treatment-related trauma)."),
    (("Product dose omission", "Device"), "Device / medication-management phenotype (dose omission, device issues, technique errors)."),
    (("Product quality", "No adverse event"), "Device safety reporting cluster (product quality, insertion/removal complications)."),
    (("No adverse event", "Product quality"), "Device safety reporting cluster (product quality, insertion/removal complications)."),
    (("Chronic kidney", "Acute kidney"), "Renal sub-phenotype (CKD, AKI, renal failure)."),
    (("Nausea", "Fatigue", "Vomiting"), "Common GI adverse-event cluster."),
    (("Death", "Dyspnoea"), "Critical-care / life-threatening outcome cluster — priority for safety review."),
    (("Dyspnoea", "Hypotension"), "Cardiorespiratory severity cluster (dyspnoea, hypotension, fluid issues)."),
    (("Alanine aminotransferase", "Aspartate aminotransferase"), "Hepatotoxicity signal (ALT/AST elevations)."),
    (("Hereditary angioedema",), "Rare-disease / hereditary angioedema treatment cluster."),
    (("COVID-19",), "Pandemic-era COVID-related adverse-event cluster."),
    (("Blindness", "Uveitis"), "Vascular / ocular complications cluster."),
    (("Embolism", "Blindness"), "Vascular / ocular complications cluster."),
]


def commentary_for(top_reactions: list[str], size: int) -> str:
    for keys, text in COMMENTARY_BY_SIGNATURE:
        if all(any(k.lower() in r.lower() for r in top_reactions) for k in keys):
            return text
    lead = ", ".join(top_reactions[:3]) if top_reactions else "mixed reactions"
    return f"Sub-phenotype of {size} cases dominated by {lead}."


COMMUNITIES_INTRO = (
    "Leiden communities summarize each patient sub-phenotype by case count, "
    "top genders, age groups, and adverse reactions. Strong demographic or "
    "reaction concentration suggests a clinically interpretable cluster for "
    "targeted safety surveillance."
)


def load_dotenv() -> None:
    for candidate in (HERE / ".env", HERE.parent.parent / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def connect():
    """Connect using NEO4J_URI + basic auth, or auth=None when NEO4J_AUTH=none.

    Prefer credentials from the environment / .env for a normal Neo4j instance.
    Only set NEO4J_AUTH=none when the server was started with authentication
    disabled (e.g. Docker ``NEO4J_AUTH=none``).
    """
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth_flag = (os.environ.get("NEO4J_AUTH") or "").strip().lower()
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")

    if auth_flag in {"none", "false", "0"}:
        if password:
            print(
                "Note: NEO4J_AUTH=none ignores NEO4J_PASSWORD. "
                "Drop NEO4J_AUTH=none if your server requires a password."
            )
        auth = None
    elif password:
        auth = (user, password)
    else:
        raise SystemExit(
            "Neo4j auth required but NEO4J_PASSWORD is empty.\n"
            "  • Normal instance: set NEO4J_USER / NEO4J_PASSWORD in .env, then:\n"
            "      python export_ass2.py\n"
            "  • Auth-disabled Docker only:\n"
            "      NEO4J_AUTH=none python export_ass2.py"
        )

    print(f"Connecting to {uri} as {'(no auth)' if auth is None else user} …")
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
    except Exception as exc:
        driver.close()
        hint = (
            "If the server requires a password, unset NEO4J_AUTH and use "
            "NEO4J_USER / NEO4J_PASSWORD from .env:\n"
            "  python export_ass2.py"
            if auth is None
            else "Check NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD and that Neo4j is running."
        )
        raise SystemExit(f"Could not connect to Neo4j: {exc}\n{hint}") from exc
    return driver


def run(session, cypher: str, **params) -> list[dict[str, Any]]:
    result = session.run(cypher, **params)
    return [dict(record) for record in result]


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.name} ({path.stat().st_size:,} bytes)")


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_")
    return (s or "drug")[:80]


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
    clean = [{k: jsonable(v) for k, v in row.items()} for row in rows]
    return {
        "id": qid,
        "title": title,
        "description": description,
        "cypher": cypher.strip(),
        "columns": cols,
        "rows": clean,
        "count": len(clean),
    }


# ---------------------------------------------------------------------------
# Stats + EDA / analytics queries
# ---------------------------------------------------------------------------

def build_stats(session) -> dict[str, Any]:
    node_counts = run(
        session,
        """
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN label, count(*) AS count
        ORDER BY count DESC, label
        """,
    )
    rel_counts = run(
        session,
        """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        ORDER BY count DESC, type
        """,
    )
    reactions = run(
        session,
        """
        MATCH (r:Reaction)
        WHERE r.description IS NOT NULL
        RETURN count(DISTINCT r.description) AS n
        """,
    )[0]["n"]
    cases = next(r["count"] for r in node_counts if r["label"] == "Case")
    drugs = next(r["count"] for r in node_counts if r["label"] == "Drug")
    top_severe = run(
        session,
        """
        MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT]-(c:Case)
        MATCH (c)-[:RESULTED_IN]->(o:Outcome)
        WHERE o.outcome IN $severe
        RETURN d.name AS drug_name, count(DISTINCT c) AS severe_cases
        ORDER BY severe_cases DESC
        LIMIT 1
        """,
        severe=SEVERE_OUTCOMES,
    )
    top_mfr = run(
        session,
        """
        MATCH (m:Manufacturer)-[:REGISTERED]->(c:Case)-[:HAS_REACTION]->(r:Reaction)
        MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT|IS_CONCOMITANT|IS_INTERACTING]-(c)
        RETURN m.manufacturerName AS manufacturer, count(DISTINCT d) AS drugs_with_side_effects
        ORDER BY drugs_with_side_effects DESC
        LIMIT 1
        """,
    )
    highlights = [
        {"label": "Nodes", "value": sum(r["count"] for r in node_counts)},
        {"label": "Relationships", "value": sum(r["count"] for r in rel_counts)},
        {"label": "Cases", "value": cases},
        {"label": "Distinct reactions", "value": reactions},
        {"label": "Drugs", "value": drugs},
    ]
    if top_severe:
        highlights.append(
            {"label": f"Top severe drug ({top_severe[0]['drug_name']})", "value": top_severe[0]["severe_cases"]}
        )
    if top_mfr:
        highlights.append(
            {"label": f"Top manufacturer ({top_mfr[0]['manufacturer']})", "value": top_mfr[0]["drugs_with_side_effects"]}
        )
    return {
        "nodeCounts": [{"label": r["label"], "count": r["count"]} for r in node_counts],
        "relCounts": [{"type": r["type"], "count": r["count"]} for r in rel_counts],
        "highlights": highlights,
    }


def build_queries(session) -> list[dict[str, Any]]:
    specs: list[tuple[str, str, str, str, dict[str, Any] | None]] = [
        (
            "eda-nodes",
            "Total nodes",
            "Overall size of the restored FAERS-style graph.",
            "MATCH (n)\nRETURN count(n) AS total_nodes;",
            None,
        ),
        (
            "eda-labels",
            "Node labels",
            "Eight entity types discovered via schema EDA.",
            "CALL db.labels() YIELD label\nRETURN label\nORDER BY label;",
            None,
        ),
        (
            "eda-rels",
            "Total relationships",
            "Directed edge count across all relationship types.",
            "MATCH ()-[r]->()\nRETURN count(r) AS total_relationships;",
            None,
        ),
        (
            "eda-rel-types",
            "Relationship types",
            "Eleven relationship types linking cases, drugs, reactions, and outcomes.",
            "MATCH ()-[r]->()\nRETURN DISTINCT type(r) AS relationship_type\nORDER BY relationship_type;",
            None,
        ),
        (
            "eda-genders",
            "Case genders",
            "Distinct gender values on Case nodes.",
            "MATCH (c:Case)\nWHERE c.gender IS NOT NULL\nRETURN DISTINCT c.gender AS gender\nORDER BY gender;",
            None,
        ),
        (
            "eda-reactions",
            "Distinct reactions",
            "Unique adverse-reaction descriptions in the graph.",
            "MATCH (r:Reaction)\nWHERE r.description IS NOT NULL\nRETURN count(DISTINCT r.description) AS distinct_reactions;",
            None,
        ),
        (
            "eda-outcomes",
            "Outcome descriptions",
            "Seriousness categories used on Outcome nodes.",
            "MATCH (o:Outcome)\nWHERE o.outcome IS NOT NULL\nRETURN DISTINCT o.outcome AS outcome_description\nORDER BY outcome_description;",
            None,
        ),
        (
            "analytics-top-reactions",
            "Top 20 reactions",
            "Most frequent adverse reactions across all cases.",
            """MATCH (c:Case)-[:HAS_REACTION]->(r:Reaction)
WHERE r.description IS NOT NULL
RETURN r.description AS reaction, count(*) AS frequency
ORDER BY frequency DESC
LIMIT 20;""",
            None,
        ),
        (
            "analytics-severe-drugs",
            "Top drugs with severe outcomes",
            "Drugs linked as primary/secondary suspect to cases with Death, Life-Threatening, Disability, or Hospitalization.",
            """MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT]-(c:Case)
MATCH (c)-[:RESULTED_IN]->(o:Outcome)
WHERE o.outcome IN $severe
RETURN d.name AS drug_name, count(DISTINCT c) AS severe_cases
ORDER BY severe_cases DESC
LIMIT 10;""",
            {"severe": SEVERE_OUTCOMES},
        ),
        (
            "analytics-manufacturers",
            "Top manufacturers by drugs with side effects",
            "Manufacturers ranked by distinct drugs appearing on their registered cases that have reactions.",
            """MATCH (m:Manufacturer)-[:REGISTERED]->(c:Case)-[:HAS_REACTION]->(r:Reaction)
MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT|IS_CONCOMITANT|IS_INTERACTING]-(c)
RETURN m.manufacturerName AS manufacturer, count(DISTINCT d) AS drugs_with_side_effects
ORDER BY drugs_with_side_effects DESC
LIMIT 10;""",
            None,
        ),
        (
            "analytics-pfizer",
            "PFIZER top drugs and side effects",
            "Leading PFIZER drugs by case count with a sample of distinct reaction descriptions.",
            """MATCH (m:Manufacturer {manufacturerName: 'PFIZER'})-[:REGISTERED]->(c:Case)-[:HAS_REACTION]->(r:Reaction)
MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT|IS_CONCOMITANT|IS_INTERACTING]-(c)
WHERE r.description IS NOT NULL
RETURN d.name AS drug_name,
       collect(DISTINCT r.description)[0..20] AS side_effects,
       count(DISTINCT c) AS case_count
ORDER BY case_count DESC
LIMIT 5;""",
            None,
        ),
    ]
    out: list[dict[str, Any]] = []
    for qid, title, desc, cypher, params in specs:
        rows = run(session, cypher, **(params or {}))
        out.append(query_entry(qid, title, desc, cypher, rows))
    return out


# ---------------------------------------------------------------------------
# GDS: node similarity + Leiden
# ---------------------------------------------------------------------------

def ensure_patient_journey(session) -> None:
    run(session, "CALL gds.graph.drop('patient-journey', false) YIELD graphName RETURN graphName")
    meta = run(
        session,
        """
        CALL gds.graph.project(
          'patient-journey',
          ['Case','Drug','Reaction'],
          {
            IS_PRIMARY_SUSPECT: { orientation: 'UNDIRECTED' },
            IS_SECONDARY_SUSPECT: { orientation: 'UNDIRECTED' },
            IS_CONCOMITANT: { orientation: 'UNDIRECTED' },
            HAS_REACTION: { orientation: 'UNDIRECTED' }
          }
        )
        YIELD graphName, nodeCount, relationshipCount
        RETURN graphName, nodeCount, relationshipCount
        """,
    )[0]
    print(f"  projected {meta['graphName']}: {meta['nodeCount']} nodes / {meta['relationshipCount']} rels")


def build_similarity(session) -> dict[str, Any]:
    ensure_patient_journey(session)
    rows = run(
        session,
        """
        CALL gds.nodeSimilarity.stream('patient-journey', {
          similarityMetric: 'JACCARD',
          similarityCutoff: 0.2
        })
        YIELD node1, node2, similarity
        WITH gds.util.asNode(node1) AS c1, gds.util.asNode(node2) AS c2, similarity
        WHERE c1:Case AND c2:Case AND elementId(c1) < elementId(c2)
        WITH c1, c2, similarity
        ORDER BY similarity DESC
        LIMIT $limit
        MATCH (c1)-[:HAS_REACTION]->(r:Reaction)<-[:HAS_REACTION]-(c2)
        WITH c1, c2, similarity, collect(DISTINCT r.description) AS shared_reactions
        OPTIONAL MATCH (c1)-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT|IS_CONCOMITANT]->(d:Drug)
               <-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT|IS_CONCOMITANT]-(c2)
        WITH c1, c2, similarity, shared_reactions, collect(DISTINCT d.name) AS shared_drugs
        RETURN
          c1.primaryid AS case1,
          c2.primaryid AS case2,
          similarity,
          size(shared_reactions) AS numSharedReactions,
          shared_reactions[0..5] AS sampleReactions,
          shared_drugs AS sharedDrugs
        ORDER BY similarity DESC
        """,
        limit=SIMILARITY_LIMIT,
    )
    pairs = [
        {
            "case1": str(r["case1"]),
            "case2": str(r["case2"]),
            "similarity": round(float(r["similarity"]), 4),
            "numSharedReactions": int(r["numSharedReactions"]),
            "sampleReactions": list(r["sampleReactions"] or []),
            "sharedDrugs": list(r["sharedDrugs"] or []),
        }
        for r in rows
    ]
    return {"metric": "JACCARD", "cutoff": 0.2, "pairs": pairs}


def ensure_patient_communities(session) -> None:
    run(session, "CALL gds.graph.drop('patient-communities', false) YIELD graphName RETURN graphName")
    meta = run(
        session,
        """
        CALL () {
          MATCH (c:Case)-[r]->(d:Drug)
          WHERE type(r) IN ['IS_PRIMARY_SUSPECT','IS_SECONDARY_SUSPECT','IS_CONCOMITANT','IS_INTERACTING']
          WITH c, d, r ORDER BY elementId(c), elementId(d), type(r)
          RETURN c AS source, d AS target, labels(c) AS sl, labels(d) AS tl, type(r) AS rt,
            CASE type(r) WHEN 'IS_PRIMARY_SUSPECT' THEN 2.0 WHEN 'IS_SECONDARY_SUSPECT' THEN 1.5 ELSE 1.0 END AS w
          UNION ALL
          MATCH (c:Case)-[r:HAS_REACTION]->(rxn:Reaction)
          WITH c, rxn ORDER BY elementId(c), elementId(rxn)
          RETURN c AS source, rxn AS target, labels(c) AS sl, labels(rxn) AS tl, 'HAS_REACTION' AS rt, 1.0 AS w
          UNION ALL
          MATCH (c:Case) WHERE c.gender IS NOT NULL
          WITH DISTINCT c.gender AS g ORDER BY g
          WITH collect(g) AS genders
          UNWIND range(0, size(genders)-1) AS i
          WITH i, genders[i] AS g, 1000000 + i AS vid
          MATCH (c:Case) WHERE c.gender = g
          WITH c, vid ORDER BY elementId(c)
          RETURN c AS source, vid AS target, labels(c) AS sl, ['Gender'] AS tl, 'HAS_GENDER' AS rt, 1.0 AS w
          UNION ALL
          MATCH (c:Case)-[r:FALLS_UNDER]->(ag:AgeGroup)
          WITH c, ag ORDER BY elementId(c), elementId(ag)
          RETURN c AS source, ag AS target, labels(c) AS sl, labels(ag) AS tl, 'FALLS_UNDER' AS rt, 1.0 AS w
          UNION ALL
          MATCH (c:Case)-[r:RESULTED_IN]->(o:Outcome)
          WITH c, o ORDER BY elementId(c), elementId(o)
          RETURN c AS source, o AS target, labels(c) AS sl, labels(o) AS tl, 'RESULTED_IN' AS rt, 1.0 AS w
        }
        WITH gds.graph.project(
          'patient-communities',
          source,
          target,
          {
            sourceNodeLabels: sl,
            targetNodeLabels: tl,
            relationshipType: rt,
            relationshipProperties: { weight: w }
          },
          { undirectedRelationshipTypes: ['*'], consecutiveIds: true }
        ) AS g
        RETURN g.graphName AS graphName, g.nodeCount AS nodeCount, g.relationshipCount AS relationshipCount
        """,
    )[0]
    print(f"  projected {meta['graphName']}: {meta['nodeCount']} nodes / {meta['relationshipCount']} rels")


def build_communities(session) -> tuple[dict[str, Any], dict[int, list[str]]]:
    """Return communities payload + map communityId -> sample case primaryids."""
    ensure_patient_communities(session)

    # Membership for curated subgraphs (Case nodes only).
    membership_rows = run(
        session,
        """
        CALL gds.leiden.stream(
          'patient-communities',
          { relationshipWeightProperty: 'weight', randomSeed: 9, concurrency: 1 }
        )
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS n, communityId
        WHERE n:Case AND n.primaryid IS NOT NULL
        RETURN communityId AS communityId, n.primaryid AS primaryid
        """,
    )
    by_comm: dict[int, list[str]] = defaultdict(list)
    for r in membership_rows:
        by_comm[int(r["communityId"])].append(str(r["primaryid"]))

    profile_rows = run(
        session,
        """
        CALL gds.leiden.stream(
          'patient-communities',
          { relationshipWeightProperty: 'weight', randomSeed: 9, concurrency: 1 }
        )
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS n, communityId
        WHERE n:Case
        WITH communityId, collect(n) AS cases
        WITH communityId, size(cases) AS case_count, cases,
             [c IN cases | elementId(c)] AS case_ids

        UNWIND cases AS c
        MATCH (c)-[:HAS_REACTION]->(r:Reaction)
        WHERE r.description IS NOT NULL
        WITH communityId, case_count, case_ids, r.description AS reaction
        WITH communityId, case_count, case_ids, reaction, count(*) AS rcnt
        ORDER BY communityId, rcnt DESC
        WITH communityId, case_count, case_ids, collect(reaction)[0..5] AS top_reactions

        WITH communityId, case_count, top_reactions, case_ids
        UNWIND case_ids AS cid
        MATCH (c) WHERE elementId(c) = cid
        WITH communityId, case_count, top_reactions, case_ids, collect(c) AS cases

        UNWIND cases AS c
        WITH communityId, case_count, top_reactions, case_ids, c
        WHERE c.gender IS NOT NULL
        WITH communityId, case_count, top_reactions, case_ids, c.gender AS gender
        WITH communityId, case_count, top_reactions, case_ids, gender, count(*) AS gcnt
        ORDER BY communityId, gcnt DESC
        WITH communityId, case_count, top_reactions, case_ids, collect(gender)[0..3] AS top_genders

        WITH communityId, case_count, top_reactions, top_genders, case_ids
        UNWIND case_ids AS cid
        MATCH (c) WHERE elementId(c) = cid
        WITH communityId, case_count, top_reactions, top_genders, case_ids, collect(c) AS cases

        UNWIND cases AS c
        OPTIONAL MATCH (c)-[:FALLS_UNDER]->(ag:AgeGroup)
        WITH communityId, case_count, top_reactions, top_genders, case_ids, ag.ageGroup AS age_group
        WHERE age_group IS NOT NULL
        WITH communityId, case_count, top_reactions, top_genders, case_ids, age_group, count(*) AS agcnt
        ORDER BY communityId, agcnt DESC
        WITH communityId, case_count, top_reactions, top_genders, case_ids, collect(age_group)[0..3] AS top_age_groups

        RETURN communityId, case_count, top_genders, top_age_groups, top_reactions
        ORDER BY case_count DESC
        """,
    )

    communities = []
    for r in profile_rows:
        cid = int(r["communityId"])
        communities.append(
            {
                "id": cid,
                "size": int(r["case_count"]),
                "topGenders": list(r["top_genders"] or []),
                "topAgeGroups": list(r["top_age_groups"] or []),
                "topReactions": list(r["top_reactions"] or []),
                "commentary": commentary_for(list(r["top_reactions"] or []), int(r["case_count"])),
            }
        )

    payload = {
        "communityCount": len(communities),
        "intro": COMMUNITIES_INTRO,
        "communities": communities,
    }
    return payload, dict(by_comm)


# ---------------------------------------------------------------------------
# Curated subgraphs
# ---------------------------------------------------------------------------

def _add_node(nodes: dict[str, dict], nid: str, caption: str, labels: list[str], **extra: Any) -> None:
    if nid in nodes:
        return
    entry = {"id": nid, "caption": caption, "labels": labels}
    entry.update(extra)
    nodes[nid] = entry


def _add_rel(rels: dict[str, dict], rid: str, frm: str, to: str, typ: str) -> None:
    if rid in rels:
        return
    rels[rid] = {"id": rid, "from": frm, "to": to, "type": typ}


def export_case_neighborhood(
    session,
    case_ids: list[str],
    *,
    community: int | None = None,
    include_manufacturer: bool = False,
) -> dict[str, Any]:
    """Build a capped NVL-shaped subgraph around the given Case primaryids."""
    if not case_ids:
        return {"nodes": [], "relationships": [], "meta": {"caseCount": 0, "capped": False}}

    rows = run(
        session,
        """
        UNWIND $ids AS pid
        MATCH (c:Case {primaryid: toInteger(pid)})
        OPTIONAL MATCH (c)-[rd]->(d:Drug)
        WHERE type(rd) IN $drugRels
        OPTIONAL MATCH (c)-[:HAS_REACTION]->(r:Reaction)
        OPTIONAL MATCH (c)-[:RESULTED_IN]->(o:Outcome)
        OPTIONAL MATCH (c)-[:FALLS_UNDER]->(ag:AgeGroup)
        OPTIONAL MATCH (m:Manufacturer)-[:REGISTERED]->(c)
        RETURN
          c.primaryid AS caseId,
          c.gender AS gender,
          c.age AS age,
          collect(DISTINCT {name: d.name, rel: type(rd)}) AS drugs,
          collect(DISTINCT r.description) AS reactions,
          collect(DISTINCT o.outcome) AS outcomes,
          collect(DISTINCT ag.ageGroup) AS ageGroups,
          collect(DISTINCT m.manufacturerName) AS manufacturers
        """,
        ids=case_ids,
        drugRels=DRUG_ROLE_RELS,
    )

    nodes: dict[str, dict] = {}
    rels: dict[str, dict] = {}
    rel_i = 0

    def next_rel(prefix: str) -> str:
        nonlocal rel_i
        rel_i += 1
        return f"{prefix}:{rel_i}"

    for row in rows:
        cid = str(row["caseId"])
        case_nid = f"Case:{cid}"
        caption = f"Case {cid}"
        if row.get("gender"):
            caption += f" ({row['gender']})"
        extra: dict[str, Any] = {}
        if community is not None:
            extra["community"] = community
        _add_node(nodes, case_nid, caption, ["Case"], **extra)

        for d in row["drugs"] or []:
            name = d.get("name")
            if not name:
                continue
            dn = f"Drug:{name}"
            _add_node(nodes, dn, name, ["Drug"])
            typ = d.get("rel") or "IS_PRIMARY_SUSPECT"
            _add_rel(rels, next_rel("CD"), case_nid, dn, typ)

        for desc in row["reactions"] or []:
            if not desc:
                continue
            rn = f"Reaction:{desc}"
            _add_node(nodes, rn, desc, ["Reaction"])
            _add_rel(rels, next_rel("CR"), case_nid, rn, "HAS_REACTION")

        for outcome in row["outcomes"] or []:
            if not outcome:
                continue
            on = f"Outcome:{outcome}"
            _add_node(nodes, on, outcome, ["Outcome"])
            _add_rel(rels, next_rel("CO"), case_nid, on, "RESULTED_IN")

        for ag in row["ageGroups"] or []:
            if not ag:
                continue
            an = f"AgeGroup:{ag}"
            _add_node(nodes, an, ag, ["AgeGroup"])
            _add_rel(rels, next_rel("CA"), case_nid, an, "FALLS_UNDER")

        if include_manufacturer:
            for mfr in row["manufacturers"] or []:
                if not mfr:
                    continue
                mn = f"Manufacturer:{mfr}"
                _add_node(nodes, mn, mfr, ["Manufacturer"])
                _add_rel(rels, next_rel("MC"), mn, case_nid, "REGISTERED")

    # Cap: prefer keeping Cases + their highest-signal neighbors.
    node_list = list(nodes.values())
    capped = False
    if len(node_list) > GRAPH_NODE_CAP:
        capped = True
        # Keep all cases, then fill with Drug/Reaction/Outcome/AgeGroup/Manufacturer by degree.
        cases = [n for n in node_list if n["labels"][0] == "Case"]
        others = [n for n in node_list if n["labels"][0] != "Case"]
        degree: Counter[str] = Counter()
        for r in rels.values():
            degree[r["from"]] += 1
            degree[r["to"]] += 1
        others.sort(key=lambda n: degree[n["id"]], reverse=True)
        keep_ids = {n["id"] for n in cases}
        for n in others:
            if len(keep_ids) >= GRAPH_NODE_CAP:
                break
            keep_ids.add(n["id"])
        node_list = [n for n in node_list if n["id"] in keep_ids]
        rel_list = [r for r in rels.values() if r["from"] in keep_ids and r["to"] in keep_ids]
    else:
        rel_list = list(rels.values())

    return {
        "nodes": node_list,
        "relationships": rel_list,
        "meta": {
            "caseCount": len(case_ids),
            "nodeCount": len(node_list),
            "relCount": len(rel_list),
            "capped": capped,
        },
    }


def build_indexes_and_graphs(
    session,
    out: Path,
    communities_payload: dict[str, Any],
    membership: dict[int, list[str]],
) -> None:
    # Community index + subgraphs
    community_index = []
    for c in communities_payload["communities"]:
        cid = int(c["id"])
        label = ", ".join((c.get("topReactions") or [])[:2]) or f"Community {cid}"
        community_index.append(
            {
                "id": cid,
                "size": c["size"],
                "label": label,
                "topReactions": c.get("topReactions") or [],
            }
        )
        case_ids = membership.get(cid, [])[:COMMUNITY_CASE_SAMPLE]
        graph = export_case_neighborhood(session, case_ids, community=cid)
        write_json(out / f"graph_community_{cid}.json", graph)
    write_json(out / "community_index.json", community_index)

    # Drug index: severe top 10 + PFIZER top 5
    severe = run(
        session,
        """
        MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT]-(c:Case)
        MATCH (c)-[:RESULTED_IN]->(o:Outcome)
        WHERE o.outcome IN $severe
        RETURN d.name AS name, count(DISTINCT c) AS severeCases
        ORDER BY severeCases DESC
        LIMIT 10
        """,
        severe=SEVERE_OUTCOMES,
    )
    pfizer = run(
        session,
        """
        MATCH (m:Manufacturer {manufacturerName: 'PFIZER'})-[:REGISTERED]->(c:Case)-[:HAS_REACTION]->(r:Reaction)
        MATCH (d:Drug)<-[:IS_PRIMARY_SUSPECT|IS_SECONDARY_SUSPECT|IS_CONCOMITANT|IS_INTERACTING]-(c)
        RETURN d.name AS name, count(DISTINCT c) AS caseCount
        ORDER BY caseCount DESC
        LIMIT 5
        """,
    )

    drug_index: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in severe:
        name = r["name"]
        if not name or name in seen:
            continue
        seen.add(name)
        drug_index.append(
            {
                "name": name,
                "slug": slugify(name),
                "severeCases": int(r["severeCases"]),
                "source": "severe",
            }
        )
    for r in pfizer:
        name = r["name"]
        if not name or name in seen:
            continue
        seen.add(name)
        drug_index.append(
            {
                "name": name,
                "slug": slugify(name),
                "caseCount": int(r["caseCount"]),
                "source": "pfizer",
            }
        )

    for entry in drug_index:
        name = entry["name"]
        slug = entry["slug"]
        case_rows = run(
            session,
            """
            MATCH (d:Drug {name: $name})<-[rd]-(c:Case)
            WHERE type(rd) IN $drugRels
            RETURN c.primaryid AS primaryid, type(rd) AS role
            ORDER BY
              CASE type(rd)
                WHEN 'IS_PRIMARY_SUSPECT' THEN 0
                WHEN 'IS_SECONDARY_SUSPECT' THEN 1
                ELSE 2
              END,
              c.primaryid
            LIMIT $limit
            """,
            name=name,
            drugRels=DRUG_ROLE_RELS,
            limit=DRUG_CASE_CAP,
        )
        case_ids = [str(r["primaryid"]) for r in case_rows]
        graph = export_case_neighborhood(session, case_ids, include_manufacturer=True)
        # Ensure the focus drug is present and marked.
        focus = f"Drug:{name}"
        if not any(n["id"] == focus for n in graph["nodes"]):
            graph["nodes"].append({"id": focus, "caption": name, "labels": ["Drug"], "score": 1.0})
        else:
            for n in graph["nodes"]:
                if n["id"] == focus:
                    n["score"] = 1.0
        graph["meta"]["focusDrug"] = name
        write_json(out / f"graph_drug_{slug}.json", graph)

    write_json(out / "drug_index.json", drug_index)


def assert_counts(stats: dict[str, Any], communities: dict[str, Any], similarity: dict[str, Any]) -> None:
    total_nodes = sum(r["count"] for r in stats["nodeCounts"])
    total_rels = sum(r["count"] for r in stats["relCounts"])
    reactions = next(h["value"] for h in stats["highlights"] if h["label"] == "Distinct reactions")
    assert total_nodes == EXPECTED_NODES, f"nodes {total_nodes} != {EXPECTED_NODES}"
    assert total_rels == EXPECTED_RELS, f"rels {total_rels} != {EXPECTED_RELS}"
    assert reactions == EXPECTED_REACTIONS, f"reactions {reactions} != {EXPECTED_REACTIONS}"
    assert communities["communityCount"] == EXPECTED_COMMUNITIES, (
        f"communities {communities['communityCount']} != {EXPECTED_COMMUNITIES}"
    )
    assert len(similarity["pairs"]) >= 5, "expected similarity pairs"
    print("  asserts OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    load_dotenv()
    driver = connect()
    try:
        with driver.session() as session:
            # GDS availability
            ver = run(session, "RETURN gds.version() AS v")[0]["v"]
            print(f"GDS {ver}")

            print("Building stats …")
            stats = build_stats(session)
            write_json(out / "stats.json", stats)

            print("Building queries …")
            queries = build_queries(session)
            write_json(out / "queries.json", queries)

            print("Building similarity (GDS nodeSimilarity) …")
            similarity = build_similarity(session)
            write_json(out / "similarity.json", similarity)

            print("Building communities (GDS Leiden) …")
            communities, membership = build_communities(session)
            write_json(out / "communities.json", communities)

            print("Building curated subgraphs …")
            build_indexes_and_graphs(session, out, communities, membership)

            assert_counts(stats, communities, similarity)
            print(f"Done → {out}")

            # Drop in-memory GDS graphs before closing the session.
            run(session, "CALL gds.graph.drop('patient-journey', false) YIELD graphName RETURN graphName")
            run(session, "CALL gds.graph.drop('patient-communities', false) YIELD graphName RETURN graphName")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
