<script setup lang="ts">
import type {
  Stats,
  QueryResult,
  GraphData,
  GraphNode,
  GraphRel,
  SimilarityData,
  CommunitiesData,
  RecommendationsData,
  UserFacet,
  Recommendation
} from '~/types/contract'

useSeoMeta({
  title: 'Movie Recommender',
  description: 'Hybrid movie recommendations with Jaccard taste similarity, FastRP-style embeddings + kNN, Louvain communities, and collaborative/hybrid scoring — fully static, no live database.'
})

const PROJECT = 'movie-recommender'

const { data: stats } = await useProjectData<Stats>(PROJECT, 'stats')
const { data: queries } = await useProjectData<QueryResult[]>(PROJECT, 'queries')
const { data: graph } = await useProjectData<GraphData>(PROJECT, 'graph')
const { data: graphSimilarity } = await useProjectData<GraphData>(PROJECT, 'graph_similarity')
const { data: similarity } = await useProjectData<SimilarityData>(PROJECT, 'similarity')
const { data: communities } = await useProjectData<CommunitiesData>(PROJECT, 'communities')
const { data: recommendations } = await useProjectData<RecommendationsData>(PROJECT, 'recommendations')
const { data: users } = await useProjectData<UserFacet[]>(PROJECT, 'users')

const LABEL_COLORS: Record<string, string> = {
  User: '#3B82F6',
  Movie: '#00C16A',
  Genre: '#F59E0B',
  Director: '#EC4899'
}

const COMMUNITY_COLORS = [
  '#3B82F6', '#00C16A', '#F59E0B', '#EF4444',
  '#8B5CF6', '#EC4899', '#14B8A6', '#F97316'
]

// --- Schema SVG --------------------------------------------------------
const SCHEMA_R = 40
const schemaPos: Record<string, { x: number, y: number }> = {
  User: { x: 100, y: 180 },
  Movie: { x: 380, y: 180 },
  Genre: { x: 660, y: 80 },
  Director: { x: 660, y: 280 }
}
const schemaRels = [
  { id: 'RATED', from: 'User', to: 'Movie', type: 'RATED' },
  { id: 'IN_GENRE', from: 'Movie', to: 'Genre', type: 'IN_GENRE' },
  { id: 'DIRECTED_BY', from: 'Movie', to: 'Director', type: 'DIRECTED_BY' }
]
const schemaNodes = computed(() =>
  Object.entries(schemaPos).map(([label, p]) => ({
    id: label,
    label,
    color: LABEL_COLORS[label] ?? '#64748B',
    x: p.x,
    y: p.y
  }))
)
const schemaEdges = computed(() =>
  schemaRels.map((r) => {
    const a = schemaPos[r.from]!
    const b = schemaPos[r.to]!
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.hypot(dx, dy) || 1
    const ux = dx / len
    const uy = dy / len
    return {
      id: r.id,
      type: r.type,
      x1: a.x + ux * SCHEMA_R,
      y1: a.y + uy * SCHEMA_R,
      x2: b.x - ux * (SCHEMA_R + 9),
      y2: b.y - uy * (SCHEMA_R + 9),
      mx: (a.x + b.x) / 2,
      my: (a.y + b.y) / 2
    }
  })
)

// --- Similarity graph (edge-type toggle) -------------------------------
type SimEdge = 'SIMILAR_TASTE' | 'KNN_SIMILAR'
const simEdgeType = ref<SimEdge>('SIMILAR_TASTE')

const simEdgeItems = [
  { label: 'Jaccard (SIMILAR_TASTE)', value: 'SIMILAR_TASTE' },
  { label: 'kNN cosine (KNN_SIMILAR)', value: 'KNN_SIMILAR' }
]

function communityColor(community: unknown): string {
  const id = typeof community === 'number' ? community : Number(community) || 0
  return COMMUNITY_COLORS[id % COMMUNITY_COLORS.length]!
}

const communityColorMap = computed(() => {
  const map: Record<string, string> = {}
  const count = communities.value?.communityCount ?? 8
  for (let i = 0; i < count; i++) map[`C${i}`] = communityColor(i)
  return map
})

const SIM_SVG = { w: 860, h: 620, nodeR: 16, pad: 48 }
// Circle diameter + label clearance so labels don't sit on neighboring nodes.
const MIN_NODE_GAP = SIM_SVG.nodeR * 2 + 28

