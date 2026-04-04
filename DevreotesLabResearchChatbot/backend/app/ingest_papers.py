import json
import os
import re
import spacy
from neo4j import GraphDatabase

from .crossref_metadata import crossref_structured_authors_to_display_names
from .doi_utils import normalize_doi_for_storage
from .paths import EXTRACTED_DIR, HGNC_LOOKUP_PATH, load_project_dotenv, resolve_project_path


load_project_dotenv()
nlp = spacy.load("en_core_sci_lg")

# Supplement scispaCy gene mentions with HGNC token scan (Phase 4)
_SUPPLEMENT_TOKEN_GENES = os.getenv("INGEST_SUPPLEMENT_TOKEN_GENES", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Tokens that are not person names when scraped from PDF headers
_AUTHOR_TOKEN_BLOCKLIST = frozenset(
    {
        "the",
        "and",
        "for",
        "author",
        "authors",
        "correspondence",
        "corresponding",
        "affiliation",
        "affiliations",
        "department",
        "university",
        "institute",
        "institution",
        "college",
        "school",
        "medical",
        "center",
        "centre",
        "laboratory",
        "lab",
        "division",
        "fig",
        "figure",
        "table",
        "abstract",
        "introduction",
        "methods",
        "results",
        "discussion",
        "received",
        "accepted",
        "published",
        "copyright",
        "keywords",
        "email",
        "phone",
        "fax",
        "usa",
        "inc",
        "ltd",
        "llc",
        "press",
        "journal",
        "vol",
        "issue",
        "doi",
        "http",
        "https",
        "www",
        "et",
        "al",
        "dr",
        "mr",
        "ms",
        "prof",
    }
)


def _load_hgnc_lookup() -> dict:
    if not HGNC_LOOKUP_PATH.exists():
        raise FileNotFoundError(f"Missing {HGNC_LOOKUP_PATH}. Run download_hgnc.py first.")
    with HGNC_LOOKUP_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not all([uri, user, password]):
        raise RuntimeError("Missing Neo4j credentials in .env.")
    return GraphDatabase.driver(uri, auth=(user, password))


def normalize_author_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower())
    return key.strip("_")


