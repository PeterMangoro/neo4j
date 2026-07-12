<script setup lang="ts">
import type { Stats, QueryResult, GraphData, GraphNode, Facets } from '~/types/contract'

useSeoMeta({
  title: 'Music Knowledge Graph',
  description: 'A Chinook music catalog as a Neo4j property graph: 5,007 nodes, 13,381 relationships, the six graded Cypher queries, and a fully client-side graph explorer.'
})

// Small payloads: prerendered into the static HTML.
const { data: stats } = await useProjectData<Stats>('music-knowledge-graph', 'stats')
const { data: queries } = await useProjectData<QueryResult[]>('music-knowledge-graph', 'queries')
const { data: facets } = await useProjectData<Facets>('music-knowledge-graph', 'facets')

// Full graph (~1.7 MB): fetched lazily in the browser, never inlined.
const { data: graph, status: graphStatus } = useProjectData<GraphData>('music-knowledge-graph', 'graph', { clientOnly: true })

const LABEL_COLORS: Record<string, string> = {
  Artist: '#3B82F6',
  Album: '#8B5CF6',
  Track: '#00C16A',
  Genre: '#F59E0B',
  MediaType: '#EC4899',
  Composer: '#EF4444'
}

// Static schema "meta-graph": one node per label, one edge per relationship type.
// Rendered as a fixed-layout SVG (not NVL) so it is always crisp and never blank.
const SCHEMA_R = 38
const schemaPos: Record<string, { x: number, y: number }> = {
  Artist: { x: 80, y: 180 },
  Album: { x: 270, y: 180 },
  Track: { x: 460, y: 180 },
  Genre: { x: 710, y: 64 },
  MediaType: { x: 710, y: 180 },
  Composer: { x: 710, y: 296 }
}
const schemaRels: { id: string, from: string, to: string, type: string }[] = [
  { id: 'RELEASED', from: 'Artist', to: 'Album', type: 'RELEASED' },
  { id: 'CONTAINS', from: 'Album', to: 'Track', type: 'CONTAINS' },
  { id: 'IN_GENRE', from: 'Track', to: 'Genre', type: 'IN_GENRE' },
  { id: 'OF_MEDIA_TYPE', from: 'Track', to: 'MediaType', type: 'OF_MEDIA_TYPE' },
  { id: 'COMPOSED_BY', from: 'Track', to: 'Composer', type: 'COMPOSED_BY' }
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

// Trim each edge to the node rims so the arrowhead lands on the target circle.
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

interface TrackRow {
  id: string
  name: string
  artistId: string
  artist: string
  albumId: string
  album: string
  genreId: string
  genre: string
  mediaId: string
  mediaType: string
  composerId: string
  composer: string
}

// Build lookups + a flat track table from the loaded graph (runs once on the client).
const index = computed(() => {
  const g = graph.value
  if (!g) return null

  const byId = new Map<string, GraphNode>()
  for (const n of g.nodes) byId.set(n.id, n)

  const trackAlbum = new Map<string, string>()
  const albumArtist = new Map<string, string>()
  const trackGenre = new Map<string, string>()
  const trackMedia = new Map<string, string>()
  const trackComposer = new Map<string, string>()
  for (const r of g.relationships) {
    if (r.type === 'CONTAINS') trackAlbum.set(r.to, r.from)
    else if (r.type === 'RELEASED') albumArtist.set(r.to, r.from)
    else if (r.type === 'IN_GENRE') trackGenre.set(r.from, r.to)
    else if (r.type === 'OF_MEDIA_TYPE') trackMedia.set(r.from, r.to)
    else if (r.type === 'COMPOSED_BY') trackComposer.set(r.from, r.to)
  }

  const cap = (id: string): string => (id ? byId.get(id)?.caption ?? '' : '')

  const rows: TrackRow[] = []
  for (const n of g.nodes) {
    if (!n.labels?.includes('Track')) continue
    const albumId = trackAlbum.get(n.id) ?? ''
    const artistId = albumArtist.get(albumId) ?? ''
    const genreId = trackGenre.get(n.id) ?? ''
    const mediaId = trackMedia.get(n.id) ?? ''
    const composerId = trackComposer.get(n.id) ?? ''
    rows.push({
      id: n.id,
      name: n.caption ?? n.id,
      artistId,
      artist: cap(artistId),
      albumId,
      album: cap(albumId),
      genreId,
      genre: cap(genreId),
      mediaId,
      mediaType: cap(mediaId),
      composerId,
      composer: cap(composerId)
    })
  }
  return { byId, rows }
})

// Sentinel for the "All …" option: reka-ui's Select/Combobox throw on an
// empty-string item value, so the no-filter choice needs a non-empty value.
const ALL = '__all__'

const genreId = ref(ALL)
const mediaId = ref(ALL)
const artistId = ref(ALL)
const search = ref('')

const genreItems = computed(() => [
  { label: 'All genres', value: ALL },
  ...(facets.value?.genres ?? []).map(g => ({ label: `${g.name} (${g.trackCount})`, value: g.id }))
])
const mediaItems = computed(() => [
  { label: 'All media types', value: ALL },
  ...(facets.value?.mediaTypes ?? []).map(m => ({ label: `${m.name} (${m.trackCount})`, value: m.id }))
])
const artistItems = computed(() => [
  { label: 'All artists', value: ALL },
  ...(facets.value?.artists ?? []).map(a => ({ label: a.name, value: a.id }))
])

const filtered = computed<TrackRow[]>(() => {
  const idx = index.value
  if (!idx) return []
  const q = search.value.trim().toLowerCase()
  return idx.rows.filter(r =>
    (genreId.value === ALL || r.genreId === genreId.value)
    && (mediaId.value === ALL || r.mediaId === mediaId.value)
    && (artistId.value === ALL || r.artistId === artistId.value)
    && (!q || r.name.toLowerCase().includes(q))
  )
})

const GRAPH_CAP = 60
const PAGE_SIZE = 10

// Bounded subgraph around the (capped) current track selection so NVL stays readable.
const subgraph = computed<GraphData>(() => {
  const idx = index.value
  if (!idx) return { nodes: [], relationships: [] }
  const ids = new Set<string>()
  for (const t of filtered.value.slice(0, GRAPH_CAP)) {
    ids.add(t.id)
    if (t.albumId) ids.add(t.albumId)
    if (t.artistId) ids.add(t.artistId)
    if (t.genreId) ids.add(t.genreId)
    if (t.mediaId) ids.add(t.mediaId)
    if (t.composerId) ids.add(t.composerId)
  }
  const nodes: GraphNode[] = []
  for (const id of ids) {
    const n = idx.byId.get(id)
    if (n) nodes.push(n)
  }
  const relationships = (graph.value?.relationships ?? []).filter(
    r => ids.has(r.from) && ids.has(r.to)
  )
  return { nodes, relationships }
})

const hasFilters = computed(() =>
  genreId.value !== ALL || mediaId.value !== ALL || artistId.value !== ALL || !!search.value.trim()
)

function resetFilters() {
  genreId.value = ALL
  mediaId.value = ALL
  artistId.value = ALL
  search.value = ''
}

const page = ref(1)
const displayRows = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})

