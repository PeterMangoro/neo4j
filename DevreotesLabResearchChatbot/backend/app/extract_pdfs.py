import json
import re
import fitz

from .paths import EXTRACTED_DIR, PAPERS_DIR, resolve_project_path


_JUNK_TITLE_PATTERNS = [
    r"^\s*\d+\s*$",
    r"^\s*(abstract|introduction|materials\s+and\s+methods|methods|results|discussion|references)\s*$",
    r"^\s*copyright\s*",
    r"^\s*all\s+rights\s+reserved\s*$",
    r"^\s*the\s+journal\s+of\s+",
    r"^\s*doi\s*:\s*",
    r"^\s*http[s]?://",
]


def _normalize_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _title_from_lines(text: str, fallback: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return fallback

    candidates = lines[:50]
    best = ""
    best_score = -1
    for ln in candidates:
        t = _normalize_title(ln)
        if len(t) < 6 or len(t) > 220:
            continue
        low = t.lower()
        if any(re.search(pat, low, flags=re.IGNORECASE) for pat in _JUNK_TITLE_PATTERNS):
            continue
        letters = sum(ch.isalpha() for ch in t)
        digits = sum(ch.isdigit() for ch in t)
        symbols = sum((not ch.isalnum()) and (not ch.isspace()) for ch in t)
        score = letters - 2 * digits - 3 * symbols
        if score > best_score:
            best = t
            best_score = score

    return best[:500] if best else _normalize_title(lines[0])[:500] if lines else fallback


def _title_from_pdf_metadata(doc: fitz.Document) -> str:
    meta = getattr(doc, "metadata", None) or {}
    title = _normalize_title(meta.get("title") or "")
    if not title:
        return ""
    if title.lower().startswith(("microsoft word", "untitled", "doc", "document")):
        return ""
    return title[:500]


def _pdf_meta_dict(doc: fitz.Document) -> dict:
    """PyMuPDF metadata fields (often empty; safe to store as hints)."""
    meta = getattr(doc, "metadata", None) or {}
    out = {}
    for key in ("author", "subject", "keywords", "creator", "producer", "format"):
        val = meta.get(key)
        if val and str(val).strip():
            out[f"pdf_{key}"] = _normalize_title(str(val))[:2000]
    return out


def _heuristic_bibliography(text: str) -> dict:
    """
    Best-effort DOI / year / journal from first pages of extracted text (no external APIs).
    """
    head = (text or "")[:14000]
    out: dict = {"doi": None, "year": None, "journal": None}

    m = re.search(r"\b(10\.\d{4,}/[^\s\]\)\"']+)", head, re.IGNORECASE)
    if m:
        doi = m.group(1).rstrip(".,;)]}")
        out["doi"] = doi[:256]

    for m in re.finditer(r"\b(19[89]\d|20[0-3]\d)\b", head):
        y = int(m.group(1))
        if 1980 <= y <= 2035:
            out["year"] = y
            break

    journal_patterns = [
        r"(?:Published in|Journal(?:\s+name)?[:]\s*)([^\n.]{6,120})",
        r"^([A-Z][A-Za-z\s&\-]{8,80}(?:Journal|Letters|Proceedings|Review))\s*$",
    ]
    for pat in journal_patterns:
        jm = re.search(pat, head, re.MULTILINE)
        if jm:
            j = _normalize_title(jm.group(1))
            if 10 < len(j) < 200 and not j.lower().startswith("http"):
                out["journal"] = j[:200]
                break

    return out


def extract_text_from_pdfs(papers_dir: str | None = None, output_dir: str | None = None):
    papers_path = resolve_project_path(papers_dir, PAPERS_DIR)
    output_path = resolve_project_path(output_dir, EXTRACTED_DIR)
    if not papers_path.is_dir():
        raise FileNotFoundError(f"Missing papers directory: {papers_path}")

    output_path.mkdir(parents=True, exist_ok=True)
    results = []

    for pdf_path in papers_path.iterdir():
        if pdf_path.suffix.lower() != ".pdf":
            continue

        paper_id = pdf_path.stem

        doc = fitz.open(str(pdf_path))
        meta_title = _title_from_pdf_metadata(doc)
        pdf_meta = _pdf_meta_dict(doc)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        full_text = full_text.replace("\n\n\n", "\n\n").strip()
        title = meta_title or _title_from_lines(full_text[:20000], paper_id)
        bib = _heuristic_bibliography(full_text)

        output = {
            "paper_id": paper_id,
            "title": title,
            "filename": pdf_path.name,
            "text": full_text,
            "doi": bib.get("doi"),
            "year": bib.get("year"),
            "journal": bib.get("journal"),
            **pdf_meta,
        }

        out_path = output_path / f"{paper_id}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(output, f)

        results.append(output)
        print(f"Extracted: {pdf_path.name} ({len(full_text)} chars)")

    print(f"Total papers extracted: {len(results)}")
    return results


if __name__ == "__main__":
    extract_text_from_pdfs()
