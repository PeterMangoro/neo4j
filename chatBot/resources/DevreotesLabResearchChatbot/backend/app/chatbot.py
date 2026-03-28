import json
import os
import sys
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .paths import HGNC_LOOKUP_PATH, load_project_dotenv
from .retrieval import (
    graph_search_author_publication_stats,
    graph_search_by_author,
    graph_search_by_gene,
    graph_search_research_themes,
    vector_search,
)
from .router import (
    classify_query,
    extract_author_from_question,
    extract_gene_from_question,
    is_author_stats_query,
)
from .agent_tools import run_evidence_agent


load_project_dotenv()

with HGNC_LOOKUP_PATH.open("r", encoding="utf-8") as f:
    hgnc_lookup = json.load(f)

llm = ChatOpenAI(model="gpt-4o", temperature=0)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.35"))
MAX_CONTEXT_CHARS_PER_CHUNK = int(os.getenv("MAX_CONTEXT_CHARS_PER_CHUNK", "900"))
MAX_CONTEXT_CHUNKS = int(os.getenv("MAX_CONTEXT_CHUNKS", "8"))

SYSTEM_PROMPT = (
    "You are a research assistant for Prof. Peter Devreotes' lab at Johns Hopkins University. "
    "You answer questions based ONLY on the provided research papers from the lab corpus. "
    "Do not use outside knowledge. If the answer is not in the provided context, say so clearly. "
    "Be concise and scientifically precise. "
    "Every substantive claim must cite one or more numbered passages in square brackets like [1] or [2]."
)


def _query_type_label(effective: str) -> str:
    """Human-readable route for UI/debug (internal keys stay stable)."""
    return {
        "themes": "Gene mention frequency (corpus)",
        "author_stats": "Author publication counts (corpus)",
        "gene": "Gene-focused retrieval",
        "author": "Author-filtered retrieval",
        "semantic": "Semantic (vector) retrieval",
        "agent": "Agent retrieval (tools)",
    }.get(effective, effective)


def _result_score(row) -> float:
    score = row.get("score")
    if score is None:
        return 0.0
    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


def build_context(results, result_type: str = "semantic", max_chunks: int = MAX_CONTEXT_CHUNKS) -> str:
    if not results:
        return "No relevant papers found in the corpus."

    context_parts = []
    if result_type == "themes":
        context_parts.append(
            "Gene mention frequency across the corpus (papers with a :MENTIONS edge to each gene; "
            "this is a bibliometric summary, not a qualitative thematic analysis):"
        )
        for idx, item in enumerate(results[:15], 1):
            g = item.get("gene", "Unknown")
            n = item.get("paper_count", 0)
            context_parts.append(f"[{idx}] Gene {g}: mentioned in {n} paper(s)")
        return "\n".join(context_parts)

    if result_type == "author_stats":
        context_parts.append(
            "Authors linked to papers by :AUTHORED (count = distinct papers in this corpus):"
        )
        for idx, item in enumerate(results[:15], 1):
            a = item.get("author") or item.get("author_key") or "Unknown"
            n = item.get("paper_count", 0)
            context_parts.append(f"[{idx}] {a}: {n} paper(s)")
        return "\n".join(context_parts)

    for idx, item in enumerate(results[:max_chunks], 1):
        title = item.get("title", "Unknown")
        chunk_id = item.get("chunk_id", "chunk_unknown")
        score = _result_score(item)
        source_file = item.get("source_file")
        text = (item.get("text") or "")[:MAX_CONTEXT_CHARS_PER_CHUNK]
        header = f"[{idx}] title={title} chunk_id={chunk_id} score={score:.4f}"
        if source_file:
            header += f" file={source_file}"
        context_parts.append(f"{header}\n{text}")
    return "\n\n".join(context_parts)