// Jump back to the first page whenever the filters change the result set.
watch([genreId, mediaId, artistId, search], () => {
  page.value = 1
})
</script>

<template>
  <ProjectLayout
    title="Music Knowledge Graph"
    subtitle="A Chinook-style music store modeled as a Neo4j property graph - artists, albums, tracks, genres, media types and composers."
    dataset="Source: Chinook CSVs · 6 node labels, 5 relationship types"
  >
    <!-- 1. Headline metrics -->
    <section v-if="stats">
      <StatCards :highlights="stats.highlights" />
      <div class="mt-6">
        <CountsTable
          :node-counts="stats.nodeCounts"
          :rel-counts="stats.relCounts"
        />
      </div>
    </section>

    <!-- 2. Schema meta-graph -->
    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Graph model
      </h2>
      <p class="mb-4 text-sm text-muted">
        The schema at a glance: each label and the relationship types connecting them.
      </p>
      <div class="rounded-lg border border-default bg-elevated/30 p-4">
        <svg
          viewBox="0 0 800 360"
          class="h-auto w-full text-muted"
          role="img"
          aria-label="Graph schema: Artist RELEASED Album CONTAINS Track, with Track IN_GENRE Genre, OF_MEDIA_TYPE MediaType and COMPOSED_BY Composer."
        >
          <defs>
            <marker
              id="schema-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
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
              marker-end="url(#schema-arrow)"
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
              :y="e.my - 5"
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

    <!-- 3. Graded queries -->
    <section v-if="queries">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Graded questions (3a-3f)
      </h2>
      <p class="mb-4 text-sm text-muted">
        The six required read queries, with results frozen from the graph build.
      </p>
      <div class="space-y-4">
        <QueryResult
          v-for="q in queries"
          :key="q.id"
          :query="q"
        />
      </div>
    </section>

    <!-- 4. Interactive explorer -->
    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Explore the catalog
      </h2>
      <p class="mb-4 text-sm text-muted">
        Only six queries were precomputed, yet the full graph ships with the page - so you can
        ask your own questions client-side (e.g. pick <span class="font-medium">Rock</span> to
        see all 1,297 rock tracks). No database, all in the browser.
      </p>

      <div
        v-if="graphStatus === 'pending' || graphStatus === 'idle'"
        class="flex items-center gap-3 rounded-lg border border-default bg-elevated/30 p-6 text-sm text-muted"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="size-4 animate-spin"
        />
        Loading the full graph (~1.7 MB)…
      </div>

      <template v-else>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <USelect
            v-model="genreId"
            :items="genreItems"
            placeholder="Genre"
            icon="i-lucide-tags"
          />
          <USelect
            v-model="mediaId"
            :items="mediaItems"
            placeholder="Media type"
            icon="i-lucide-disc"
          />
          <USelectMenu
            v-model="artistId"
            :items="artistItems"
            value-key="value"
            placeholder="Artist"
            icon="i-lucide-mic-vocal"
          />
          <UInput
            v-model="search"
            placeholder="Search track name…"
            icon="i-lucide-search"
          />
        </div>

        <div class="mt-3 flex flex-wrap items-center gap-3">
          <UBadge
            color="neutral"
            variant="subtle"
          >
            {{ filtered.length.toLocaleString() }} tracks match
          </UBadge>
          <span class="text-sm text-muted">
            graph shows {{ Math.min(filtered.length, GRAPH_CAP) }} ·
            {{ PAGE_SIZE }} per page
          </span>
          <UButton
            v-if="hasFilters"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            label="Reset"
            @click="resetFilters"
          />
        </div>

        <div class="mt-4">
          <GraphView
            :nodes="subgraph.nodes"
            :relationships="subgraph.relationships"
            :colors="LABEL_COLORS"
            height="560px"
          />
        </div>

        <div class="mt-6 overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-default text-left text-muted">
                <th class="px-3 py-2 font-medium">
                  Track
                </th>
                <th class="px-3 py-2 font-medium">
                  Artist
                </th>
                <th class="px-3 py-2 font-medium">
                  Album
                </th>
                <th class="px-3 py-2 font-medium">
                  Genre
                </th>
                <th class="px-3 py-2 font-medium">
                  Media type
                </th>
                <th class="px-3 py-2 font-medium">
                  Composer
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in displayRows"
                :key="row.id"
                class="border-b border-default/60"
              >
                <td class="px-3 py-2">
                  {{ row.name }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.artist || '—' }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.album || '—' }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.genre || '—' }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.mediaType || '—' }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ row.composer || '—' }}
                </td>
              </tr>
            </tbody>
          </table>
          <p
            v-if="filtered.length === 0"
            class="py-6 text-center text-sm text-muted"
          >
            No tracks match these filters.
          </p>
          <div
            v-else-if="filtered.length > PAGE_SIZE"
            class="mt-4 flex flex-col items-center justify-between gap-3 sm:flex-row"
          >
            <span class="text-xs text-dimmed">
              Showing {{ (page - 1) * PAGE_SIZE + 1 }}–{{ Math.min(page * PAGE_SIZE, filtered.length) }}
              of {{ filtered.length.toLocaleString() }} tracks
            </span>
            <UPagination
              v-model:page="page"
              :total="filtered.length"
              :items-per-page="PAGE_SIZE"
              :sibling-count="1"
            />
          </div>
        </div>
      </template>
    </section>
  </ProjectLayout>
</template>
