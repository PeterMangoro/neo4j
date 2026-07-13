#!/usr/bin/env python3
"""Generate static JSON payloads for the /movie-recommender demo.

Pure-Python offline mirror of P_Mangoro_recommender_project.ipynb:
Jaccard taste similarity, FastRP-style embeddings + cosine kNN, Louvain
communities, and collaborative/hybrid recommendations for every user.

Writes into nuxt_neo4j/public/data/movie-recommender/:
    stats.json, queries.json, graph.json, graph_similarity.json,
    similarity.json, communities.json, recommendations.json, users.json

Usage:
    python export_recommender.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
from networkx.algorithms.community import louvain_communities, modularity

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent.parent / "nuxt_neo4j" / "public" / "data" / "movie-recommender"

MIN_RATING = 4
TOP_K_SIM = 5
TOP_K_REC = 10
EMBED_DIM = 64
RANDOM_SEED = 42
GENRE_WEIGHT = 0.5
DIRECTOR_WEIGHT = 1.0


def read_csv(name: str) -> list[dict[str, str]]:
    with open(HERE / name, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def round2(x: float) -> float:
    return round(float(x), 2)


def round3(x: float) -> float:
    return round(float(x), 3)


class RecommenderGraph:
    def __init__(self) -> None:
        self.users = read_csv("users.csv")
        self.movies = read_csv("movies.csv")
        self.ratings = read_csv("ratings.csv")

        self.user_by_id = {r["userId"]: r for r in self.users}
        self.movie_by_id = {r["movieId"]: r for r in self.movies}

        # Genre / Director enrichment (same as notebook MERGE from genre1/genre2/director)
        self.genres: list[str] = []
        self.directors: list[str] = []
        seen_g: set[str] = set()
        seen_d: set[str] = set()
        self.movie_genres: dict[str, list[str]] = {}
        self.movie_director: dict[str, str] = {}
        for m in self.movies:
            mid = m["movieId"]
            gs: list[str] = []
            for key in ("genre1", "genre2"):
                g = (m.get(key) or "").strip()
                if g:
                    gs.append(g)
                    if g not in seen_g:
                        seen_g.add(g)
                        self.genres.append(g)
            self.movie_genres[mid] = gs
            d = (m.get("director") or "").strip()
            self.movie_director[mid] = d
            if d and d not in seen_d:
                seen_d.add(d)
                self.directors.append(d)

        # Ratings lookup
        self.ratings_by_user: dict[str, list[tuple[str, float]]] = defaultdict(list)
        self.rating_lookup: dict[tuple[str, str], float] = {}
        for r in self.ratings:
            uid, mid = r["userId"], r["movieId"]
            rating = float(r["rating"])
            self.ratings_by_user[uid].append((mid, rating))
            self.rating_lookup[(uid, mid)] = rating

        # Movies rated (all) and liked (>= MIN_RATING) per user
        self.rated_movies: dict[str, set[str]] = {
            uid: {m for m, _ in pairs} for uid, pairs in self.ratings_by_user.items()
        }
        self.liked_movies: dict[str, set[str]] = {
            uid: {m for m, rt in pairs if rt >= MIN_RATING}
            for uid, pairs in self.ratings_by_user.items()
        }

        self.user_ids = [u["userId"] for u in self.users]
        self.movie_ids = [m["movieId"] for m in self.movies]

        # Filled by compute_* methods
        self.jaccard_edges: list[tuple[str, str, float]] = []
        self.knn_edges: list[tuple[str, str, float]] = []
        self.community_of: dict[str, int] = {}
        self.community_count = 0
        self.modularity = 0.0

    # --- ids ------------------------------------------------------------
    @staticmethod
    def user_node(uid: str) -> str:
        return f"User:{uid}"

    @staticmethod
    def movie_node(mid: str) -> str:
        return f"Movie:{mid}"

    @staticmethod
    def genre_node(name: str) -> str:
        return f"Genre:{name}"

    @staticmethod
    def director_node(name: str) -> str:
        return f"Director:{name}"

    # --- similarity -----------------------------------------------------
    def compute_jaccard(self) -> None:
        """GDS-style Jaccard on undirected RATED bipartite neighbors, topK=5."""
        sets = self.rated_movies
        scores: dict[str, list[tuple[str, float]]] = {uid: [] for uid in self.user_ids}
        for i, u1 in enumerate(self.user_ids):
            s1 = sets.get(u1, set())
            if not s1:
                continue
            for u2 in self.user_ids[i + 1 :]:
                s2 = sets.get(u2, set())
                if not s2:
                    continue
                inter = len(s1 & s2)
                if inter == 0:
                    continue
                union = len(s1 | s2)
                score = inter / union
                scores[u1].append((u2, score))
                scores[u2].append((u1, score))

        edges: list[tuple[str, str, float]] = []
        for uid, nbrs in scores.items():
            nbrs.sort(key=lambda x: (-x[1], x[0]))
            for other, score in nbrs[:TOP_K_SIM]:
                edges.append((uid, other, score))
        self.jaccard_edges = edges

    def compute_fastrp_knn(self) -> None:
        """Deterministic random-projection embeddings + cosine kNN (topK=5)."""
        rng = random.Random(RANDOM_SEED)
        movie_index = {mid: i for i, mid in enumerate(self.movie_ids)}
        n_movies = len(self.movie_ids)
        n_users = len(self.user_ids)

        # Sparse rating matrix rows
        rows: list[list[float]] = []
        for uid in self.user_ids:
            row = [0.0] * n_movies
            for mid, rt in self.ratings_by_user.get(uid, []):
                if mid in movie_index:
                    row[movie_index[mid]] = rt
            rows.append(row)

        # Random projection matrix (movies x dim), gaussian-ish via Box-Muller-lite
        proj = [[rng.gauss(0.0, 1.0) for _ in range(EMBED_DIM)] for _ in range(n_movies)]

        embeds: list[list[float]] = []
        for row in rows:
            emb = [0.0] * EMBED_DIM
            for j, val in enumerate(row):
                if val == 0.0:
                    continue
                for d in range(EMBED_DIM):
                    emb[d] += val * proj[j][d]
            # L2 normalize
            norm = math.sqrt(sum(x * x for x in emb)) or 1.0
            embeds.append([x / norm for x in emb])

        def cosine(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b))

        edges: list[tuple[str, str, float]] = []
        for i, uid in enumerate(self.user_ids):
            sims: list[tuple[str, float]] = []
            for j, other in enumerate(self.user_ids):
                if i == j:
                    continue
                sims.append((other, cosine(embeds[i], embeds[j])))
            sims.sort(key=lambda x: (-x[1], x[0]))
            for other, score in sims[:TOP_K_SIM]:
                edges.append((uid, other, max(0.0, float(score))))
        self.knn_edges = edges

    def compute_louvain(self) -> None:
        """Louvain on undirected Jaccard SIMILAR_TASTE graph."""
        G = nx.Graph()
        G.add_nodes_from(self.user_ids)
        for u1, u2, score in self.jaccard_edges:
            if G.has_edge(u1, u2):
                if score > G[u1][u2].get("weight", 0):
                    G[u1][u2]["weight"] = score
            else:
                G.add_edge(u1, u2, weight=score)

        # Drop isolated nodes from community detection input? Keep them — Louvain assigns alone.
        communities = louvain_communities(G, weight="weight", seed=RANDOM_SEED)
        # Sort communities by size desc then min member id for stability
        communities = sorted(communities, key=lambda c: (-len(c), min(c)))
        self.community_of = {}
        for cid, members in enumerate(communities):
            for uid in members:
                self.community_of[uid] = cid
        for uid in self.user_ids:
            self.community_of.setdefault(uid, len(communities))
        # Remap if any orphans got a new id beyond list
        max_id = max(self.community_of.values()) if self.community_of else 0
        self.community_count = max_id + 1
        # Modularity on the weighted graph
        partition = [set() for _ in range(self.community_count)]
        for uid, cid in self.community_of.items():
            partition[cid].add(uid)
        partition = [p for p in partition if p]
        self.community_count = len(partition)
        # Remap contiguous
        self.community_of = {}
        for cid, members in enumerate(partition):
            for uid in members:
                self.community_of[uid] = cid
        try:
            self.modularity = float(modularity(G, partition, weight="weight"))
        except Exception:
            self.modularity = 0.0

    # --- neighbors helper -----------------------------------------------
    def similar_users(self, uid: str, rel: str) -> list[str]:
        edges = self.jaccard_edges if rel == "SIMILAR_TASTE" else self.knn_edges
        out: set[str] = set()
        for a, b, _ in edges:
            if a == uid:
                out.add(b)
            elif b == uid:
                out.add(a)
        out.discard(uid)
        return sorted(out)

    def cf_recommendations(self, uid: str, rel: str, top_k: int = TOP_K_REC) -> list[dict]:
        similars = self.similar_users(uid, rel)
        already = self.rated_movies.get(uid, set())
        # movie -> (supporters set, ratings list)
        supporters: dict[str, set[str]] = defaultdict(set)
        ratings_acc: dict[str, list[float]] = defaultdict(list)
        for sim in similars:
            for mid, rt in self.ratings_by_user.get(sim, []):
                if rt < MIN_RATING or mid in already:
                    continue
                supporters[mid].add(sim)
                ratings_acc[mid].append(rt)
        rows: list[dict] = []
        for mid, supp in supporters.items():
            avg = sum(ratings_acc[mid]) / len(ratings_acc[mid])
            rows.append({
                "movieId": mid,
                "title": self.movie_by_id[mid]["title"],
                "supporters": len(supp),
                "avgRating": round2(avg),
            })
        rows.sort(key=lambda r: (-r["supporters"], -r["avgRating"], r["title"]))
        return rows[:top_k]

    def hybrid_recommendations(self, uid: str, rel: str, top_k: int = TOP_K_REC) -> list[dict]:
        similars = self.similar_users(uid, rel)
        already = self.rated_movies.get(uid, set())
        liked = self.liked_movies.get(uid, set())
        liked_genres: set[str] = set()
        liked_dirs: set[str] = set()
        for mid in liked:
            liked_genres.update(self.movie_genres.get(mid, []))
            d = self.movie_director.get(mid)
            if d:
                liked_dirs.add(d)

        supporters: dict[str, set[str]] = defaultdict(set)
        ratings_acc: dict[str, list[float]] = defaultdict(list)
        for sim in similars:
            for mid, rt in self.ratings_by_user.get(sim, []):
                if rt < MIN_RATING or mid in already:
                    continue
                supporters[mid].add(sim)
                ratings_acc[mid].append(rt)

        rows: list[dict] = []
        for mid, supp in supporters.items():
            avg = sum(ratings_acc[mid]) / len(ratings_acc[mid])
            g_overlap = len(set(self.movie_genres.get(mid, [])) & liked_genres)
            d = self.movie_director.get(mid)
            d_overlap = 1 if d and d in liked_dirs else 0
            final = (len(supp) + avg) + g_overlap * GENRE_WEIGHT + d_overlap * DIRECTOR_WEIGHT
            rows.append({
                "movieId": mid,
                "title": self.movie_by_id[mid]["title"],
                "supporters": len(supp),
                "avgRating": round2(avg),
                "genreOverlapCount": g_overlap,
                "directorOverlapCount": d_overlap,
                "finalScore": round3(final),
            })
        rows.sort(key=lambda r: (-r["finalScore"], -r["supporters"], -r["avgRating"], r["title"]))
        return rows[:top_k]

    # --- JSON builders --------------------------------------------------
    def build_stats(self) -> dict:
        n_users = len(self.users)
        n_movies = len(self.movies)
        n_genres = len(self.genres)
        n_dirs = len(self.directors)
        n_rated = len(self.ratings)
        n_in_genre = sum(len(gs) for gs in self.movie_genres.values())
        n_directed = sum(1 for d in self.movie_director.values() if d)
        return {
            "nodeCounts": [
                {"label": "User", "count": n_users},
                {"label": "Movie", "count": n_movies},
                {"label": "Genre", "count": n_genres},
                {"label": "Director", "count": n_dirs},
            ],
            "relCounts": [
                {"type": "RATED", "count": n_rated},
                {"type": "IN_GENRE", "count": n_in_genre},
                {"type": "DIRECTED_BY", "count": n_directed},
            ],
            "highlights": [
                {"label": "Users", "value": n_users},
                {"label": "Movies", "value": n_movies},
                {"label": "Ratings", "value": n_rated},
                {"label": "Taste communities", "value": self.community_count},
            ],
        }

    def build_graph(self) -> dict:
        nodes: list[dict] = []
        for u in self.users:
            uid = u["userId"]
            nodes.append({
                "id": self.user_node(uid),
                "caption": u["name"],
                "labels": ["User"],
                "community": self.community_of.get(uid, 0),
                "age": int(u["age"]),
                "occupation": u["occupation"],
            })
        for m in self.movies:
            nodes.append({
                "id": self.movie_node(m["movieId"]),
                "caption": m["title"],
                "labels": ["Movie"],
                "year": int(m["year"]) if m.get("year") else None,
            })
        for g in self.genres:
            nodes.append({"id": self.genre_node(g), "caption": g, "labels": ["Genre"]})
        for d in self.directors:
            nodes.append({"id": self.director_node(d), "caption": d, "labels": ["Director"]})

        rels: list[dict] = []
        for r in self.ratings:
            uid, mid = r["userId"], r["movieId"]
            rels.append({
                "id": f"RATED:{uid}:{mid}",
                "from": self.user_node(uid),
                "to": self.movie_node(mid),
                "type": "RATED",
                "rating": float(r["rating"]),
            })
        for mid, gs in self.movie_genres.items():
            for g in gs:
                rels.append({
                    "id": f"IN_GENRE:{mid}:{g}",
                    "from": self.movie_node(mid),
                    "to": self.genre_node(g),
                    "type": "IN_GENRE",
                })
        for mid, d in self.movie_director.items():
            if not d:
                continue
            rels.append({
                "id": f"DIRECTED_BY:{mid}:{d}",
                "from": self.movie_node(mid),
                "to": self.director_node(d),
                "type": "DIRECTED_BY",
            })
        return {"nodes": nodes, "relationships": rels}

    def build_graph_similarity(self) -> dict:
        nodes = []
        for u in self.users:
            uid = u["userId"]
            nodes.append({
                "id": self.user_node(uid),
                "caption": u["name"],
                "labels": ["User"],
                "community": self.community_of.get(uid, 0),
            })
        rels = []
        for u1, u2, score in self.jaccard_edges:
            rels.append({
                "id": f"SIMILAR_TASTE:{u1}:{u2}",
                "from": self.user_node(u1),
                "to": self.user_node(u2),
                "type": "SIMILAR_TASTE",
                "score": round3(score),
            })
        for u1, u2, score in self.knn_edges:
            rels.append({
                "id": f"KNN_SIMILAR:{u1}:{u2}",
                "from": self.user_node(u1),
                "to": self.user_node(u2),
                "type": "KNN_SIMILAR",
                "score": round3(score),
            })
        return {"nodes": nodes, "relationships": rels}

    def build_similarity(self) -> dict:
        jaccard = [
            {"user1": a, "user2": b, "score": round3(s)}
            for a, b, s in self.jaccard_edges
        ]
        knn = [
            {"user1": a, "user2": b, "score": round3(s)}
            for a, b, s in self.knn_edges
        ]
        # Pairwise comparison: undirected key of sorted user ids
        j_map: dict[tuple[str, str], float] = {}
        for a, b, s in self.jaccard_edges:
            key = tuple(sorted((a, b)))
            j_map[key] = max(j_map.get(key, 0.0), s)
        k_map: dict[tuple[str, str], float] = {}
        for a, b, s in self.knn_edges:
            key = tuple(sorted((a, b)))
            k_map[key] = max(k_map.get(key, 0.0), s)
        keys = sorted(set(j_map) | set(k_map))
        comparison = []
        for u1, u2 in keys:
            comparison.append({
                "user1": u1,
                "user2": u2,
                "jaccard": round3(j_map[u1, u2]) if (u1, u2) in j_map else None,
                "knn": round3(k_map[u1, u2]) if (u1, u2) in k_map else None,
            })
        return {"jaccard": jaccard, "knn": knn, "comparison": comparison}

    def build_communities(self) -> dict:
        members_by: dict[int, list[str]] = defaultdict(list)
        for uid, cid in self.community_of.items():
            members_by[cid].append(uid)

        communities = []
        for cid in sorted(members_by):
            members = sorted(members_by[cid])
            ages = [int(self.user_by_id[u]["age"]) for u in members]
            avg_age = round2(sum(ages) / len(ages)) if ages else 0

            # Top genres by avg rating across community ratings
            genre_ratings: dict[str, list[float]] = defaultdict(list)
            occ_counts: Counter[str] = Counter()
            for uid in members:
                occ_counts[self.user_by_id[uid]["occupation"]] += 1
                for mid, rt in self.ratings_by_user.get(uid, []):
                    for g in self.movie_genres.get(mid, []):
                        genre_ratings[g].append(rt)
            top_genres = sorted(
                (
                    {"name": g, "avgRating": round2(sum(vs) / len(vs)), "count": len(vs)}
                    for g, vs in genre_ratings.items()
                ),
                key=lambda x: (-x["avgRating"], -x["count"], x["name"]),
            )[:5]
            top_occupations = [
                {"name": name, "count": count}
                for name, count in occ_counts.most_common(5)
            ]
            communities.append({
                "id": cid,
                "size": len(members),
                "avgAge": avg_age,
                "topGenres": top_genres,
                "topOccupations": top_occupations,
                "members": [
                    {"id": uid, "name": self.user_by_id[uid]["name"]}
                    for uid in members
                ],
            })
        return {
            "communityCount": self.community_count,
            "modularity": round3(self.modularity),
            "communities": communities,
        }

    def build_recommendations(self) -> dict:
        out: dict = {}
        for uid in self.user_ids:
            out[uid] = {
                "collaborative": {
                    "similarTaste": self.cf_recommendations(uid, "SIMILAR_TASTE"),
                    "knn": self.cf_recommendations(uid, "KNN_SIMILAR"),
                },
                "hybrid": {
                    "similarTaste": self.hybrid_recommendations(uid, "SIMILAR_TASTE"),
                    "knn": self.hybrid_recommendations(uid, "KNN_SIMILAR"),
                },
            }
        return out

    def build_users(self) -> list[dict]:
        rows = []
        for u in self.users:
            uid = u["userId"]
            rows.append({
                "id": uid,
                "name": u["name"],
                "age": int(u["age"]),
                "occupation": u["occupation"],
                "community": self.community_of.get(uid, 0),
                "ratingsGiven": len(self.ratings_by_user.get(uid, [])),
            })
        return rows

    def build_queries(self) -> list[dict]:
        """EDA questions frozen as QueryResult[] (mirrors notebook explorations)."""
        queries: list[dict] = []

        # Graph size
        queries.append({
            "id": "eda-size",
            "title": "Graph size",
            "description": "Node and relationship counts after enrichment.",
            "cypher": "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count\n"
                      "ORDER BY count DESC\n"
                      "UNION ALL\n"
                      "MATCH ()-[r]->() RETURN type(r) AS label, count(*) AS count",
            "columns": ["label", "count"],
            "rows": [
                {"label": "User", "count": len(self.users)},
                {"label": "Movie", "count": len(self.movies)},
                {"label": "Genre", "count": len(self.genres)},
                {"label": "Director", "count": len(self.directors)},
                {"label": "RATED", "count": len(self.ratings)},
                {"label": "IN_GENRE", "count": sum(len(gs) for gs in self.movie_genres.values())},
                {"label": "DIRECTED_BY", "count": sum(1 for d in self.movie_director.values() if d)},
            ],
            "count": 7,
        })

        # Top active users
        activity = sorted(
            (
                {
                    "userId": uid,
                    "name": self.user_by_id[uid]["name"],
                    "ratingsGiven": len(pairs),
                    "avgRating": round2(sum(r for _, r in pairs) / len(pairs)),
                }
                for uid, pairs in self.ratings_by_user.items()
            ),
            key=lambda r: (-r["ratingsGiven"], -r["avgRating"], r["name"]),
        )[:5]
        queries.append({
            "id": "eda-top-users",
            "title": "Top 5 most active users",
            "description": "Users with the most ratings.",
            "cypher": "MATCH (u:User)-[r:RATED]->(:Movie)\n"
                      "RETURN u.userId AS userId, u.name AS name, count(r) AS ratingsGiven, "
                      "round(avg(r.rating),2) AS avgRating\n"
                      "ORDER BY ratingsGiven DESC LIMIT 5",
            "columns": ["userId", "name", "ratingsGiven", "avgRating"],
            "rows": activity,
            "count": len(activity),
        })

        # Top movies by numRatings
        movie_stats: dict[str, list[float]] = defaultdict(list)
        for (uid, mid), rt in self.rating_lookup.items():
            movie_stats[mid].append(rt)
        by_count = sorted(
            (
                {
                    "movieId": mid,
                    "title": self.movie_by_id[mid]["title"],
                    "numRatings": len(vs),
                    "avgUserRating": round2(sum(vs) / len(vs)),
                    "avgRating": float(self.movie_by_id[mid].get("avgRating") or 0),
                }
                for mid, vs in movie_stats.items()
            ),
            key=lambda r: (-r["numRatings"], -r["avgUserRating"], r["title"]),
        )[:10]
        queries.append({
            "id": "eda-top-movies",
            "title": "Top 10 movies by number of ratings",
            "description": "Most-rated movies with average user rating vs catalog avgRating.",
            "cypher": "MATCH (m:Movie)<-[r:RATED]-(:User)\n"
                      "RETURN m.movieId AS movieId, m.title AS title, count(r) AS numRatings, "
                      "round(avg(r.rating),2) AS avgUserRating, m.avgRating AS avgRating\n"
                      "ORDER BY numRatings DESC LIMIT 10",
            "columns": ["movieId", "title", "numRatings", "avgUserRating", "avgRating"],
            "rows": by_count,
            "count": len(by_count),
        })

        # Rating distribution
        dist = Counter(int(float(r["rating"])) for r in self.ratings)
        dist_rows = [{"rating": k, "count": dist[k]} for k in sorted(dist)]
        queries.append({
            "id": "eda-rating-dist",
            "title": "Rating distribution",
            "description": "How many ratings fall in each 1–5 bucket.",
            "cypher": "MATCH ()-[r:RATED]->() RETURN r.rating AS rating, count(*) AS count ORDER BY rating",
            "columns": ["rating", "count"],
            "rows": dist_rows,
            "count": len(dist_rows),
        })

        # Genre stats
        genre_movies: dict[str, set[str]] = defaultdict(set)
        genre_ratings: dict[str, list[float]] = defaultdict(list)
        for mid, gs in self.movie_genres.items():
            for g in gs:
                genre_movies[g].add(mid)
        for mid, vs in movie_stats.items():
            for g in self.movie_genres.get(mid, []):
                genre_ratings[g].extend(vs)
        genre_rows = sorted(
            (
                {
                    "genre": g,
                    "movieCount": len(genre_movies[g]),
                    "totalRatings": len(genre_ratings.get(g, [])),
                    "avgRating": round2(sum(genre_ratings[g]) / len(genre_ratings[g]))
                    if genre_ratings.get(g) else None,
                }
                for g in self.genres
            ),
            key=lambda r: (-r["movieCount"], r["genre"]),
        )
        queries.append({
            "id": "eda-genres",
            "title": "Genre statistics",
            "description": "Movies, ratings, and average rating per genre.",
            "cypher": "MATCH (m:Movie)-[:IN_GENRE]->(g:Genre)\n"
                      "OPTIONAL MATCH (m)<-[r:RATED]-()\n"
                      "RETURN g.name AS genre, count(DISTINCT m) AS movieCount, "
                      "count(r) AS totalRatings, round(avg(r.rating),2) AS avgRating\n"
                      "ORDER BY movieCount DESC",
            "columns": ["genre", "movieCount", "totalRatings", "avgRating"],
            "rows": genre_rows,
            "count": len(genre_rows),
        })

        # Director stats
        dir_movies: dict[str, list[str]] = defaultdict(list)
        for mid, d in self.movie_director.items():
            if d:
                dir_movies[d].append(mid)
        dir_rows = sorted(
            (
                {
                    "director": d,
                    "movieCount": len(mids),
                    "avgUserRating": round2(
                        sum(sum(movie_stats[m]) / len(movie_stats[m]) for m in mids if movie_stats.get(m))
                        / max(1, sum(1 for m in mids if movie_stats.get(m)))
                    ) if any(movie_stats.get(m) for m in mids) else None,
                }
                for d, mids in dir_movies.items()
            ),
            key=lambda r: (-r["movieCount"], r["director"]),
        )
        queries.append({
            "id": "eda-directors",
            "title": "Director statistics",
            "description": "Movies and average user rating per director.",
            "cypher": "MATCH (m:Movie)-[:DIRECTED_BY]->(d:Director)\n"
                      "OPTIONAL MATCH (m)<-[r:RATED]-()\n"
                      "RETURN d.name AS director, count(DISTINCT m) AS movieCount, "
                      "round(avg(r.rating),2) AS avgUserRating\n"
                      "ORDER BY movieCount DESC",
            "columns": ["director", "movieCount", "avgUserRating"],
            "rows": dir_rows,
            "count": len(dir_rows),
        })

        # Polarizing movies (stDev, >=3 ratings)
        def stdev(vs: list[float]) -> float:
            if len(vs) < 2:
                return 0.0
            mean = sum(vs) / len(vs)
            return math.sqrt(sum((x - mean) ** 2 for x in vs) / (len(vs) - 1))

        polar = sorted(
            (
                {
                    "movieId": mid,
                    "title": self.movie_by_id[mid]["title"],
                    "numRatings": len(vs),
                    "avgUserRating": round2(sum(vs) / len(vs)),
                    "stDev": round2(stdev(vs)),
                }
                for mid, vs in movie_stats.items()
                if len(vs) >= 3
            ),
            key=lambda r: (-r["stDev"], -r["numRatings"], r["title"]),
        )[:10]
        queries.append({
            "id": "eda-polarizing",
            "title": "Most polarizing movies",
            "description": "Highest rating standard deviation among movies with ≥3 ratings.",
            "cypher": "MATCH (m:Movie)<-[r:RATED]-(:User)\n"
                      "WITH m, count(r) AS numRatings, avg(r.rating) AS avgUserRating, stDev(r.rating) AS stDev\n"
                      "WHERE numRatings >= 3\n"
                      "RETURN m.movieId AS movieId, m.title AS title, numRatings, "
                      "round(avgUserRating,2) AS avgUserRating, round(stDev,2) AS stDev\n"
                      "ORDER BY stDev DESC LIMIT 10",
            "columns": ["movieId", "title", "numRatings", "avgUserRating", "stDev"],
            "rows": polar,
            "count": len(polar),
        })

        # High-overlap user pairs
        pairs = []
        for i, u1 in enumerate(self.user_ids):
            s1 = self.rated_movies.get(u1, set())
            for u2 in self.user_ids[i + 1 :]:
                s2 = self.rated_movies.get(u2, set())
                shared = s1 & s2
                if len(shared) < 2:
                    continue
                diffs = [
                    abs(self.rating_lookup[(u1, m)] - self.rating_lookup[(u2, m)])
                    for m in shared
                ]
                pairs.append({
                    "user1": u1,
                    "user1Name": self.user_by_id[u1]["name"],
                    "user2": u2,
                    "user2Name": self.user_by_id[u2]["name"],
                    "coRated": len(shared),
                    "avgAbsDiff": round2(sum(diffs) / len(diffs)),
                })
        pairs.sort(key=lambda r: (-r["coRated"], r["avgAbsDiff"], r["user1"]))
        pairs = pairs[:10]
        queries.append({
            "id": "eda-overlap",
            "title": "High-overlap user pairs",
            "description": "Users who co-rated the most movies, with average absolute rating difference.",
            "cypher": "MATCH (u1:User)-[:RATED]->(m:Movie)<-[:RATED]-(u2:User)\n"
                      "WHERE u1.userId < u2.userId\n"
                      "WITH u1, u2, count(m) AS coRated, "
                      "avg(abs((u1)-[:RATED]->(m)).rating - ((u2)-[:RATED]->(m)).rating) AS avgAbsDiff\n"
                      "RETURN u1.userId AS user1, u2.userId AS user2, coRated, round(avgAbsDiff,2) AS avgAbsDiff\n"
                      "ORDER BY coRated DESC LIMIT 10",
            "columns": ["user1", "user1Name", "user2", "user2Name", "coRated", "avgAbsDiff"],
            "rows": pairs,
            "count": len(pairs),
        })

        # Per-user genre preference (sample top users by activity — all users for small data)
        pref_rows = []
        for uid in self.user_ids:
            g_acc: dict[str, list[float]] = defaultdict(list)
            for mid, rt in self.ratings_by_user.get(uid, []):
                for g in self.movie_genres.get(mid, []):
                    g_acc[g].append(rt)
            if not g_acc:
                continue
            best = max(g_acc.items(), key=lambda kv: (sum(kv[1]) / len(kv[1]), len(kv[1])))
            pref_rows.append({
                "userId": uid,
                "name": self.user_by_id[uid]["name"],
                "topGenre": best[0],
                "avgRating": round2(sum(best[1]) / len(best[1])),
                "ratingsInGenre": len(best[1]),
            })
        pref_rows.sort(key=lambda r: r["name"])
        queries.append({
            "id": "eda-genre-prefs",
            "title": "Per-user genre preference",
            "description": "Each user's highest-average genre among genres they rated.",
            "cypher": "MATCH (u:User)-[r:RATED]->(m:Movie)-[:IN_GENRE]->(g:Genre)\n"
                      "WITH u, g, avg(r.rating) AS avgRating, count(*) AS ratingsInGenre\n"
                      "ORDER BY avgRating DESC\n"
                      "WITH u, collect({genre:g.name, avgRating:avgRating, ratingsInGenre:ratingsInGenre})[0] AS top\n"
                      "RETURN u.userId AS userId, u.name AS name, top.genre AS topGenre, "
                      "round(top.avgRating,2) AS avgRating, top.ratingsInGenre AS ratingsInGenre",
            "columns": ["userId", "name", "topGenre", "avgRating", "ratingsInGenre"],
            "rows": pref_rows,
            "count": len(pref_rows),
        })

        return queries


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Export movie-recommender static JSON payloads.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    g = RecommenderGraph()
    g.compute_jaccard()
    g.compute_fastrp_knn()
    g.compute_louvain()

    stats = g.build_stats()
    queries = g.build_queries()
    graph = g.build_graph()
    graph_sim = g.build_graph_similarity()
    similarity = g.build_similarity()
    communities = g.build_communities()
    recommendations = g.build_recommendations()
    users = g.build_users()

    # Integrity asserts
    n_nodes = len(graph["nodes"])
    n_rels = len(graph["relationships"])
    assert n_nodes == 80, f"expected 80 nodes, got {n_nodes}"
    assert n_rels == 176, f"expected 176 relationships, got {n_rels}"
    assert len(users) == 20, f"expected 20 users, got {len(users)}"
    assert set(recommendations.keys()) == set(g.user_ids), "recommendations missing users"
    assert stats["highlights"][3]["value"] == g.community_count

    write_json(out / "stats.json", stats)
    write_json(out / "queries.json", queries)
    write_json(out / "graph.json", graph)
    write_json(out / "graph_similarity.json", graph_sim)
    write_json(out / "similarity.json", similarity)
    write_json(out / "communities.json", communities)
    write_json(out / "recommendations.json", recommendations)
    write_json(out / "users.json", users)

    # Quick sparsity report
    empty_cf = sum(
        1 for uid, rec in recommendations.items()
        if not rec["collaborative"]["similarTaste"] and not rec["collaborative"]["knn"]
    )
    print(f"Wrote movie-recommender JSON to {out}")
    print(f"  nodes={n_nodes} rels={n_rels} communities={g.community_count} modularity={g.modularity:.3f}")
    print(f"  jaccard_edges={len(g.jaccard_edges)} knn_edges={len(g.knn_edges)}")
    print(f"  users with empty collaborative (both signals)={empty_cf}/20")


if __name__ == "__main__":
    main()