def _build_sources_and_preview(results, result_kind: str):
    """
    result_kind matches the retrieval path (usually `effective_query_type`):
    themes | author_stats | gene | author | semantic.
    """
    sources = []
    preview = []

    if result_kind == "author_stats":
        for item in results[:15]:
            a = item.get("author") or item.get("author_key") or "Unknown"
            n = item.get("paper_count", 0)
            sources.append(f"{a} ({n} papers)")
            preview.append(
                {
                    "author": a,
                    "author_key": item.get("author_key"),
                    "paper_count": n,
                    "stat_type": "author_publication_count",
                    "route": "author_stats",
                }
            )
        return sources, preview

    if result_kind == "themes":
        for item in results[:10]:
            gene = item.get("gene", "Unknown")
            count = item.get("paper_count", 0)
            sources.append(f"{gene} ({count} papers)")
            preview.append(
                {
                    "gene": gene,
                    "paper_count": count,
                    "stat_type": "gene_mention_frequency",
                    "route": "themes",
                }
            )
        return sources, preview

    seen_sources = set()
    for item in results[:MAX_CONTEXT_CHUNKS]:
        title = (item.get("title") or "Unknown").strip()
        chunk_id = item.get("chunk_id")
        source_file = item.get("source_file")
        source_key = f"{title} [{chunk_id}]" if chunk_id else title
        if source_file:
            source_key = f"{source_key} ({source_file})"
        if source_key and source_key not in seen_sources:
            sources.append(source_key)
            seen_sources.add(source_key)
        row_route = item.get("route") or result_kind
        preview.append(
            {
                "paper_id": item.get("paper_id") or item.get("id"),
                "title": title,
                "source_file": source_file,
                "chunk_id": chunk_id,
                "score": item.get("score"),
                "gene": item.get("gene"),
                "author": item.get("author"),
                "route": row_route,
                "retrieval_path": result_kind,
            }
        )
    return sources, preview


def _retrieve_or_abstain(question: str, query_type: str, routed_key: str | None):
    if query_type == "themes":
        results = graph_search_research_themes()
        if not results:
            return {
                "abstained": True,
                "abstain_reason": "no_theme_data",
                "results": [],
            }
        return {
            "abstained": False,
            "abstain_reason": None,
            "results": results,
        }

    if query_type == "author_stats":
        results = graph_search_author_publication_stats()
        if not results:
            return {
                "abstained": True,
                "abstain_reason": "no_author_stats",
                "results": [],
            }
        return {
            "abstained": False,
            "abstain_reason": None,
            "results": results,
        }

    if query_type == "gene":
        if routed_key:
            results = graph_search_by_gene(routed_key, question=question, top_k=RAG_TOP_K)
        else:
            results = vector_search(question, top_k=RAG_TOP_K)
    elif query_type == "author":
        results = graph_search_by_author(routed_key or "Devreotes", question=question, top_k=RAG_TOP_K)
    else:
        results = vector_search(question, top_k=RAG_TOP_K)

    if not results:
        return {
            "abstained": True,
            "abstain_reason": "no_chunks",
            "results": [],
        }

    best_score = max(_result_score(r) for r in results)
    if best_score < RAG_MIN_SCORE:
        return {
            "abstained": True,
            "abstain_reason": "below_min_score",
            "results": results,
            "best_score": best_score,
        }

    return {
        "abstained": False,
        "abstain_reason": None,
        "results": sorted(results, key=_result_score, reverse=True),
    }


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _rag_mode() -> str:
    return os.getenv("DEVREOTES_RAG_MODE", "router").strip().lower()


def _merge_raw_chunks(rows: list) -> list:
    """Deduplicate by chunk_id keeping the row with the best score."""
    by_id: dict = {}
    for r in rows:
        cid = r.get("chunk_id")
        if not cid:
            continue
        prev = by_id.get(cid)
        if prev is None or _result_score(r) > _result_score(prev):
            by_id[cid] = dict(r)
    return sorted(by_id.values(), key=_result_score, reverse=True)


def _themes_context_with_s_labels(results: list, max_n: int = 15) -> str:
    lines = [
        "Gene mention frequency across the corpus (bibliometric summary):",
    ]
    for idx, item in enumerate(results[:max_n], 1):
        g = item.get("gene", "Unknown")
        n = item.get("paper_count", 0)
        lines.append(f"[S{idx}] Gene {g}: mentioned in {n} paper(s)")
    return "\n".join(lines)


