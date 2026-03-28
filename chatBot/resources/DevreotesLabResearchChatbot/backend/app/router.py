import re


def classify_query(question: str) -> str:
    """
    Classify the user's question.
    Returns: 'gene', 'author', 'themes', or 'semantic'

    Note: 'themes' maps to graph aggregate **gene mention frequency** across papers,
    not a qualitative topic model. See `graph_search_research_themes` in retrieval.

    Order matters: themes and author-style questions should win over generic gene
    vocabulary (e.g. "main research themes about kinases" → themes, not gene).
    """
    q = question.lower()

    # Avoid matching "gene" inside unrelated words (e.g. "general", "oxygen").
    gene_vocab = [
        "protein",
        "enzyme",
        "kinase",
        "receptor",
        "pten",
        "ras",
        "pi3k",
        "gpcr",
        "camp",
    ]
    author_keywords = [
        "author",
        "collaborat",
        "co-author",
        "who wrote",
        "researcher",
        "scientist",
        "devreotes",
        "principal",
        "written by",
        "papers by",
        "publications by",
    ]
    theme_keywords = [
        "theme",
        "themes",
        "topic",
        "topics",
        "focus",
        "research overview",
        "overview of the lab",
        "lab overview",
        "overview of the papers",
        "main research",
        "research focus",
        "research themes",
        "what does the lab",
        "what has the lab",
        "what are the main",
        "summary",
        "field",
        "corpus",
        "across the papers",
        "across papers",
        "gene frequency",
        "most cited",
        "most mentioned",
        "most common",
        "most frequent",
        "prevalence",
        "bibliometric",
    ]

    if any(kw in q for kw in theme_keywords):
        return "themes"

    # Corpus-wide ranking over gene families (avoid misrouting to single-gene retrieval).
    if re.search(
        r"\b(which|what)\s+(genes|kinases|receptors|proteins|enzymes|gpcrs)\b.*\b(most|main|top|common|frequent|often|mentioned|discussed|cited)\b",
        q,
    ) or re.search(
        r"\b(most|main|top)\s+(common|frequent|mentioned|discussed|often|cited)\b.*\b(genes|kinases|kinase|receptors|proteins|enzymes|gpcrs)\b",
        q,
    ):
        return "themes"

    if any(kw in q for kw in author_keywords):
        return "author"
    if re.search(r"\bgenes?\b", q) or any(kw in q for kw in gene_vocab):
        return "gene"
    return "semantic"


def extract_gene_from_question(question: str, hgnc_lookup: dict):
    if not hgnc_lookup:
        return None
    for raw in re.split(r"[^\w]+", question):
        if not raw:
            continue
        clean = raw.strip("_,.'\"()[]{}").upper()
        if len(clean) < 2:
            continue
        if clean in hgnc_lookup:
            return clean
    upper_q = question.upper()
    for m in re.finditer(r"\b[A-Z][A-Z0-9]{1,15}\b", upper_q):
        tok = m.group(0)
        if tok in hgnc_lookup:
            return tok
    return None


def extract_author_from_question(question: str) -> str | None:
    """
    Best-effort author name; chatbot may still default to Devreotes when None.
    Case-insensitive; supports "papers by ...", two-word names, etc.
    """
    q = question.strip()
    patterns = [
        r"(?:papers?|publications?|work)\s+by\s+([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){0,3})",
        r"(?:written\s+by|authored\s+by)\s+([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){0,3})",
        r"\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
        r"\bauthor\s+([A-Za-z][A-Za-z'\-]+)\b",
        r"\b([A-Z][a-z]+)'s\s+papers\b",
        r"\b(?:collaborator|researcher)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        r"\bfrom\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:lab|group)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, q, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) > 2 and name.lower() not in {"the", "and", "for", "lab"}:
                return name
    return None
