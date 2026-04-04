"""
Map Crossref /works/{doi} `message` JSON into fields for extracted paper JSON.

Used by backend/scripts/enrich_extracted_crossref.py (no HTTP here).
"""

from __future__ import annotations

import html
import re
from typing import Any


def _first_str(val: Any, max_len: int = 2000) -> str | None:
    if val is None:
        return None
    if isinstance(val, list):
        if not val:
            return None
        s = str(val[0]).strip()
    elif isinstance(val, str):
        s = val.strip()
    else:
        s = str(val).strip()
    if not s:
        return None
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len] if len(s) > max_len else s


def _date_year(msg: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        block = msg.get(key)
        if not isinstance(block, dict):
            continue
        parts = block.get("date-parts")
        if not parts or not isinstance(parts, list) or not parts[0]:
            continue
        y = parts[0][0]
        if isinstance(y, int) and 1900 <= y <= 2100:
            return y
    return None


def _authors(msg: dict) -> list[dict[str, str | None]]:
    raw = msg.get("author") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str | None]] = []
    for a in raw[:80]:
        if not isinstance(a, dict):
            continue
        aff = None
        affs = a.get("affiliation")
        if isinstance(affs, list) and affs and isinstance(affs[0], dict):
            aff = _first_str(affs[0].get("name"), 400)
        given = _first_str(a.get("given"), 200)
        family = _first_str(a.get("family"), 200)
        name = _first_str(a.get("name"), 300)
        seq = a.get("sequence")
        out.append(
            {
                "given": given,
                "family": family,
                "name": name,
                "sequence": str(seq) if seq else None,
                "affiliation": aff,
            }
        )
    return out


def crossref_structured_authors_to_display_names(rows: list[dict[str, Any]]) -> list[str]:
    """
    Turn Crossref-style author dicts (from _authors) into ordered display strings for JSON / ingest.
    """
    out: list[str] = []
    for a in rows:
        if not isinstance(a, dict):
            continue
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        name = (a.get("name") or "").strip()
        if given and family:
            s = f"{given} {family}".strip()
        elif name:
            s = name
        else:
            s = (family or given or "").strip()
        if not s:
            continue
        s = s[:200]
        if s not in out:
            out.append(s)
    return out


def _issn_list(msg: dict) -> list[str]:
    issn = msg.get("ISSN") or msg.get("issn-type")
    if not isinstance(issn, list):
        return []
    out: list[str] = []
    for x in issn:
        if isinstance(x, str) and x.strip():
            out.append(x.strip()[:32])
        elif isinstance(x, dict) and x.get("value"):
            v = str(x["value"]).strip()
            if v:
                out.append(v[:32])
    return out[:4]


def message_to_enrichment(message: dict) -> dict[str, Any]:
    """
    Build a dict safe to merge into extracted JSON.

    Top-level keys for ingest: title, year, journal (when caller applies them).
    Everything else is intended for nested `crossref` in the JSON file.
    """
    title = _first_str(message.get("title"), 800)
    subtitle = _first_str(message.get("subtitle"), 500)
    journal = _first_str(message.get("container-title"), 500)
    year = _date_year(message)
    vol = _first_str(message.get("volume"), 32)
    issue = _first_str(message.get("issue"), 32)
    page = _first_str(message.get("page"), 64)
    publisher = _first_str(message.get("publisher"), 400)
    typ = _first_str(message.get("type"), 80)
    url = _first_str(message.get("URL"), 512)
    doi_from_api = _first_str(message.get("DOI"), 256)

    structured_authors = _authors(message)
    authors_display = crossref_structured_authors_to_display_names(structured_authors)

    crossref_block: dict[str, Any] = {
        "publisher": publisher,
        "type": typ,
        "url": url,
        "volume": vol,
        "issue": issue,
        "page": page,
        "subtitle": subtitle,
        "issn": _issn_list(message) or None,
        "authors": structured_authors or None,
    }
    if doi_from_api:
        crossref_block["doi"] = doi_from_api

    # Drop None values for cleaner JSON
    crossref_block = {k: v for k, v in crossref_block.items() if v is not None}

    return {
        "title": title,
        "year": year,
        "journal": journal,
        "authors": authors_display,
        "crossref": crossref_block,
    }