def _prepare_generation_router(question: str):
    """
    Rule-based routing + retrieval + prompt construction.
    Returns either {abstain: True, result: dict} or {abstain: False, messages, results, effective_query_type, routed_key}.
    """
    query_type = classify_query(question)
    if query_type == "author" and is_author_stats_query(question):
        query_type = "author_stats"
        _log("[Router] Promoted author → author_stats (aggregate wording)")
    _log(f"[Router] Query type: {query_type}")

    routed_key = None
    effective_query_type = query_type
    if query_type == "gene":
        gene = extract_gene_from_question(question, hgnc_lookup)
        if gene:
            routed_key = gene
            _log(f"[Graph] Gene route for '{gene}'")
        else:
            routed_key = "semantic_fallback"
            effective_query_type = "semantic"
            _log("[Graph] Gene route fell back to semantic retrieval")
    elif query_type == "author":
        author = extract_author_from_question(question) or "Devreotes"
        routed_key = author
        _log(f"[Graph] Author route for '{author}'")
    elif query_type == "author_stats":
        routed_key = "author_stats"
        _log("[Graph] Author publication stats route")
    elif query_type == "themes":
        routed_key = "themes"
        _log("[Graph] Themes route")
    else:
        routed_key = "semantic"
        _log("[Vector] Semantic route")

    retrieved = _retrieve_or_abstain(
        question,
        effective_query_type,
        routed_key if query_type not in ("themes", "author_stats") else None,
    )
    results = retrieved["results"]

    if retrieved["abstained"]:
        reason = retrieved.get("abstain_reason")
        best_score = retrieved.get("best_score")
        if reason == "below_min_score":
            answer = (
                f"The best retrieved chunk score ({best_score:.4f}) is below the configured minimum "
                f"({RAG_MIN_SCORE:.4f}), so I cannot answer confidently from this corpus alone."
            )
        elif reason == "no_theme_data":
            answer = "No gene mention statistics were found in the corpus yet."
        elif reason == "no_author_stats":
            answer = (
                "No authors with multiple papers were found in the graph yet "
                "(or the minimum paper threshold filtered everyone out)."
            )
        else:
            answer = "No relevant passages were retrieved from the corpus."
        sources, preview = _build_sources_and_preview(results, effective_query_type)
        return {
            "abstain": True,
            "result": {
                "answer": answer,
                "query_type": effective_query_type,
                "query_type_label": _query_type_label(effective_query_type),
                "routed_key": routed_key,
                "results_count": len(results),
                "sources": sources,
                "retrieval_preview": preview,
                "abstained": True,
                "abstain_reason": reason,
            },
        }

    context = build_context(results, effective_query_type)

    if effective_query_type == "themes":
        user_block = (
            "Numbered gene mention statistics derived from the graph:\n"
            "---\n"
            f"{context}\n"
            "---\n\n"
            f"Question: {question}\n\n"
            "Answer only using the statistics above. Cite each statistic you rely on as [n]. "
            "Do not invent qualitative research themes that are not supported by these counts."
        )
    elif effective_query_type == "author_stats":
        user_block = (
            "Numbered author–publication counts derived from the graph (:Author)-[:AUTHORED]->(:Paper):\n"
            "---\n"
            f"{context}\n"
            "---\n\n"
            f"Question: {question}\n\n"
            "Answer only using the rows above. Cite each row you use as [n]. "
            "If the question asks who appears on multiple papers, list authors with paper_count ≥ 2."
        )
    else:
        user_block = (
            "Numbered passages from Prof. Devreotes' papers:\n"
            "---\n"
            f"{context}\n"
            "---\n\n"
            f"Question: {question}\n\n"
            "Answer only from the passages above. Cite supporting passages as [n]."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_block),
    ]
    return {
        "abstain": False,
        "messages": messages,
        "results": results,
        "effective_query_type": effective_query_type,
        "routed_key": routed_key,
    }