function trimEdge(
  x1: number, y1: number, x2: number, y2: number,
  r: number, arrowGap = 9
) {
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  return {
    x1: x1 + ux * r,
    y1: y1 + uy * r,
    x2: x2 - ux * (r + arrowGap),
    y2: y2 - uy * (r + arrowGap)
  }
}

/** Deterministic PRNG so each metric's layout is stable across reloads. */
function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

interface LayoutEdge { from: string, to: string, score: number, id: string }

/**
 * Spring layout for the active similarity metric.
 * Runs unconstrained (no wall clamping — that caused edge stacking), then
 * collision-resolves and fits the bbox into the SVG.
 */
function layoutBySimilarity(
  nodes: GraphNode[],
  edges: LayoutEdge[],
  seed: number
): Map<string, { x: number, y: number }> {
  const { w, h, pad } = SIM_SVG
  const ids = nodes.map(n => n.id)
  const rng = mulberry32(seed)
  const pos = new Map<string, { x: number, y: number, vx: number, vy: number }>()

  const commIds = [...new Set(nodes.map(n =>
    typeof n.community === 'number' ? n.community : Number(n.labels?.[0]?.slice(1) || 0)
  ))].sort((a, b) => a - b)
  const commAngle = new Map<number, number>()
  commIds.forEach((c, i) => commAngle.set(c, (2 * Math.PI * i) / Math.max(commIds.length, 1)))

  // Spread seeds: community ring + unique jitter so identical neighborhoods don't start stacked.
  ids.forEach((id, i) => {
    const n = nodes.find(nn => nn.id === id)!
    const c = typeof n.community === 'number' ? n.community : Number(n.labels?.[0]?.slice(1) || 0)
    const base = commAngle.get(c) ?? 0
    const angle = base + (rng() - 0.5) * 0.9 + (i / ids.length) * 0.15
    const r = 110 + rng() * 90
    pos.set(id, {
      x: w / 2 + r * Math.cos(angle),
      y: h / 2 + r * Math.sin(angle),
      vx: 0,
      vy: 0
    })
  })

  const k = Math.sqrt((w * h) / Math.max(ids.length, 1)) * 1.35
  const deduped: { a: string, b: string, score: number }[] = []
  const seen = new Set<string>()
  for (const e of edges) {
    const a = e.from < e.to ? e.from : e.to
    const b = e.from < e.to ? e.to : e.from
    const key = `${a}:${b}`
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push({ a, b, score: e.score })
  }

  for (let iter = 0; iter < 280; iter++) {
    const alpha = 1 - iter / 280
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const p1 = pos.get(ids[i]!)!
        const p2 = pos.get(ids[j]!)!
        let dx = p1.x - p2.x
        let dy = p1.y - p2.y
        let dist = Math.hypot(dx, dy)
        // Identical starts: nudge apart on a deterministic axis.
        if (dist < 0.01) {
          const a = ((i * 17 + j * 31 + seed) % 360) * (Math.PI / 180)
          dx = Math.cos(a)
          dy = Math.sin(a)
          dist = 0.01
        }
        const repulse = dist < MIN_NODE_GAP
          ? ((MIN_NODE_GAP - dist) / dist) * 3.5
          : ((k * k) / dist) * 0.7 * alpha
        dx = (dx / dist) * repulse
        dy = (dy / dist) * repulse
        p1.vx += dx
        p1.vy += dy
        p2.vx -= dx
        p2.vy -= dy
      }
    }
    for (const { a, b, score } of deduped) {
      const p1 = pos.get(a)
      const p2 = pos.get(b)
      if (!p1 || !p2) continue
      let dx = p2.x - p1.x
      let dy = p2.y - p1.y
      const dist = Math.hypot(dx, dy) || 0.01
      // Weaker attraction so repulsion can keep circles clear.
      const ideal = Math.max(MIN_NODE_GAP * 1.15, k * (1.25 - score * 0.55))
      const attract = (dist - ideal) * 0.08 * (0.35 + score)
      dx = (dx / dist) * attract
      dy = (dy / dist) * attract
      p1.vx += dx
      p1.vy += dy
      p2.vx -= dx
      p2.vy -= dy
    }
    // Soft gravity to center — no hard walls (walls caused edge stacking).
    for (const id of ids) {
      const p = pos.get(id)!
      p.vx += (w / 2 - p.x) * 0.012
      p.vy += (h / 2 - p.y) * 0.012
      p.vx *= 0.78
      p.vy *= 0.78
      p.x += p.vx
      p.y += p.vy
    }
  }

  function separate(gap: number, rounds: number) {
    for (let round = 0; round < rounds; round++) {
      let moved = false
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const p1 = pos.get(ids[i]!)!
          const p2 = pos.get(ids[j]!)!
          let dx = p2.x - p1.x
          let dy = p2.y - p1.y
          let dist = Math.hypot(dx, dy)
          if (dist < 0.01) {
            const a = ((i * 17 + j * 31 + seed) % 360) * (Math.PI / 180)
            dx = Math.cos(a)
            dy = Math.sin(a)
            dist = 0.01
          }
          if (dist >= gap) continue
          const push = (gap - dist) / 2
          const ux = dx / dist
          const uy = dy / dist
          p1.x -= ux * push
          p1.y -= uy * push
          p2.x += ux * push
          p2.y += uy * push
          moved = true
        }
      }
      if (!moved) break
    }
  }

  function fitToBox() {
    let minX = Infinity
    let maxX = -Infinity
    let minY = Infinity
    let maxY = -Infinity
    for (const id of ids) {
      const p = pos.get(id)!
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minY = Math.min(minY, p.y)
      maxY = Math.max(maxY, p.y)
    }
    const spanX = Math.max(maxX - minX, 1)
    const spanY = Math.max(maxY - minY, 1)
    const labelPad = 18
    const availW = w - pad * 2
    const availH = h - pad * 2 - labelPad
    const scale = Math.min(availW / spanX, availH / spanY)
    const ox = pad + (availW - spanX * scale) / 2
    const oy = pad + (availH - spanY * scale) / 2
    for (const id of ids) {
      const p = pos.get(id)!
      p.x = ox + (p.x - minX) * scale
      p.y = oy + (p.y - minY) * scale
    }
  }

  // Separate in free space, fit, then re-separate in screen space.
  // End on separate (not fit) so downscaling cannot reintroduce overlaps.
  separate(MIN_NODE_GAP, 100)
  fitToBox()
  separate(MIN_NODE_GAP, 80)
  // If separation spilled past the pad, center without crushing gaps.
  {
    let minX = Infinity
    let maxX = -Infinity
    let minY = Infinity
    let maxY = -Infinity
    for (const id of ids) {
      const p = pos.get(id)!
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minY = Math.min(minY, p.y)
      maxY = Math.max(maxY, p.y)
    }
    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2
    const dx = w / 2 - cx
    const dy = h / 2 - cy
    for (const id of ids) {
      const p = pos.get(id)!
      p.x += dx
      p.y += dy
    }
  }

  return new Map(ids.map((id) => {
    const p = pos.get(id)!
    return [id, { x: p.x, y: p.y }]
  }))
}

