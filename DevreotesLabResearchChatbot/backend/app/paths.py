import os
from pathlib import Path


BACKEND_APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BACKEND_APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Default single-file path (for docs); actual loading uses `load_project_dotenv()`.
DOTENV_PATH = PROJECT_ROOT / ".env"


def load_project_dotenv() -> None:
    """Load `.env` from the Devreotes project root, with optional production overlay.

    1. If ``DEVREOTES_DOTENV`` is set, load only that file (relative paths are under ``PROJECT_ROOT``).
    2. Else load ``.env`` if present; if ``DEVREOTES_USE_PRODUCTION_ENV`` is truthy, load
       ``.env.production`` with ``override=True`` (e.g. Neo4j Aura ``NEO4J_*`` in production).
    """
    from dotenv import load_dotenv

    explicit = os.getenv("DEVREOTES_DOTENV", "").strip()
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        load_dotenv(p)
        return

    base = PROJECT_ROOT / ".env"
    if base.is_file():
        load_dotenv(base)

    use_prod = os.getenv("DEVREOTES_USE_PRODUCTION_ENV", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if use_prod:
        prod = PROJECT_ROOT / ".env.production"
        if prod.is_file():
            load_dotenv(prod, override=True)
HGNC_LOOKUP_PATH = PROJECT_ROOT / "hgnc_lookup.json"
PAPERS_DIR = PROJECT_ROOT / "papers"
EXTRACTED_DIR = PROJECT_ROOT / "extracted"


def resolve_project_path(value: str | None, default_path: Path) -> Path:
    if value is None:
        return default_path
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p


# Sentence-Transformers Hugging Face id — must match between create_embeddings.py and retrieval.py.
DEFAULT_EMBEDDING_MODEL = "pritamdeka/PubMedBERT-mnli-snli-scinli-scitail-mednli-stsb"


def embedding_model_name() -> str:
    """Model used to encode chunks (offline) and queries (online). Change only with full re-embed."""
    raw = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    s = (raw or "").strip()
    return s if s else DEFAULT_EMBEDDING_MODEL
