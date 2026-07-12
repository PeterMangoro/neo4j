#!/usr/bin/env python3
"""Generate the static JSON payloads for the /music-knowledge-graph demo.

This mirrors the Cypher model/queries in P_Mangoro_C1_assn.ipynb but computes
everything directly from the 5 Chinook CSVs in pure Python - no Neo4j/GDS needed
for this project (the queries are deterministic traversals). It writes four files
into the Nuxt app's public/data/music-knowledge-graph/ tree:

    stats.json    - node/relationship counts + headline metrics  (Stats)
    queries.json  - the six graded queries 3a-3f, frozen         (QueryResult[])
    graph.json    - the full graph dump (5,007 nodes / 13,381 rels) (GraphData)
    facets.json   - small helper lists for the explorer's pickers

Usage:
    python export_ass1.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent.parent / "nuxt_neo4j" / "public" / "data" / "music-knowledge-graph"

NODE_LABELS = ["Track", "Composer", "Album", "Artist", "Genre", "MediaType"]
REL_TYPES = ["CONTAINS", "IN_GENRE", "OF_MEDIA_TYPE", "RELEASED", "COMPOSED_BY"]


def is_blank_composer(value: str | None) -> bool:
    """Match the notebook's skip rule: NULL / empty / whitespace-only."""
    if value is None:
        return True
    v = value.strip()
    return v == "" or v.upper() == "NULL"