def chunk_text(text: str, chunk_chars: int = 2000, overlap_chars: int = 200):
    text = (text or "").strip()
    if not text:
        return []
    if overlap_chars >= chunk_chars:
        overlap_chars = max(0, chunk_chars // 5)

    chunks = []
    start = 0
    idx = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((idx, chunk))
            idx += 1
        if end >= n:
            break
        start = end - overlap_chars
    return chunks


def _claim_from_chunk(chunk_text_value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (chunk_text_value or "").strip())
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    claim = parts[0] if parts else cleaned
    return claim[:280]


def _build_chunk_rows(paper_data: dict):
    paper_id = paper_data["paper_id"]
    rows = []
    for idx, chunk in chunk_text(paper_data.get("text", ""), chunk_chars=2000, overlap_chars=200):
        rows.append(
            {
                "chunk_id": f"{paper_id}_{idx}",
                "paper_id": paper_id,
                "chunk_index": idx,
                "text": chunk,
            }
        )
    return rows


def find_genes_in_text(text: str, hgnc_lookup: dict):
    """scispaCy entities plus optional ALLCAPS token pass validated against HGNC only."""
    found_genes = {}
    doc = nlp(text[:50000])
    for ent in doc.ents:
        token = ent.text.strip().upper()
        if token in hgnc_lookup:
            gene = hgnc_lookup[token]
            found_genes[gene["hgnc_id"]] = gene

    if _SUPPLEMENT_TOKEN_GENES and hgnc_lookup:
        head = (text or "")[:80000]
        for m in re.finditer(r"\b[A-Z][A-Z0-9]{1,12}\b", head):
            tok = m.group(0)
            if tok in hgnc_lookup:
                gene = hgnc_lookup[tok]
                found_genes[gene["hgnc_id"]] = gene

    return list(found_genes.values())


def _pdf_author_metadata_trustworthy(raw: str | None) -> bool:
    """False for tool strings / garbage so we fall back to text heuristics."""
    if not raw or len(raw.strip()) < 3:
        return False
    s = raw.strip()
    if len(s) > 800:
        return False
    low = s.lower()
    junk_markers = (
        "microsoft word",
        "microsoft corporation",
        "adobe",
        "acrobat distiller",
        "acrobat pdf",
        "endnote",
        "latex with hyperref",
        "quarkxpress",
        "phantompdf",
        "primopdf",
        "pdf-xchange",
        "scansoft",
        "wkhtmltopdf",
    )
    if any(m in low for m in junk_markers):
        return False
    letters = sum(c.isalpha() for c in s)
    if letters < 4:
        return False
    if letters < len(s) * 0.25 and len(s) > 30:
        return False
    return True


def _is_plausible_display_author(name: str) -> bool:
    n = (name or "").strip()
    if len(n) < 4 or len(n) > 120:
        return False
    low = n.lower()
    if low in _AUTHOR_TOKEN_BLOCKLIST:
        return False
    if sum(c.isalpha() for c in n) < 3:
        return False
    if n.lower().startswith("http"):
        return False
    tokens = re.findall(r"[A-Za-z][a-zA-Z'\-]+", n)
    if not tokens:
        return False
    bad = sum(1 for t in tokens if t.lower() in _AUTHOR_TOKEN_BLOCKLIST)
    if bad >= len(tokens):
        return False
    return True


def _split_pdf_author_line(pdf_author: str) -> list[str]:
    raw = (pdf_author or "").replace("\n", " ").strip()
    if len(raw) < 3:
        return []
    if ";" in raw:
        parts = [p.strip() for p in raw.split(";") if p.strip()]
    elif re.search(r"\s+and\s+", raw, re.I):
        parts = [p.strip() for p in re.split(r"\s+and\s+", raw, flags=re.I) if p.strip()]
    else:
        parts = [raw]
    out = []
    for p in parts[:15]:
        cleaned = re.sub(r"\s+", " ", p).strip()
        if 2 < len(cleaned) < 120 and _is_plausible_display_author(cleaned):
            out.append(cleaned)
    return out[:10]


def authors_from_crossref_json_field(paper_data: dict) -> list[str] | None:
    """Use top-level `authors` list (strings) when present — e.g. from enrich_extracted_crossref."""
    raw = paper_data.get("authors")
    if not isinstance(raw, list) or not raw:
        return None
    out: list[str] = []
    for x in raw:
        if isinstance(x, str):
            s = x.strip()
            if len(s) >= 2 and not s.lower().startswith("http"):
                out.append(s[:200])
    return out if out else None


def crossref_enrichment_ok(paper_data: dict) -> bool:
    """True when extracted JSON has a successful Crossref /works payload (not an error stub)."""
    cr = paper_data.get("crossref")
    return isinstance(cr, dict) and "error" not in cr


def resolve_bibliography_for_ingest(paper_data: dict) -> dict:
    """
    Paper fields for Neo4j: prefer Crossref-backed values when enrichment succeeded.

    Title / year / journal use top-level JSON (set by enrich script on HTTP 200).
    DOI prefers ``crossref.doi`` when present so it stays aligned with the registry id.
    """
    title = paper_data.get("title") or ""
    year = paper_data.get("year")
    journal = paper_data.get("journal")
    cr = paper_data.get("crossref") if crossref_enrichment_ok(paper_data) else None
    raw_doi = None
    if isinstance(cr, dict) and cr.get("doi"):
        raw_doi = cr.get("doi")
    elif paper_data.get("doi"):
        raw_doi = paper_data.get("doi")
    doi = normalize_doi_for_storage(str(raw_doi).strip()) if raw_doi and str(raw_doi).strip() else None
    return {"title": title, "year": year, "journal": journal, "doi": doi}


def resolve_authors_for_ingest(paper_data: dict) -> list[str]:
    """
    Order: top-level ``authors`` strings → structured ``crossref.authors`` → PDF metadata / text heuristics.
    """
    from_strings = authors_from_crossref_json_field(paper_data)
    if from_strings:
        return from_strings
    if crossref_enrichment_ok(paper_data):
        cr = paper_data.get("crossref") or {}
        struct = cr.get("authors")
        if isinstance(struct, list) and struct and isinstance(struct[0], dict):
            names = crossref_structured_authors_to_display_names(struct)
            if names:
                return names
    return extract_authors_from_text(
        paper_data.get("text", ""),
        pdf_author=paper_data.get("pdf_author"),
    )


def extract_authors_from_text(text: str, pdf_author: str | None = None):
    """
    Prefer PDF metadata author when trustworthy; otherwise scan front matter for author lines.
    """
    if pdf_author and _pdf_author_metadata_trustworthy(pdf_author):
        from_meta = _split_pdf_author_line(pdf_author)
        if from_meta:
            return from_meta

    authors = []
    lines = text.split("\n")[:45]
    for line in lines:
        lower = line.lower().strip()
        if any(kw in lower for kw in ["author", "correspondence", "affiliation"]):
            segment = line
            for prefix in ("author", "authors", "author information", "correspondence"):
                if lower.startswith(prefix):
                    idx = line.lower().find(prefix)
                    segment = line[idx + len(prefix) :].lstrip(" :;\t")
                    break
            for sep in (";", ","):
                if sep in segment:
                    chunks = [c.strip() for c in segment.split(sep) if c.strip()]
                    names = []
                    for ch in chunks[:12]:
                        words = ch.replace(" and ", " ").split()
                        for w in words:
                            w = w.strip(".,;")
                            if (
                                len(w) > 2
                                and w[0].isupper()
                                and w.lower() not in _AUTHOR_TOKEN_BLOCKLIST
                            ):
                                names.append(w)
                    if names:
                        authors = [n for n in names[:10] if _is_plausible_display_author(n)]
                        if authors:
                            break
            if authors:
                break
            parts = line.replace(",", " ").replace(";", " ").replace(" and ", " ").split()
            names = [
                p.strip(".,;")
                for p in parts
                if p
                and p[0].isupper()
                and len(p) > 2
                and p.strip(".,;").lower() not in _AUTHOR_TOKEN_BLOCKLIST
            ]
            if names:
                authors = [n for n in names[:10] if _is_plausible_display_author(n)]
                if authors:
                    break
    return authors


def load_paper(session, paper_data: dict, genes: list, authors: list, chunk_rows: list):
    bib = resolve_bibliography_for_ingest(paper_data)
    session.run(
        """
        MERGE (p:Paper {paper_id: $paper_id})
        SET p.title = $title,
            p.filename = $filename,
            p.source_file = $filename,
            p.text_preview = $text_preview,
            p.doi = $doi,
            p.year = $year,
            p.journal = $journal,
            p.pdf_author = $pdf_author,
            p.pdf_subject = $pdf_subject,
            p.pdf_keywords = $pdf_keywords,
            p.pdf_creator = $pdf_creator,
            p.pdf_producer = $pdf_producer,
            p.pdf_format = $pdf_format,
            p.text_via_ocr = $text_via_ocr
        """,
        paper_id=paper_data["paper_id"],
        title=bib["title"],
        text_preview=(paper_data.get("text") or "")[:500],
        filename=paper_data["filename"],
        text_via_ocr=bool(paper_data.get("text_via_ocr")),
        doi=bib["doi"],
        year=bib["year"],
        journal=bib["journal"],
        pdf_author=paper_data.get("pdf_author"),
        pdf_subject=paper_data.get("pdf_subject"),
        pdf_keywords=paper_data.get("pdf_keywords"),
        pdf_creator=paper_data.get("pdf_creator"),
        pdf_producer=paper_data.get("pdf_producer"),
        pdf_format=paper_data.get("pdf_format"),
    )

    if chunk_rows:
        session.run(
            """
            MATCH (p:Paper {paper_id: $paper_id})
            UNWIND $rows AS row
            MERGE (c:Chunk {chunk_id: row.chunk_id})
            SET c.paper_id = row.paper_id,
                c.chunk_index = row.chunk_index,
                c.text = row.text
            MERGE (p)-[:HAS_CHUNK]->(c)
            """,
            paper_id=paper_data["paper_id"],
            rows=chunk_rows,
        )

    for gene in genes:
        session.run(
            """
            MERGE (g:Gene {hgnc_id: $hgnc_id})
            SET g.official_symbol = $symbol
            WITH g
            MATCH (p:Paper {paper_id: $paper_id})
            MERGE (p)-[:MENTIONS]->(g)
            MERGE (e:Entity {entity_key: $entity_key})
            SET e.type = 'GENE', e.name = $symbol
            MERGE (p)-[:HAS_TOPIC]->(e)
            MERGE (e)-[:RELATED_TO]->(g)
            """,
            hgnc_id=gene["hgnc_id"],
            symbol=gene["official_symbol"],
            entity_key=f"gene:{gene['official_symbol'].upper()}",
            paper_id=paper_data["paper_id"],
        )

    for author_name in authors:
        author_key = normalize_author_key(author_name) or author_name.lower()
        session.run(
            """
            MERGE (a:Author {author_key: $author_key})
            SET a.name = $name
            WITH a
            MATCH (p:Paper {paper_id: $paper_id})
            MERGE (a)-[:AUTHORED]->(p)
            MERGE (e:Entity {entity_key: $entity_key})
            SET e.type = 'AUTHOR', e.name = $name
            MERGE (p)-[:HAS_TOPIC]->(e)
            """,
            author_key=author_key,
            name=author_name,
            entity_key=f"author:{author_key}",
            paper_id=paper_data["paper_id"],
        )

    for row in chunk_rows:
        chunk_id = row["chunk_id"]
        chunk_text_value = row["text"]
        chunk_lower = chunk_text_value.lower()

        for gene in genes:
            symbol = (gene.get("official_symbol") or "").strip()
            if symbol and symbol.lower() in chunk_lower:
                entity_key = f"gene:{symbol.upper()}"
                session.run(
                    """
                    MATCH (c:Chunk {chunk_id: $chunk_id})
                    MERGE (e:Entity {entity_key: $entity_key})
                    SET e.type = 'GENE', e.name = $symbol
                    MERGE (c)-[:MENTIONS]->(e)
                    """,
                    chunk_id=chunk_id,
                    entity_key=entity_key,
                    symbol=symbol,
                )

        claim_text = _claim_from_chunk(chunk_text_value)
        if claim_text:
            claim_id = f"{paper_data['paper_id']}_claim_{row['chunk_index']}"
            session.run(
                """
                MATCH (c:Chunk {chunk_id: $chunk_id})
                MERGE (cl:Claim {claim_id: $claim_id})
                SET cl.text = $text
                MERGE (cl)-[:SUPPORTS]->(c)
                """,
                chunk_id=chunk_id,
                claim_id=claim_id,
                text=claim_text,
            )

            for gene in genes:
                symbol = (gene.get("official_symbol") or "").strip()
                if symbol and symbol.lower() in chunk_lower:
                    entity_key = f"gene:{symbol.upper()}"
                    session.run(
                        """
                        MATCH (cl:Claim {claim_id: $claim_id})
                        MERGE (e:Entity {entity_key: $entity_key})
                        SET e.type = 'GENE', e.name = $symbol
                        MERGE (cl)-[:ABOUT]->(e)
                        """,
                        claim_id=claim_id,
                        entity_key=entity_key,
                        symbol=symbol,
                    )


def ingest_all_papers(extracted_dir: str | None = None):
    extracted_path = resolve_project_path(extracted_dir, EXTRACTED_DIR)
    if not extracted_path.is_dir():
        raise FileNotFoundError(f"Missing extracted directory: {extracted_path}")

    hgnc_lookup = _load_hgnc_lookup()
    driver = _get_driver()
    papers = []

    with driver.session() as session:
        for filename in os.listdir(extracted_path):
            if not filename.endswith(".json"):
                continue
            path = extracted_path / filename
            with path.open("r", encoding="utf-8") as f:
                paper_data = json.load(f)

            bib = resolve_bibliography_for_ingest(paper_data)
            print(f"Processing: {bib.get('title', '')[:60]}...")
            genes = find_genes_in_text(paper_data.get("text", ""), hgnc_lookup)
            authors = resolve_authors_for_ingest(paper_data)
            chunk_rows = _build_chunk_rows(paper_data)
            load_paper(session, paper_data, genes, authors, chunk_rows)
            print(
                f"  -> {len(chunk_rows)} chunks, {len(genes)} genes, {len(authors)} authors loaded"
            )
            papers.append(paper_data)

    driver.close()
    print(f"Ingestion complete: {len(papers)} papers loaded into Neo4j")
    return papers


if __name__ == "__main__":
    ingest_all_papers()