def _prepare_generation_agent(question: str):
    _log("[Agent] DEVREOTES_RAG_MODE=agent")
    ev = run_evidence_agent(llm, question)
    tool_calls_log = ev["tool_calls_log"]
    extras = {"tool_calls_log": tool_calls_log}

    if not ev["used_tools"]:
        _log("[Agent] No tool calls; falling back to router")
        return _prepare_generation_router(question)

    themes = ev["themes"] if ev["themes"] else None
    author_stats = ev.get("author_stats") if ev.get("author_stats") else None
    merged = _merge_raw_chunks(ev["raw_chunks"])
    routed_key = "agent"

    def abstain_payload(answer: str, reason: str, results: list, qtype: str):
        kind = (
            "themes"
            if qtype == "themes"
            else "author_stats"
            if qtype == "author_stats"
            else "semantic"
        )
        sources, preview = _build_sources_and_preview(results, kind)
        return {
            "abstain": True,
            "result": {
                "answer": answer,
                "query_type": qtype,
                "query_type_label": _query_type_label(qtype),
                "routed_key": routed_key,
                "results_count": len(results),
                "sources": sources,
                "retrieval_preview": preview,
                "abstained": True,
                "abstain_reason": reason,
                **extras,
            },
        }

    if not merged and not themes and not author_stats:
        return abstain_payload(
            "No relevant passages were retrieved from the corpus.",
            "no_chunks",
            [],
            "agent",
        )

    if not merged and themes and not author_stats:
        results = themes
        if not results:
            return abstain_payload(
                "No gene mention statistics were found in the corpus yet.",
                "no_theme_data",
                [],
                "themes",
            )
        context = build_context(results, "themes")
        user_block = (
            "Numbered gene mention statistics derived from the graph:\n"
            "---\n"
            f"{context}\n"
            "---\n\n"
            f"Question: {question}\n\n"
            "Answer only using the statistics above. Cite each statistic you rely on as [n]. "
            "Do not invent qualitative research themes that are not supported by these counts."
        )
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_block)]
        return {
            "abstain": False,
            "messages": messages,
            "results": results,
            "effective_query_type": "themes",
            "routed_key": routed_key,
            "tool_calls_log": tool_calls_log,
        }

    if not merged and author_stats and not themes:
        results = author_stats
        if not results:
            return abstain_payload(
                "No authors with multiple papers were found in the graph yet.",
                "no_author_stats",
                [],
                "author_stats",
            )
        context = build_context(results, "author_stats")
        user_block = (
            "Numbered author–publication counts derived from the graph (:Author)-[:AUTHORED]->(:Paper):\n"
            "---\n"
            f"{context}\n"
            "---\n\n"
            f"Question: {question}\n\n"
            "Answer only using the rows above. Cite each row as [n]."
        )
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_block)]
        return {
            "abstain": False,
            "messages": messages,
            "results": results,
            "effective_query_type": "author_stats",
            "routed_key": routed_key,
            "tool_calls_log": tool_calls_log,
        }

    if not merged and themes and author_stats:
        gctx = build_context(themes, "themes")
        actx = build_context(author_stats, "author_stats")
        user_block = (
            "Two graph statistics sections:\n"
            "---\n"
            f"{gctx}\n\n"
            f"{actx}\n"
            "---\n\n"
            f"Question: {question}\n\n"
            "Answer using only the sections above. Cite gene lines and author lines as [n] by their bracket numbers."
        )
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_block)]
        return {
            "abstain": False,
            "messages": messages,
            "results": (themes or []) + (author_stats or []),
            "effective_query_type": "agent",
            "routed_key": routed_key,
            "tool_calls_log": tool_calls_log,
        }

    best_score = max(_result_score(r) for r in merged)
    if best_score < RAG_MIN_SCORE:
        sources, preview = _build_sources_and_preview(merged, "semantic")
        return {
            "abstain": True,
            "result": {
                "answer": (
                    f"The best retrieved chunk score ({best_score:.4f}) is below the configured minimum "
                    f"({RAG_MIN_SCORE:.4f}), so I cannot answer confidently from this corpus alone."
                ),
                "query_type": "agent",
                "query_type_label": _query_type_label("agent"),
                "routed_key": routed_key,
                "results_count": len(merged),
                "sources": sources,
                "retrieval_preview": preview,
                "abstained": True,
                "abstain_reason": "below_min_score",
                **extras,
            },
        }

    results = sorted(merged, key=_result_score, reverse=True)

    if themes or author_stats:
        extra_sections: list[str] = []
        if themes:
            extra_sections.append(
                "=== Gene mention statistics ===\n" + _themes_context_with_s_labels(themes)
            )
        if author_stats:
            extra_sections.append(
                "=== Author publication counts ===\n" + build_context(author_stats, "author_stats")
            )
        chunk_ctx = build_context(results, "semantic")
        user_block = (
            "You may use multiple evidence sections below.\n"
            "- Cite gene statistics as [S1], [S2], ... when present.\n"
            "- Cite author statistics by their [n] line numbers when present.\n"
            "- Cite paper passages as [1], [2], ... in the passages section.\n\n"
            + "\n\n".join(extra_sections)
            + "\n\n=== Numbered passages from papers ===\n---\n"
            f"{chunk_ctx}\n---\n\n"
            f"Question: {question}\n\n"
            "Answer only from the sections above. Do not use outside knowledge."
        )
        effective_query_type = "agent"
    else:
        context = build_context(results, "semantic")
        user_block = (
            "Numbered passages from Prof. Devreotes' papers:\n---\n"
            f"{context}\n---\n\n"
            f"Question: {question}\n\n"
            "Answer only from the passages above. Cite supporting passages as [n]."
        )
        effective_query_type = "agent"

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_block)]
    return {
        "abstain": False,
        "messages": messages,
        "results": results,
        "effective_query_type": effective_query_type,
        "routed_key": routed_key,
        "tool_calls_log": tool_calls_log,
    }


