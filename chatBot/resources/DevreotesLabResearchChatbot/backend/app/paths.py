from pathlib import Path


BACKEND_APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BACKEND_APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

DOTENV_PATH = PROJECT_ROOT / ".env"
HGNC_LOOKUP_PATH = PROJECT_ROOT / "hgnc_lookup.json"
PAPERS_DIR = PROJECT_ROOT / "papers"
EXTRACTED_DIR = PROJECT_ROOT / "extracted"


def resolve_project_path(value: str | None, default_path: Path) -> Path:
    if value is None:
        return default_path
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p
