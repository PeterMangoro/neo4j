"""
LangChain tools wrapping Neo4j-backed retrieval for multi-step evidence gathering.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from .paths import load_project_dotenv
from .retrieval import (
    graph_corpus_meta,
    graph_search_author_directory,
    graph_search_author_publication_stats,
    graph_search_by_author,
    graph_search_by_gene,
    graph_search_research_themes,
    vector_search,
)

load_project_dotenv()


def _rag_top_k() -> int:
    return int(os.getenv("RAG_TOP_K", "8"))


def _max_context_chars() -> int:
    return int(os.getenv("MAX_CONTEXT_CHARS_PER_CHUNK", "900"))


def _slim_chunk_rows(rows: list, route: str) -> list[dict[str, Any]]:
    cap = _max_context_chars()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "paper_id": r.get("paper_id") or r.get("id"),
                "title": r.get("title"),
                "chunk_id": r.get("chunk_id"),
                "text": (r.get("text") or "")[:cap],
                "score": r.get("score"),
                "gene": r.get("gene"),
                "author": r.get("author"),
                "source_file": r.get("source_file"),
                "route": route,
            }
        )
    return out


def _pack_chunks(route: str, rows: list) -> str:
    return json.dumps(
        {"kind": "chunks", "route": route, "items": _slim_chunk_rows(rows, route)},
        ensure_ascii=True,
    )


@tool
def semantic_search(query: str) -> str:
    """Vector similarity search over paper chunks. Use for broad or conceptual questions when no specific HGNC gene symbol or author filter is required. Pass a focused search phrase."""
    q = (query or "").strip()
    if not q:
        return json.dumps({"kind": "chunks", "route": "semantic", "items": []}, ensure_ascii=True)
    rows = vector_search(q, top_k=_rag_top_k())
    return _pack_chunks("semantic", rows)


@tool
def gene_literature_search(gene_symbol: str, question_context: str = "") -> str:
    """Retrieve chunks from papers that mention a human gene by official HGNC symbol (e.g. PTEN, PIK3CB). Optionally pass question_context to steer ranking. Returns empty items if the symbol is not found."""
    sym = (gene_symbol or "").strip().upper()
    if not sym:
        return json.dumps({"kind": "chunks", "route": "gene", "items": []}, ensure_ascii=True)
    ctx = (question_context or "").strip()
    rows = graph_search_by_gene(sym, question=ctx or None, top_k=_rag_top_k())
    return _pack_chunks("gene", rows)


@tool
def author_literature_search(author_name: str, question_context: str = "") -> str:
    """Retrieve chunks from papers associated with an author name (matched loosely). Default lab context: use 'Devreotes' if unsure. Pass question_context for semantic reranking within that author scope."""
    name = (author_name or "").strip() or "Devreotes"
    ctx = (question_context or "").strip()
    rows = graph_search_by_author(name, question=ctx or None, top_k=max(_rag_top_k(), 12))
    return _pack_chunks("author", rows)


@tool
def corpus_gene_frequencies() -> str:
    """Corpus-wide gene mention counts (papers per gene via the graph). Use for questions about most-mentioned genes, prevalence, or bibliometric summaries—not for passage-level quotes."""
    rows, meta = graph_search_research_themes()
    return json.dumps(
        {"kind": "themes", "route": "themes", "items": rows or [], "meta": meta},
        ensure_ascii=True,
    )


@tool
def corpus_author_publication_stats() -> str:
    """Authors with multiple papers in this corpus (:AUTHORED counts). Use for which authors appear on more than one paper, collaborators across publications, or publication counts per author—not 'papers by a specific name'."""
    rows = graph_search_author_publication_stats()
    return json.dumps({"kind": "author_stats", "route": "author_stats", "items": rows or []}, ensure_ascii=True)


@tool
def corpus_all_authors_directory() -> str:
    """Full author bibliography: every :Author with :AUTHORED links and their distinct paper counts (min 1 paper), sorted by count. Use for 'list all authors', 'complete author list', or 'every author in the corpus'—not for 'papers by Dr. X'."""
    rows, meta = graph_search_author_directory()
    return json.dumps(
        {"kind": "author_directory", "route": "author_directory", "items": rows or [], "meta": meta},
        ensure_ascii=True,
    )


@tool
def corpus_graph_inventory() -> str:
    """Exact counts of Paper, Chunk, Gene, Author, Entity, and Claim nodes in the Neo4j graph. Use when the user asks how many papers/chunks/genes/authors are in the corpus, database, or graph—not for 'most mentioned' genes (use corpus_gene_frequencies) or passage search."""
    meta = graph_corpus_meta()
    return json.dumps(
        {"kind": "corpus_meta", "route": "corpus_meta", "items": [meta]},
        ensure_ascii=True,
    )


DEVREOTES_RETRIEVAL_TOOLS = [
    semantic_search,
    gene_literature_search,
    author_literature_search,
    corpus_gene_frequencies,
    corpus_author_publication_stats,
    corpus_all_authors_directory,
    corpus_graph_inventory,
]

AGENT_SYSTEM_PROMPT = """You are a retrieval planner for a biomedical literature corpus (Prof. Devreotes lab papers).

