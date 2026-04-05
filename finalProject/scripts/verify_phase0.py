#!/usr/bin/env python3
"""Phase 0 check: Python deps, optional Neo4j Bolt connectivity via .env."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.chdir(ROOT)
    print(f"Working directory: {ROOT}")

    # Imports
    try:
        import pandas  # noqa: F401
        import neo4j  # noqa: F401
        import dotenv  # noqa: F401
        import matplotlib  # noqa: F401
    except ImportError as e:
        print("FAIL: missing dependency — run: .venv/bin/pip install -r requirements.txt")
        print(e)
        return 1
    print("OK: pandas, neo4j, python-dotenv, matplotlib import")

    # Optional: pyxlsb (Phase 1 extraction)
    try:
        import pyxlsb  # noqa: F401
    except ImportError:
        print("NOTE: pyxlsb not installed yet (add in Phase 1 for .xlsb extraction)")
    else:
        print("OK: pyxlsb import")

    env_path = ROOT / ".env"
    if not env_path.is_file():
        print("NOTE: no .env — copy .env.example to .env or export NEO4J_* variables")
        return 0

    from dotenv import load_dotenv

    load_dotenv(env_path)
    uri = os.environ.get("NEO4J_URI", "").strip()
    user = os.environ.get("NEO4J_USER", "").strip()
    password = os.environ.get("NEO4J_PASSWORD", "")

    if not uri or not user:
        print("NOTE: NEO4J_URI / NEO4J_USER not set in .env — skipping Bolt test")
        return 0

    from neo4j import GraphDatabase, basic_auth

    auth = basic_auth(user, password)
    try:
        driver = GraphDatabase.driver(uri, auth=auth)
        driver.verify_connectivity()
        driver.close()
    except Exception as e:
        print(f"FAIL: Neo4j connectivity ({uri}): {e}")
        return 1

    print(f"OK: Neo4j Bolt connectivity ({uri})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