function collectEdges(rels: GraphRel[]): LayoutEdge[] {
  const seen = new Set<string>()
  const out: LayoutEdge[] = []
  for (const r of rels) {
    const a = r.from < r.to ? r.from : r.to
    const b = r.from < r.to ? r.to : r.from
    const key = `${a}:${b}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push({
      id: r.id,
      from: r.from,
      to: r.to,
      score: typeof r.score === 'number' ? r.score : 0
    })
  }
  return out
}

const similaritySvg = computed(() => {
  const g = graphSimilarity.value
  if (!g?.nodes.length) {
    return {
      nodes: [] as { id: string, caption: string, community: number, color: string, x: number, y: number }[],
      edges: [] as { id: string, x1: number, y1: number, x2: number, y2: number }[]
    }
  }

  const activeRels = g.relationships.filter(r => r.type === simEdgeType.value)
  const activeEdges = collectEdges(activeRels)

  const seed = simEdgeType.value === 'SIMILAR_TASTE' ? 42 : 137
  const pos = layoutBySimilarity(g.nodes, activeEdges, seed)

  const nodes = g.nodes.map((n) => {
    const community = typeof n.community === 'number'
      ? n.community
      : Number(n.labels?.[0]?.slice(1) || 0)
    const p = pos.get(n.id) ?? { x: SIM_SVG.w / 2, y: SIM_SVG.h / 2 }
    return {
      id: n.id,
      caption: String(n.caption ?? n.id),
      community,
      color: communityColor(community),
      x: p.x,
      y: p.y
    }
  })

  const edges = activeEdges.flatMap((e) => {
    const p1 = pos.get(e.from)
    const p2 = pos.get(e.to)
    if (!p1 || !p2) return []
    return [{ id: e.id, ...trimEdge(p1.x, p1.y, p2.x, p2.y, SIM_SVG.nodeR) }]
  })

  return { nodes, edges }
})

const similarityLegend = computed(() =>
  Object.entries(communityColorMap.value).map(([label, color]) => ({ label, color }))
)

const PAGE_SIZE = 10
const comparisonPage = ref(1)
const comparisonRows = computed(() => similarity.value?.comparison ?? [])
const pagedComparison = computed(() => {
  const start = (comparisonPage.value - 1) * PAGE_SIZE
  return comparisonRows.value.slice(start, start + PAGE_SIZE)
})

// --- Recommender picker ------------------------------------------------
const ALL_SENTINEL = '__pick__'
const selectedUserId = ref(ALL_SENTINEL)
const method = ref<'collaborative' | 'hybrid'>('hybrid')
const signal = ref<'similarTaste' | 'knn'>('similarTaste')

const userItems = computed(() => [
  { label: 'Select a user…', value: ALL_SENTINEL },
  ...(users.value ?? []).map(u => ({
    label: `${u.name} (${u.id}) · C${u.community}`,
    value: u.id
  }))
])

const methodItems = [
  { label: 'Collaborative', value: 'collaborative' },
  { label: 'Hybrid', value: 'hybrid' }
]
const signalItems = [
  { label: 'Jaccard taste', value: 'similarTaste' },
  { label: 'kNN cosine', value: 'knn' }
]

const selectedUser = computed(() =>
  (users.value ?? []).find(u => u.id === selectedUserId.value) ?? null
)

const currentRecs = computed<Recommendation[]>(() => {
  if (!recommendations.value || selectedUserId.value === ALL_SENTINEL) return []
  const block = recommendations.value[selectedUserId.value]
  if (!block) return []
  return block[method.value][signal.value] ?? []
})

const recPage = ref(1)
watch([selectedUserId, method, signal], () => {
  recPage.value = 1
})
const pagedRecs = computed(() => {
  const start = (recPage.value - 1) * PAGE_SIZE
  return currentRecs.value.slice(start, start + PAGE_SIZE)
})

// Ego graph: target user -> similar users -> recommended movies
const egoGraph = computed<GraphData>(() => {
  if (!graph.value || !graphSimilarity.value || selectedUserId.value === ALL_SENTINEL) {
    return { nodes: [], relationships: [] }
  }
  const uid = selectedUserId.value
  const targetId = `User:${uid}`
  const edgeType: SimEdge = signal.value === 'knn' ? 'KNN_SIMILAR' : 'SIMILAR_TASTE'
  const simRels = graphSimilarity.value.relationships.filter(
    r => r.type === edgeType && (r.from === targetId || r.to === targetId)
  )
  const similarIds = new Set<string>()
  for (const r of simRels) {
    similarIds.add(r.from === targetId ? r.to : r.from)
  }

  const movieIds = currentRecs.value.slice(0, 8).map(r => `Movie:${r.movieId}`)
  const nodeIds = new Set<string>([targetId, ...similarIds, ...movieIds])

  const byId = new Map(graph.value.nodes.map(n => [n.id, n]))
  // Prefer similarity-graph captions/community for users
  for (const n of graphSimilarity.value.nodes) byId.set(n.id, n)

  const nodes: GraphNode[] = []
  for (const id of nodeIds) {
    const n = byId.get(id)
    if (!n) continue
    if (n.labels?.includes('User') || id.startsWith('User:')) {
      const c = typeof n.community === 'number' ? n.community : 0
      nodes.push({ ...n, labels: [`C${c}`], score: id === targetId ? 1 : 0.4 })
    } else {
      nodes.push({ ...n, labels: ['Movie'], score: 0.7 })
    }
  }

  const relationships: GraphRel[] = [
    ...simRels,
    // Link recommended movies to the target for a readable ego layout
    ...movieIds.map(mid => ({
      id: `REC:${uid}:${mid}`,
      from: targetId,
      to: mid,
      type: 'RECOMMENDED'
    }))
  ]
  return { nodes, relationships }
})

const egoColors = computed(() => ({
  ...communityColorMap.value,
  Movie: LABEL_COLORS.Movie!
}))
</script>

<template>
  <ProjectLayout
    title="Graph-Based Movie Recommender"
    subtitle="Hybrid recommendations on a sparse user–movie graph: Jaccard taste similarity, FastRP-style embeddings + kNN, Louvain communities, and content boosts from genre/director overlap."
    dataset="Source: assignments/recommender (20 users · 25 movies · 101 ratings) · offline GDS-equivalent precompute"
  >
    <!-- 1. Hero -->
    <section v-if="stats">
      <StatCards :highlights="stats.highlights" />
      <div class="mt-6">
        <CountsTable
          :node-counts="stats.nodeCounts"
          :rel-counts="stats.relCounts"
        />
      </div>
    </section>

    <!-- 2. Schema -->
    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Graph model
      </h2>
      <p class="mb-4 text-sm text-muted">
        Users rate movies; movies link to genres and directors used for the hybrid content boost.
      </p>
      <div class="rounded-lg border border-default bg-elevated/30 p-4">
        <svg
          viewBox="0 0 760 360"
          class="h-auto w-full text-muted"
          role="img"
          aria-label="Graph schema: User RATED Movie, Movie IN_GENRE Genre, Movie DIRECTED_BY Director."
        >
          <defs>
            <marker
              id="rec-schema-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              marker-width="7"
              marker-height="7"
              orient="auto-start-reverse"
            >
              <path
                d="M 0 0 L 10 5 L 0 10 z"
                fill="currentColor"
              />
            </marker>
          </defs>
          <g
            stroke="currentColor"
            stroke-width="1.5"
            opacity="0.7"
          >
            <line
              v-for="e in schemaEdges"
              :key="e.id"
              :x1="e.x1"
              :y1="e.y1"
              :x2="e.x2"
              :y2="e.y2"
              marker-end="url(#rec-schema-arrow)"
            />
          </g>
          <g
            font-size="10"
            font-weight="600"
            fill="currentColor"
            text-anchor="middle"
          >
            <text
              v-for="e in schemaEdges"
              :key="e.id"
              :x="e.mx"
              :y="e.my - 6"
            >{{ e.type }}</text>
          </g>
          <g>
            <g
              v-for="n in schemaNodes"
              :key="n.id"
            >
              <circle
                :cx="n.x"
                :cy="n.y"
                :r="SCHEMA_R"
                :fill="n.color"
              />
              <text
                :x="n.x"
                :y="n.y + 4"
                text-anchor="middle"
                font-size="12"
                font-weight="700"
                fill="#ffffff"
              >{{ n.label }}</text>
            </g>
          </g>
        </svg>
      </div>
    </section>

    <!-- 3. EDA -->
    <section v-if="queries">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Exploratory analysis
      </h2>
      <p class="mb-4 text-sm text-muted">
        Frozen Cypher-style EDA from the notebook: activity, rating shape, genres, directors, and overlap.
      </p>
      <div class="space-y-4">
        <QueryResult
          v-for="q in queries"
          :key="q.id"
          :query="q"
        />
      </div>
    </section>

    <!-- 4. GDS similarity -->
    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        User similarity (GDS pipeline)
      </h2>
      <p class="mb-4 text-sm text-muted">
        Users connected by the selected similarity metric only (Jaccard or kNN).
        Node positions follow those edges; switch the dropdown to compare layouts.
        Colors = Louvain community.
      </p>

      <div class="mb-4 max-w-sm">
        <USelect
          v-model="simEdgeType"
          :items="simEdgeItems"
        />
      </div>

      <div
        v-if="similaritySvg.nodes.length"
        class="space-y-3"
      >
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span
            v-for="entry in similarityLegend"
            :key="entry.label"
            class="inline-flex items-center gap-1.5 text-sm text-muted"
          >
            <span
              class="size-3 rounded-full"
              :style="{ backgroundColor: entry.color }"
            />
            {{ entry.label }}
          </span>
        </div>

        <div class="rounded-lg border border-default bg-elevated/30 p-4">
          <svg
            :viewBox="`0 0 ${SIM_SVG.w} ${SIM_SVG.h}`"
            class="h-auto w-full text-muted"
            role="img"
            :aria-label="`User similarity graph (${simEdgeType}), nodes colored by Louvain community.`"
          >
            <defs>
              <marker
                id="sim-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                marker-width="7"
                marker-height="7"
                orient="auto-start-reverse"
              >
                <path
                  d="M 0 0 L 10 5 L 0 10 z"
                  fill="currentColor"
                />
              </marker>
            </defs>

            <g
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            >
              <line
                v-for="e in similaritySvg.edges"
                :key="e.id"
                :x1="e.x1"
                :y1="e.y1"
                :x2="e.x2"
                :y2="e.y2"
                opacity="0.7"
                marker-end="url(#sim-arrow)"
              />
            </g>

            <g>
              <g
                v-for="n in similaritySvg.nodes"
                :key="n.id"
              >
                <circle
                  :cx="n.x"
                  :cy="n.y"
                  :r="SIM_SVG.nodeR"
                  :fill="n.color"
                />
                <text
                  :x="n.x"
                  :y="n.y + SIM_SVG.nodeR + 12"
                  text-anchor="middle"
                  font-size="10"
                  font-weight="600"
                  fill="currentColor"
                >{{ n.caption.split(' ')[0] }}</text>
              </g>
            </g>
          </svg>
        </div>
      </div>

      <div
        v-if="comparisonRows.length"
        class="mt-6 overflow-x-auto"
      >
        <h3 class="mb-2 text-base font-semibold text-highlighted">
          Jaccard vs kNN comparison
        </h3>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-default text-left text-muted">
              <th class="px-3 py-2 font-medium">
                User 1
              </th>
              <th class="px-3 py-2 font-medium">
                User 2
              </th>
              <th class="px-3 py-2 font-medium">
                Jaccard
              </th>
              <th class="px-3 py-2 font-medium">
                kNN
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in pagedComparison"
              :key="i"
              class="border-b border-default/60"
            >
              <td class="px-3 py-2">
                {{ row.user1 }}
              </td>
              <td class="px-3 py-2">
                {{ row.user2 }}
              </td>
              <td class="px-3 py-2 text-muted">
                {{ row.jaccard ?? '—' }}
              </td>
              <td class="px-3 py-2 text-muted">
                {{ row.knn ?? '—' }}
              </td>
            </tr>
          </tbody>
        </table>
        <div
          v-if="comparisonRows.length > PAGE_SIZE"
          class="mt-4 flex flex-col items-center justify-between gap-3 sm:flex-row"
        >
          <span class="text-xs text-dimmed">
            Showing {{ (comparisonPage - 1) * PAGE_SIZE + 1 }}–{{ Math.min(comparisonPage * PAGE_SIZE, comparisonRows.length) }}
            of {{ comparisonRows.length }} pairs
          </span>
          <UPagination
            v-model:page="comparisonPage"
            :total="comparisonRows.length"
            :items-per-page="PAGE_SIZE"
            :sibling-count="1"
          />
        </div>
      </div>
    </section>

    <!-- 5. Recommender -->
    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Recommendations
      </h2>
      <p class="mb-4 text-sm text-muted">
        Precomputed for every user. Collaborative uses similar users' high ratings (≥4);
        hybrid adds genre/director overlap against the target's liked movies.
      </p>

      <div class="grid gap-3 sm:grid-cols-3">
        <USelectMenu
          v-model="selectedUserId"
          :items="userItems"
          value-key="value"
          placeholder="User"
          icon="i-lucide-user"
        />
        <USelect
          v-model="method"
          :items="methodItems"
        />
        <USelect
          v-model="signal"
          :items="signalItems"
        />
      </div>

      <div
        v-if="selectedUser"
        class="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted"
      >
        <UBadge
          color="primary"
          variant="subtle"
        >
          Community {{ selectedUser.community }}
        </UBadge>
        <span>{{ selectedUser.occupation }} · age {{ selectedUser.age }}</span>
        <span>{{ selectedUser.ratingsGiven }} ratings</span>
        <UBadge
          color="neutral"
          variant="subtle"
        >
          {{ currentRecs.length }} recommendations
        </UBadge>
      </div>

      <template v-if="selectedUserId !== ALL_SENTINEL">
        <div class="mt-4">
          <GraphView
            :nodes="egoGraph.nodes"
            :relationships="egoGraph.relationships"
            :colors="egoColors"
            height="420px"
          />
        </div>

        <div class="mt-6 overflow-x-auto">
          <table
            v-if="currentRecs.length"
            class="w-full text-sm"
          >
            <thead>
              <tr class="border-b border-default text-left text-muted">
                <th class="px-3 py-2 font-medium">
                  Movie
                </th>
                <th class="px-3 py-2 font-medium">
                  Supporters
                </th>
                <th class="px-3 py-2 font-medium">
                  Avg rating
                </th>
                <th
                  v-if="method === 'hybrid'"
                  class="px-3 py-2 font-medium"
                >
                  Genre overlap
                </th>
                <th
                  v-if="method === 'hybrid'"
                  class="px-3 py-2 font-medium"
                >
                  Director overlap
                </th>
                <th
                  v-if="method === 'hybrid'"
                  class="px-3 py-2 font-medium"
                >
                  Final score
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in pagedRecs"
                :key="row.movieId"
                class="border-b border-default/60"
              >
                <td class="px-3 py-2">
                  {{ row.title }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.supporters }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.avgRating }}
                </td>
                <td
                  v-if="method === 'hybrid'"
                  class="px-3 py-2 text-muted"
                >
                  {{ row.genreOverlapCount ?? 0 }}
                </td>
                <td
                  v-if="method === 'hybrid'"
                  class="px-3 py-2 text-muted"
                >
                  {{ row.directorOverlapCount ?? 0 }}
                </td>
                <td
                  v-if="method === 'hybrid'"
                  class="px-3 py-2 text-muted"
                >
                  {{ row.finalScore ?? '—' }}
                </td>
              </tr>
            </tbody>
          </table>

          <UAlert
            v-else
            class="mt-2"
            icon="i-lucide-info"
            color="neutral"
            variant="subtle"
            title="No collaborative candidates"
            description="Similar users' high-rated movies are already rated by this user (or no similar users). Try Hybrid, or switch the similarity signal."
          />

          <div
            v-if="currentRecs.length > PAGE_SIZE"
            class="mt-4 flex flex-col items-center justify-between gap-3 sm:flex-row"
          >
            <span class="text-xs text-dimmed">
              Showing {{ (recPage - 1) * PAGE_SIZE + 1 }}–{{ Math.min(recPage * PAGE_SIZE, currentRecs.length) }}
              of {{ currentRecs.length }}
            </span>
            <UPagination
              v-model:page="recPage"
              :total="currentRecs.length"
              :items-per-page="PAGE_SIZE"
              :sibling-count="1"
            />
          </div>
        </div>
      </template>
      <p
        v-else
        class="mt-6 text-sm text-muted"
      >
        Pick a user to load precomputed recommendations and an ego-network view.
      </p>
    </section>

    <!-- 6. Communities -->
    <section v-if="communities">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Taste communities
      </h2>
      <p class="mb-4 text-sm text-muted">
        Louvain on the Jaccard user–user graph —
        {{ communities.communityCount }} communities, modularity {{ communities.modularity }}.
      </p>
      <div class="grid gap-4 sm:grid-cols-2">
        <UCard
          v-for="c in communities.communities"
          :key="c.id"
        >
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <span
                  class="size-3 rounded-full"
                  :style="{ backgroundColor: communityColor(c.id) }"
                />
                <h3 class="text-base font-semibold text-highlighted">
                  Community {{ c.id }}
                </h3>
              </div>
              <UBadge
                color="neutral"
                variant="subtle"
              >
                {{ c.size }} members · avg age {{ c.avgAge }}
              </UBadge>
            </div>
          </template>

          <div class="space-y-3 text-sm">
            <div>
              <p class="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
                Top genres
              </p>
              <div class="flex flex-wrap gap-1.5">
                <UBadge
                  v-for="g in c.topGenres"
                  :key="g.name"
                  color="neutral"
                  variant="outline"
                  size="sm"
                >
                  {{ g.name }} ({{ g.avgRating }})
                </UBadge>
                <span
                  v-if="!c.topGenres.length"
                  class="text-muted"
                >—</span>
              </div>
            </div>
            <div>
              <p class="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
                Occupations
              </p>
              <div class="flex flex-wrap gap-1.5">
                <UBadge
                  v-for="o in c.topOccupations"
                  :key="o.name"
                  color="neutral"
                  variant="outline"
                  size="sm"
                >
                  {{ o.name }} ×{{ o.count }}
                </UBadge>
              </div>
            </div>
            <div>
              <p class="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
                Members
              </p>
              <div class="flex flex-wrap gap-1.5">
                <UBadge
                  v-for="m in c.members"
                  :key="m.id"
                  color="primary"
                  variant="subtle"
                  size="sm"
                >
                  {{ m.name }}
                </UBadge>
              </div>
            </div>
          </div>
        </UCard>
      </div>
    </section>
  </ProjectLayout>
</template>