Your job is to call one or more tools to gather evidence for the user's question. Rules:
- Prefer gene_literature_search when the user names a specific human gene symbol (HGNC).
- Prefer author_literature_search when the question is about passages from papers by a **specific** author name.
- Use corpus_author_publication_stats for questions about **which authors** show up on **multiple papers**, collaborators across the corpus, or author–publication counts (not a single named author).
- Use corpus_all_authors_directory for a **complete list** of authors with paper counts (every author in the graph), or when the user asks for **all** / **every** author.
- Use corpus_gene_frequencies for questions about which genes are most mentioned across the corpus, counts, or prevalence.
- Use corpus_graph_inventory for **total** papers, chunks, genes, or authors **in the graph/corpus** (exact inventory counts)—not semantic search over text.
- For **combined** questions (e.g. full author list **and** how many papers in the corpus), call **corpus_graph_inventory** together with **corpus_all_authors_directory** or **corpus_author_publication_stats** as appropriate.
- Use semantic_search for general conceptual questions or when other tools are not a clear fit.
- You may call multiple tools if the question combines scopes (e.g. gene + author).
- Do not write a final answer to the user; only call tools. After you have enough evidence, stop calling tools (respond with no tool calls)."""


def _parse_tool_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return {"kind": "unknown", "items": [], "raw": raw[:500]}


def _accumulate_payload(
    chunk_acc: list[dict[str, Any]],
    themes_holder: list[Any],
    author_stats_holder: list[Any],
    author_directory_holder: list[Any],
    author_directory_meta_holder: dict[str, Any],
    corpus_meta_holder: list[Any],
    themes_meta_holder: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    kind = payload.get("kind")
    if kind == "chunks":
        items = payload.get("items") or []
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    chunk_acc.append(it)
    elif kind == "themes":
        items = payload.get("items") or []
        if isinstance(items, list):
            themes_holder.clear()
            themes_holder.extend(items)
        m = payload.get("meta")
        if isinstance(m, dict):
            themes_meta_holder.clear()
            themes_meta_holder.update(m)
    elif kind == "author_stats":
        items = payload.get("items") or []
        if isinstance(items, list):
            author_stats_holder.clear()
            author_stats_holder.extend(items)
    elif kind == "author_directory":
        items = payload.get("items") or []
        if isinstance(items, list):
            author_directory_holder.clear()
            author_directory_holder.extend(items)
        m = payload.get("meta")
        if isinstance(m, dict):
            author_directory_meta_holder.clear()
            author_directory_meta_holder.update(m)
    elif kind == "corpus_meta":
        items = payload.get("items") or []
        if isinstance(items, list) and items:
            corpus_meta_holder.clear()
            corpus_meta_holder.extend(items)


def run_evidence_agent(llm, question: str) -> dict[str, Any]:
    """
    Run tool-calling loop; return merged raw chunk dicts, optional themes list, and log.
    If the model issues no tool calls on the first turn, used_tools is False (caller should fallback).
    """
    max_steps = max(1, int(os.getenv("DEVREOTES_AGENT_MAX_STEPS", "6")))
    bound = llm.bind_tools(DEVREOTES_RETRIEVAL_TOOLS)
    messages: list = [
        SystemMessage(content=AGENT_SYSTEM_PROMPT),
        HumanMessage(content=question.strip()),
    ]
    tool_calls_log: list[dict[str, Any]] = []
    chunk_acc: list[dict[str, Any]] = []
    themes_holder: list[Any] = []
    author_stats_holder: list[Any] = []
    author_directory_holder: list[Any] = []
    author_directory_meta_holder: dict[str, Any] = {}
    corpus_meta_holder: list[Any] = []
    themes_meta_holder: dict[str, Any] = {}
    tool_by_name = {t.name: t for t in DEVREOTES_RETRIEVAL_TOOLS}
    used_tools = False

    for _ in range(max_steps):
        ai_msg: AIMessage = bound.invoke(messages)
        calls = getattr(ai_msg, "tool_calls", None) or []
        if not calls:
            messages.append(ai_msg)
            break
        used_tools = True
        messages.append(ai_msg)
        for tc in calls:
            name = tc.get("name")
            tid = tc.get("id") or tc.get("tool_call_id") or str(uuid.uuid4())
            args = tc.get("args")
            if not isinstance(args, dict):
                args = {}
            tool_calls_log.append({"name": name, "args": dict(args)})
            tool_fn = tool_by_name.get(name)
            if tool_fn is None:
                out = json.dumps({"kind": "error", "message": f"unknown_tool:{name}"})
            else:
                try:
                    out = tool_fn.invoke(args)
                except Exception as exc:  # pragma: no cover - defensive
                    out = json.dumps({"kind": "error", "message": str(exc)})
            payload = _parse_tool_payload(out if isinstance(out, str) else str(out))
            _accumulate_payload(
                chunk_acc,
                themes_holder,
                author_stats_holder,
                author_directory_holder,
                author_directory_meta_holder,
                corpus_meta_holder,
                themes_meta_holder,
                payload,
            )
            messages.append(ToolMessage(content=out if isinstance(out, str) else str(out), tool_call_id=tid))

    return {
        "used_tools": used_tools,
        "raw_chunks": chunk_acc,
        "themes": list(themes_holder) if themes_holder else None,
        "author_stats": list(author_stats_holder) if author_stats_holder else None,
        "author_directory": list(author_directory_holder) if author_directory_holder else None,
        "author_directory_meta": dict(author_directory_meta_holder) if author_directory_meta_holder else None,
        "corpus_meta": list(corpus_meta_holder) if corpus_meta_holder else None,
        "themes_meta": dict(themes_meta_holder) if themes_meta_holder else None,
        "tool_calls_log": tool_calls_log,
    }