def read_csv(name: str) -> list[dict[str, str]]:
    with open(HERE / name, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


class MusicGraph:
    """In-memory build of the Chinook music graph from the CSVs."""

    def __init__(self) -> None:
        self.artists = read_csv("Artist.csv")
        self.albums = read_csv("Album.csv")
        self.genres = read_csv("Genre.csv")
        self.media = read_csv("MediaType.csv")
        self.tracks = read_csv("Track.csv")

        # Lookups by primary key (string ids straight from the CSV).
        self.artist_name = {r["ArtistId"]: r["Name"] for r in self.artists}
        self.album_title = {r["AlbumId"]: r["Title"] for r in self.albums}
        self.album_artist = {r["AlbumId"]: r["ArtistId"] for r in self.albums}
        self.genre_name = {r["GenreId"]: r["Name"] for r in self.genres}
        self.media_name = {r["MediaTypeId"]: r["Name"] for r in self.media}

        # Composer nodes: distinct non-empty strings, first-seen order -> 1-based index.
        self.composer_id: "OrderedDict[str, int]" = OrderedDict()
        for r in self.tracks:
            c = r["Composer"]
            if not is_blank_composer(c) and c not in self.composer_id:
                self.composer_id[c] = len(self.composer_id) + 1

        # Reverse name lookups for queries (exact, case-sensitive per the notebook).
        self.genre_by_name = {v: k for k, v in self.genre_name.items()}
        self.media_by_name = {v: k for k, v in self.media_name.items()}
        # Album titles are not unique; keep a name -> [ids] map.
        self.albums_by_title: dict[str, list[str]] = {}
        for aid, title in self.album_title.items():
            self.albums_by_title.setdefault(title, []).append(aid)
        self.artists_by_name: dict[str, list[str]] = {}
        for aid, name in self.artist_name.items():
            self.artists_by_name.setdefault(name, []).append(aid)

    # --- node ids -------------------------------------------------------
    @staticmethod
    def artist_node(aid: str) -> str:
        return f"Artist:{aid}"

    @staticmethod
    def album_node(aid: str) -> str:
        return f"Album:{aid}"

    @staticmethod
    def track_node(tid: str) -> str:
        return f"Track:{tid}"

    @staticmethod
    def genre_node(gid: str) -> str:
        return f"Genre:{gid}"

    @staticmethod
    def media_node(mid: str) -> str:
        return f"MediaType:{mid}"

    def composer_node(self, name: str) -> str:
        return f"Composer:{self.composer_id[name]}"

    # --- graph dump -----------------------------------------------------
    def build_graph(self) -> dict:
        nodes: list[dict] = []
        for r in self.artists:
            nodes.append({"id": self.artist_node(r["ArtistId"]), "caption": r["Name"], "labels": ["Artist"]})
        for r in self.albums:
            nodes.append({"id": self.album_node(r["AlbumId"]), "caption": r["Title"], "labels": ["Album"]})
        for r in self.tracks:
            nodes.append({"id": self.track_node(r["TrackId"]), "caption": r["Name"], "labels": ["Track"]})
        for r in self.genres:
            nodes.append({"id": self.genre_node(r["GenreId"]), "caption": r["Name"], "labels": ["Genre"]})
        for r in self.media:
            nodes.append({"id": self.media_node(r["MediaTypeId"]), "caption": r["Name"], "labels": ["MediaType"]})
        for name, idx in self.composer_id.items():
            nodes.append({"id": f"Composer:{idx}", "caption": name, "labels": ["Composer"]})

        rels: list[dict] = []

        def add(rtype: str, frm: str, to: str) -> None:
            rels.append({"id": f"{rtype}:{frm}->{to}", "from": frm, "to": to, "type": rtype})

        # RELEASED: Artist -> Album
        for r in self.albums:
            add("RELEASED", self.artist_node(r["ArtistId"]), self.album_node(r["AlbumId"]))
        # Track-rooted relationships
        for r in self.tracks:
            t = self.track_node(r["TrackId"])
            add("CONTAINS", self.album_node(r["AlbumId"]), t)
            add("IN_GENRE", t, self.genre_node(r["GenreId"]))
            add("OF_MEDIA_TYPE", t, self.media_node(r["MediaTypeId"]))
            if not is_blank_composer(r["Composer"]):
                add("COMPOSED_BY", t, self.composer_node(r["Composer"]))

        return {"nodes": nodes, "relationships": rels}

    # --- stats ----------------------------------------------------------
    def build_stats(self) -> dict:
        node_counts = {
            "Track": len(self.tracks),
            "Composer": len(self.composer_id),
            "Album": len(self.albums),
            "Artist": len(self.artists),
            "Genre": len(self.genres),
            "MediaType": len(self.media),
        }
        composed = sum(1 for r in self.tracks if not is_blank_composer(r["Composer"]))
        rel_counts = {
            "CONTAINS": len(self.tracks),
            "IN_GENRE": len(self.tracks),
            "OF_MEDIA_TYPE": len(self.tracks),
            "RELEASED": len(self.albums),
            "COMPOSED_BY": composed,
        }
        total_nodes = sum(node_counts.values())
        total_rels = sum(rel_counts.values())
        return {
            "nodeCounts": [{"label": k, "count": node_counts[k]} for k in NODE_LABELS],
            "relCounts": [{"type": k, "count": rel_counts[k]} for k in REL_TYPES],
            "highlights": [
                {"label": "Nodes", "value": f"{total_nodes:,}"},
                {"label": "Relationships", "value": f"{total_rels:,}"},
                {"label": "Node types", "value": len(NODE_LABELS)},
                {"label": "Relationship types", "value": len(REL_TYPES)},
            ],
        }

    # --- the six graded queries (3a-3f) --------------------------------
    def _tracks_in_genre(self, gid: str) -> set[str]:
        return {r["TrackId"] for r in self.tracks if r["GenreId"] == gid}

    def _tracks_by_composer(self, name: str) -> set[str]:
        return {r["TrackId"] for r in self.tracks if r["Composer"] == name}

    def q_3a(self) -> dict:
        gid = self.genre_by_name.get("Jazz")
        jazz = self._tracks_in_genre(gid) if gid else set()
        by_miles = self._tracks_by_composer("Miles Davis")
        names = sorted({self._track_name(t) for t in (jazz & by_miles)})
        return self._result(
            "3a", "Jazz tracks composed by Miles Davis",
            "Tracks in the Jazz genre whose composer is Miles Davis.",
            "MATCH (g:Genre {name:'Jazz'})<-[:IN_GENRE]-(t:Track)-[:COMPOSED_BY]->"
            "(c:Composer {name:'Miles Davis'})\nRETURN t.name AS track",
            ["track"], [{"track": n} for n in names],
        )

    def q_3b(self) -> dict:
        mid = self.media_by_name.get("AAC audio file")
        track_albums = {r["TrackId"]: r["AlbumId"] for r in self.tracks}
        aac_tracks = [r for r in self.tracks if r["MediaTypeId"] == mid] if mid else []
        artist_ids = set()
        for r in aac_tracks:
            artist_id = self.album_artist.get(track_albums.get(r["TrackId"]))
            if artist_id:
                artist_ids.add(artist_id)
        names = sorted({self.artist_name[a] for a in artist_ids})
        return self._result(
            "3b", "Artists with an AAC-audio-file track",
            "Artists who have at least one track distributed as an 'AAC audio file'.",
            "MATCH (:MediaType {name:'AAC audio file'})<-[:OF_MEDIA_TYPE]-(:Track)<-[:CONTAINS]-"
            "(:Album)<-[:RELEASED]-(a:Artist)\nRETURN DISTINCT a.name AS artist",
            ["artist"], [{"artist": n} for n in names],
        )

    def q_3c(self) -> dict:
        album_ids = self.albums_by_title.get("Bongo Fury", [])
        names = sorted({self.artist_name[self.album_artist[a]] for a in album_ids})
        return self._result(
            "3c", 'Artist(s) who released "Bongo Fury"',
            "Artists linked by RELEASED to the album titled 'Bongo Fury'.",
            "MATCH (a:Artist)-[:RELEASED]->(:Album {title:'Bongo Fury'})\nRETURN a.name AS artist",
            ["artist"], [{"artist": n} for n in names],
        )

    def q_3d(self) -> dict:
        led = set(self.artists_by_name.get("Led Zeppelin", []))
        coda_albums = [a for a in self.albums_by_title.get("Coda", []) if self.album_artist[a] in led]
        coda = set(coda_albums)
        names = sorted({self._track_name(r["TrackId"]) for r in self.tracks if r["AlbumId"] in coda})
        return self._result(
            "3d", 'Tracks on Led Zeppelin\'s "Coda"',
            "All tracks contained in Led Zeppelin's album 'Coda'.",
            "MATCH (:Artist {name:'Led Zeppelin'})-[:RELEASED]->(:Album {title:'Coda'})"
            "-[:CONTAINS]->(t:Track)\nRETURN DISTINCT t.name AS track",
            ["track"], [{"track": n} for n in names],
        )

    def q_3e(self) -> dict:
        composer = "Alanis Morissette & Glenn Ballard"
        tids = self._tracks_by_composer(composer)
        album_ids = {r["AlbumId"] for r in self.tracks if r["TrackId"] in tids}
        titles = sorted({self.album_title[a] for a in album_ids})
        return self._result(
            "3e", 'Albums with a track composed by "Alanis Morissette & Glenn Ballard"',
            "Albums that contain at least one track composed by this writing duo.",
            "MATCH (:Composer {name:'Alanis Morissette & Glenn Ballard'})<-[:COMPOSED_BY]-"
            "(t:Track)<-[:CONTAINS]-(a:Album)\nRETURN DISTINCT a.title AS album",
            ["album"], [{"album": t} for t in titles],
        )

    def q_3f(self) -> dict:
        albums_with_missing = {
            r["AlbumId"] for r in self.tracks if is_blank_composer(r["Composer"])
        }
        titles = sorted({self.album_title[a] for a in albums_with_missing if a in self.album_title})
        return self._result(
            "3f", "Albums with a track that has no composer",
            "Albums containing at least one track that lacks a COMPOSED_BY relationship.",
            "MATCH (a:Album)-[:CONTAINS]->(t:Track)\nWHERE NOT (t)-[:COMPOSED_BY]->()\n"
            "RETURN DISTINCT a.title AS albumName",
            ["albumName"], [{"albumName": t} for t in titles],
        )

    # --- helpers --------------------------------------------------------
    def _track_name(self, tid: str) -> str:
        return self._track_name_map[tid]

    @property
    def _track_name_map(self) -> dict[str, str]:
        if not hasattr(self, "_tnm"):
            self._tnm = {r["TrackId"]: r["Name"] for r in self.tracks}
        return self._tnm

    @staticmethod
    def _result(qid, title, description, cypher, columns, rows) -> dict:
        return {
            "id": qid,
            "title": title,
            "description": description,
            "cypher": cypher,
            "columns": columns,
            "rows": rows,
            "count": len(rows),
        }

    def build_queries(self) -> list[dict]:
        return [self.q_3a(), self.q_3b(), self.q_3c(), self.q_3d(), self.q_3e(), self.q_3f()]

    # --- facets (explorer pickers) -------------------------------------
    def build_facets(self) -> dict:
        genre_track = {r["GenreId"]: 0 for r in self.genres}
        media_track = {r["MediaTypeId"]: 0 for r in self.media}
        for r in self.tracks:
            genre_track[r["GenreId"]] = genre_track.get(r["GenreId"], 0) + 1
            media_track[r["MediaTypeId"]] = media_track.get(r["MediaTypeId"], 0) + 1
        genres = sorted(
            ({"id": self.genre_node(gid), "name": self.genre_name[gid], "trackCount": n}
             for gid, n in genre_track.items()),
            key=lambda g: (-g["trackCount"], g["name"]),
        )
        media = sorted(
            ({"id": self.media_node(mid), "name": self.media_name[mid], "trackCount": n}
             for mid, n in media_track.items()),
            key=lambda m: (-m["trackCount"], m["name"]),
        )
        artists = sorted(
            ({"id": self.artist_node(r["ArtistId"]), "name": r["Name"]} for r in self.artists),
            key=lambda a: a["name"].lower(),
        )
        return {"genres": genres, "mediaTypes": media, "artists": artists}


def write_json(path: Path, data, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if compact:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Export music-knowledge-graph static JSON payloads.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = ap.parse_args()

    g = MusicGraph()
    stats = g.build_stats()
    queries = g.build_queries()
    graph = g.build_graph()
    facets = g.build_facets()

    # Integrity checks - fail loudly if the source data drifts.
    assert len(graph["nodes"]) == 5007, f"expected 5007 nodes, got {len(graph['nodes'])}"
    assert len(graph["relationships"]) == 13381, (
        f"expected 13381 rels, got {len(graph['relationships'])}"
    )
    q3f = next(q for q in queries if q["id"] == "3f")
    assert q3f["count"] == 82, f"expected 3f=82 albums, got {q3f['count']}"

    out = args.out
    write_json(out / "stats.json", stats)
    write_json(out / "queries.json", queries)
    write_json(out / "facets.json", facets)
    write_json(out / "graph.json", graph, compact=True)

    print(f"Wrote music-knowledge-graph JSON to {out}")
    print(f"  nodes={len(graph['nodes'])} rels={len(graph['relationships'])}")
    for q in queries:
        print(f"  {q['id']}: {q['count']} rows - {q['title']}")


if __name__ == "__main__":
    main()
