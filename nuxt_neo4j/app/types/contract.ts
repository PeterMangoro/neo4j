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

// Movie recommender (recommendations / similarity / communities).
export interface SimilarityPair {
  user1: string
  user2: string
  score: number
}

export interface ComparisonRow {
  user1: string
  user2: string
  jaccard: number | null
  knn: number | null
}

export interface SimilarityData {
  jaccard: SimilarityPair[]
  knn: SimilarityPair[]
  comparison: ComparisonRow[]
}

export interface Recommendation {
  movieId: string
  title: string
  supporters: number
  avgRating: number
  genreOverlapCount?: number
  directorOverlapCount?: number
  finalScore?: number
}

export interface MethodRecommendations {
  similarTaste: Recommendation[]
  knn: Recommendation[]
}

export interface UserRecommendations {
  collaborative: MethodRecommendations
  hybrid: MethodRecommendations
}

export type RecommendationsData = Record<string, UserRecommendations>

export interface CommunityMember {
  id: string
  name: string
}

export interface CommunityGenreStat {
  name: string
  avgRating: number
  count: number
}

export interface CommunityOccupationStat {
  name: string
  count: number
}

export interface Community {
  id: number
  size: number
  avgAge: number
  topGenres: CommunityGenreStat[]
  topOccupations: CommunityOccupationStat[]
  members: CommunityMember[]
}

export interface CommunitiesData {
  communityCount: number
  modularity: number
  communities: Community[]
}

export interface UserFacet {
  id: string
  name: string
  age: number
  occupation: string
  community: number
  ratingsGiven: number
}

// Healthcare FAERS (Assignment 2) — Leiden sub-phenotypes + case similarity.
export interface HealthcareCommunity {
  id: number
  size: number
  topReactions: string[]
  topGenders: string[]
  topAgeGroups: string[]
  commentary?: string | null
}

export interface HealthcareCommunitiesData {
  communityCount: number
  intro?: string
  communities: HealthcareCommunity[]
}

export interface CaseSimilarityPair {
  case1: string
  case2: string
  similarity: number
  numSharedReactions: number
  sampleReactions: string[]
  sharedDrugs: string[]
}

export interface HealthcareSimilarityData {
  metric: string
  cutoff: number
  pairs: CaseSimilarityPair[]
}

export interface CommunityIndexEntry {
  id: number
  size: number
  label: string
  topReactions: string[]
}

export interface DrugIndexEntry {
  name: string
  slug: string
  severeCases?: number
  caseCount?: number
  source: 'severe' | 'pfizer' | string
}

export interface GraphMeta {
  caseCount?: number
  nodeCount?: number
  relCount?: number
  capped?: boolean
  focusDrug?: string
  focusProduct?: string
  oemNodes?: string[]
}

export interface CuratedGraphData extends GraphData {
  meta?: GraphMeta
}

// Supply chain / automotive BOM (finalProject).
export interface PageRankEntry {
  nodeName: string
  nodeType: string[]
  score: number
  roleLabels?: string[]
}

export interface PageRankData {
  projection: { name: string, nodeCount: number, relationshipCount: number }
  topNodes: PageRankEntry[]
  topFacilities: PageRankEntry[]
}

export interface CommunityComposition {
  group: string
  count: number
}

export interface SupplyChainCommunity {
  id: number
  size: number
  composition: CommunityComposition[]
  commentary?: string
}

export interface SupplyChainCommunitiesData {
  communityCount: number
  intro?: string
  communities: SupplyChainCommunity[]
}

export interface ProductIndexEntry {
  productId: string
  groupName?: string
  slug: string
  source: string
}