def _prepare_generation(question: str):
    if _rag_mode() == "agent":
        return _prepare_generation_agent(question)
    return _prepare_generation_router(question)


def _stream_chunk_text(chunk) -> str:
    c = getattr(chunk, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(str(p.get("text", "")))
            elif isinstance(p, str):
                parts.append(p)
        return "".join(parts)
    return ""


def iter_answer_ndjson(question: str):
    """Yield NDJSON lines (stdout only) for the streaming bridge: delta + finish."""
    state = _prepare_generation(question)
    if state["abstain"]:
        res = state["result"]
        yield json.dumps({"type": "delta", "text": res["answer"]}) + "\n"
        yield json.dumps({"type": "finish", "result": res}) + "\n"
        return

    messages = state["messages"]
    results = state["results"]
    effective_query_type = state["effective_query_type"]
    routed_key = state["routed_key"]

    accumulated: list[str] = []
    for chunk in llm.stream(messages):
        piece = _stream_chunk_text(chunk)
        if piece:
            accumulated.append(piece)
            yield json.dumps({"type": "delta", "text": piece}) + "\n"

    answer = "".join(accumulated)
    preview_kind = "semantic" if effective_query_type == "agent" else effective_query_type
    sources, preview = _build_sources_and_preview(results, preview_kind)
    result = {
        "answer": answer,
        "query_type": effective_query_type,
        "query_type_label": _query_type_label(effective_query_type),
        "routed_key": routed_key,
        "results_count": len(results),
        "sources": sources,
        "retrieval_preview": preview,
        "abstained": False,
        "abstain_reason": None,
    }
    if state.get("tool_calls_log") is not None:
        result["tool_calls_log"] = state["tool_calls_log"]
    yield json.dumps({"type": "finish", "result": result}) + "\n"


def answer_question_with_metadata(question: str, chat_history=None) -> dict:
    state = _prepare_generation(question)
    if state["abstain"]:
        return state["result"]

    response = llm.invoke(state["messages"])
    answer = response.content
    eqt = state["effective_query_type"]
    preview_kind = "semantic" if eqt == "agent" else eqt
    sources, preview = _build_sources_and_preview(state["results"], preview_kind)
    out = {
        "answer": answer,
        "query_type": eqt,
        "query_type_label": _query_type_label(eqt),
        "routed_key": state["routed_key"],
        "results_count": len(state["results"]),
        "sources": sources,
        "retrieval_preview": preview,
        "abstained": False,
        "abstain_reason": None,
    }
    if state.get("tool_calls_log") is not None:
        out["tool_calls_log"] = state["tool_calls_log"]
    return out


def answer_question(question: str, chat_history=None) -> str:
    result = answer_question_with_metadata(question, chat_history=chat_history)
    return result["answer"]


def run_chatbot():
    print("=" * 60)
    print("GraphRAG Chatbot - Prof. Devreotes Lab")
    print("Type 'quit' to exit")
    print("=" * 60)

    while True:
        question = input("\nYou: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
        if not question:
            continue

        print("\nSearching corpus...")
        answer = answer_question(question)
        print(f"\nAssistant: {answer}")


if __name__ == "__main__":
    run_chatbot()
