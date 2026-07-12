// Shared data contract for the precomputed, fully-static Neo4j project demos.
// Every Python generator (export_<project>.py) must emit JSON matching these shapes,
// and every page/component consumes them through this single spec.

export interface CountEntry {
  label: string
  count: number
}

export interface RelCountEntry {
  type: string
  count: number
}

export interface Highlight {
  label: string
  value: string | number
}

export interface Stats {
  nodeCounts: CountEntry[]
  relCounts: RelCountEntry[]
  highlights: Highlight[]
}

export interface QueryResult {
  id: string
  title: string
  description: string
  cypher: string
  columns: string[]
  rows: Record<string, unknown>[]
  count: number
}

// NVL-shaped graph payload: nodes carry `id`, relationships carry `from`/`to`.
export interface GraphNode {
  id: string
  caption?: string
  labels?: string[]
  score?: number
  community?: number
  [key: string]: unknown
}

export interface GraphRel {
  id: string
  from: string
  to: string
  type: string
  [key: string]: unknown
}

export interface GraphData {
  nodes: GraphNode[]
  relationships: GraphRel[]
}

// Music KG explorer pickers (facets.json).
export interface FacetEntry {
  id: string
  name: string
  trackCount: number
}

export interface ArtistFacet {
  id: string
  name: string
}

export interface Facets {
  genres: FacetEntry[]
  mediaTypes: FacetEntry[]
  artists: ArtistFacet[]
}
