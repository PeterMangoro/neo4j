<script setup lang="ts">
import type {
  Stats,
  QueryResult,
  PageRankData,
  SupplyChainCommunitiesData,
  ProductIndexEntry,
  CuratedGraphData
} from '~/types/contract'

useSeoMeta({
  title: 'Automotive Supply-Chain Risk',
  description: 'Multi-tier automotive production network: Cypher analytics, PageRank chokepoints, Louvain BOM modules, and curated facility/BOM explorers — fully static, no live database.'
})

const PROJECT = 'supply-chain'

const { data: stats } = await useProjectData<Stats>(PROJECT, 'stats')
const { data: queries } = await useProjectData<QueryResult[]>(PROJECT, 'queries')
const { data: pagerank } = await useProjectData<PageRankData>(PROJECT, 'pagerank')
const { data: communities } = await useProjectData<SupplyChainCommunitiesData>(PROJECT, 'communities')
const { data: productIndex } = await useProjectData<ProductIndexEntry[]>(PROJECT, 'product_index')
const { data: facilityGraph } = await useProjectData<CuratedGraphData>(PROJECT, 'graph_facility')

const GROUP_COLORS: Record<string, string> = {
  car: '#3B82F6',
  engine: '#EF4444',
  gear: '#F59E0B',
  battery: '#00C16A',
  seat: '#8B5CF6',
  seat_componment: '#EC4899',
  battery_componment: '#14B8A6',
  ProductGroup: '#64748B',
  Facility: '#0EA5E9',
  OEM: '#DC2626',
  SupplierSite: '#6B7280',
  Production: '#F97316',
  Inventory: '#A855F7',
  unassigned: '#94A3B8'
}

// --- Schema SVG --------------------------------------------------------
const SCHEMA_R = 32
const schemaPos: Record<string, { x: number, y: number }> = {
  Facility: { x: 120, y: 150 },
  Product: { x: 380, y: 150 },
  ProductGroup: { x: 640, y: 150 },
  Customer: { x: 120, y: 340 },
  DemandFact: { x: 380, y: 340 }
}
const schemaRels: { id: string, from: string, to: string, type: string, loop?: boolean }[] = [
  { id: 'SHIPS_TO', from: 'Facility', to: 'Facility', type: 'SHIPS_TO', loop: true },
  { id: 'REQUIRES', from: 'Product', to: 'Product', type: 'REQUIRES', loop: true },
  { id: 'BELONGS_TO', from: 'Product', to: 'ProductGroup', type: 'BELONGS_TO' },
  { id: 'PRODUCES', from: 'Facility', to: 'Product', type: 'PRODUCES' },
  { id: 'HAS_DEMAND', from: 'Facility', to: 'DemandFact', type: 'HAS_DEMAND' },
  { id: 'ORDERS', from: 'Customer', to: 'DemandFact', type: 'ORDERS' }
]
const schemaNodes = computed(() =>
  Object.entries(schemaPos).map(([label, p]) => ({
    id: label,
    label,
    color: GROUP_COLORS[label] ?? '#64748B',
    x: p.x,
    y: p.y
  }))
)
const schemaEdges = computed(() =>
  schemaRels.map((r) => {
    const a = schemaPos[r.from]!
    if (r.loop) {
      // Arc above the node: leave right rim, curve up, re-enter left rim.
      const x1 = a.x + SCHEMA_R * 0.55
      const y1 = a.y - SCHEMA_R * 0.75
      const x2 = a.x - SCHEMA_R * 0.55
      const y2 = a.y - SCHEMA_R * 0.75
      return {
        id: r.id,
        type: r.type,
        loop: true as const,
        d: `M ${x1} ${y1} C ${a.x + 48} ${a.y - 78}, ${a.x - 48} ${a.y - 78}, ${x2} ${y2}`,
        mx: a.x,
        my: a.y - 86
      }
    }
    const b = schemaPos[r.to]!
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.hypot(dx, dy) || 1
    const ux = dx / len
    const uy = dy / len
    return {
      id: r.id,
      type: r.type,
      loop: false as const,
      d: '',
      x1: a.x + ux * SCHEMA_R,
      y1: a.y + uy * SCHEMA_R,
      x2: b.x - ux * (SCHEMA_R + 9),
      y2: b.y - uy * (SCHEMA_R + 9),
      mx: (a.x + b.x) / 2,
      my: (a.y + b.y) / 2
    }
  })
)

const edaQueries = computed(() =>
  (queries.value ?? []).filter(q => q.id.startsWith('eda-'))
)
const analyticsQueries = computed(() =>
  (queries.value ?? []).filter(q => q.id.startsWith('analytics-'))
)

// --- Explorer ----------------------------------------------------------
type ExplorerTab = 'facility' | 'bom'
const explorerTab = ref<ExplorerTab>('facility')

const productItems = computed(() =>
  (productIndex.value ?? []).map(p => ({
    label: `${p.productId} (${p.groupName ?? '?'}) · ${p.source}`,
    value: p.slug
  }))
)
const selectedProductSlug = ref<string>('')

watch(productIndex, (idx) => {
  if (idx?.length && !selectedProductSlug.value) {
    selectedProductSlug.value = idx[0]!.slug
  }
}, { immediate: true })

const bomFile = computed(() => {
  const slug = selectedProductSlug.value
  return slug ? `graph_bom_${slug}` : null
})

const {
  data: bomGraph,
  status: bomStatus,
  error: bomError
} = await useAsyncData(
  'supply-chain-bom-graph',
  async () => {
    const file = bomFile.value
    if (!file) return null as CuratedGraphData | null
    return await $fetch<CuratedGraphData>(`/data/${PROJECT}/${file}.json`)
  },
  { watch: [bomFile], server: false }
)

const facilityColors = computed(() => {
  const map: Record<string, string> = { ...GROUP_COLORS }
  for (const n of facilityGraph.value?.nodes ?? []) {
    const id = n.id.replace('Facility:', '')
    if (id === 'zp7' || id === 'zp8') map.Facility = GROUP_COLORS.OEM!
    const extra = n.labels?.find(l => ['OEM', 'Production', 'Inventory'].includes(l))
    if (extra) map[n.labels?.[0] ?? 'Facility'] = GROUP_COLORS[extra] ?? map.Facility!
  }
  return map
})

function graphColors(nodes: { labels?: string[] }[]): Record<string, string> {
  const map: Record<string, string> = { ...GROUP_COLORS }
  for (const n of nodes) {
    const labels = n.labels ?? []
    const primary = labels[0] ?? 'Node'
    if (primary === 'Product' && labels[1]) {
      map[primary] = GROUP_COLORS[labels[1]] ?? GROUP_COLORS.car!
    } else if (primary === 'Facility') {
      map[primary] = labels.includes('OEM') ? GROUP_COLORS.OEM! : GROUP_COLORS.Facility!
    } else {
      map[primary] = GROUP_COLORS[primary] ?? '#64748B'
    }
  }
  return map
}

const bomColors = computed(() =>
  bomGraph.value?.nodes?.length ? graphColors(bomGraph.value.nodes) : GROUP_COLORS
)
</script>

<template>
  <ProjectLayout
    title="Automotive Supply-Chain Risk"
    subtitle="Moetz et al. (2020) production-network instance: multi-hop BOM dependencies, supplier lanes, PageRank chokepoints, and Louvain product modules — curated subgraphs only; no live database at runtime."
    dataset="Source: 28,049 products · 87,059 REQUIRES · 12 facilities · 11 SHIPS_TO · offline precompute from workbook"
  >
    <section v-if="stats">
      <StatCards :highlights="stats.highlights" />
      <div class="mt-6">
        <CountsTable
          :node-counts="stats.nodeCounts"
          :rel-counts="stats.relCounts"
        />
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Graph model
      </h2>
      <p class="mb-4 text-sm text-muted">
        Facilities ship components along <code class="text-xs">SHIPS_TO</code> lanes;
        products form a deep BOM via <code class="text-xs">REQUIRES</code>; demand facts wire customers to OEM nodes.
      </p>
      <div class="rounded-lg border border-default bg-elevated/30 p-4">
        <svg
          viewBox="0 0 760 420"
          class="h-auto w-full text-muted"
          role="img"
          aria-label="Supply-chain schema: Facility SHIPS_TO Facility; Product REQUIRES Product; Facility PRODUCES Product; Product BELONGS_TO ProductGroup; Facility HAS_DEMAND DemandFact; Customer ORDERS DemandFact."
        >
          <defs>
            <marker
              id="sc-schema-arrow"
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
            fill="none"
            opacity="0.65"
          >
            <template
              v-for="e in schemaEdges"
              :key="e.id"
            >
              <path
                v-if="e.loop"
                :d="e.d"
                marker-end="url(#sc-schema-arrow)"
              />
              <line
                v-else
                :x1="e.x1"
                :y1="e.y1"
                :x2="e.x2"
                :y2="e.y2"
                marker-end="url(#sc-schema-arrow)"
              />
            </template>
          </g>
          <g
            font-size="9"
            font-weight="600"
            fill="currentColor"
            text-anchor="middle"
          >
            <text
              v-for="e in schemaEdges"
              :key="`${e.id}-label`"
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
                font-size="10"
                font-weight="700"
                fill="#ffffff"
              >{{ n.label }}</text>
            </g>
          </g>
        </svg>
      </div>
    </section>

    <section v-if="edaQueries.length">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Exploratory analysis
      </h2>
      <p class="mb-4 text-sm text-muted">
        Structural EDA from the notebook: entity layers, BOM width, lanes, capacity, and component spread.
      </p>
      <div class="space-y-4">
        <QueryResult
          v-for="q in edaQueries"
          :key="q.id"
          :query="q"
        />
      </div>
    </section>

    <section v-if="analyticsQueries.length">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Deeper analytics (Option 2)
      </h2>
      <p class="mb-4 text-sm text-muted">
        Concentration risk, lane fragility, and risk-adjusted component priority — integrating BOM reach with logistics exposure.
      </p>
      <div class="space-y-4">
        <QueryResult
          v-for="q in analyticsQueries"
          :key="q.id"
          :query="q"
        />
      </div>
    </section>

    <section v-if="pagerank">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        PageRank chokepoints
      </h2>
      <p class="mb-4 text-sm text-muted">
        GDS PageRank on the projected automotive network ({{
          pagerank.projection.nodeCount.toLocaleString()
        }} nodes). OEM sites <strong class="text-highlighted">zp7</strong> and
        <strong class="text-highlighted">zp8</strong> dominate facility influence; product-group hubs
        (<code class="text-xs">car</code>, <code class="text-xs">engine</code>, <code class="text-xs">gear</code>) lead node scores.
      </p>
      <div class="grid gap-6 lg:grid-cols-2">
        <div>
          <h3 class="mb-2 text-sm font-semibold text-highlighted">
            Top facilities
          </h3>
          <div class="overflow-x-auto rounded-lg border border-default">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-default bg-elevated/40 text-left text-muted">
                  <th class="px-3 py-2">
                    Facility
                  </th>
                  <th class="px-3 py-2">
                    Role
                  </th>
                  <th class="px-3 py-2 text-right">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(f, i) in pagerank.topFacilities"
                  :key="f.nodeName"
                  class="border-b border-default/60"
                  :class="i % 2 ? 'bg-elevated/20' : ''"
                >
                  <td class="px-3 py-2 font-mono text-xs">
                    {{ f.nodeName }}
                  </td>
                  <td class="px-3 py-2 text-xs text-muted">
                    {{ (f.roleLabels ?? []).join(', ') }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-xs">
                    {{ f.score.toFixed(6) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h3 class="mb-2 text-sm font-semibold text-highlighted">
            Top nodes (all types)
          </h3>
          <div class="overflow-x-auto rounded-lg border border-default">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-default bg-elevated/40 text-left text-muted">
                  <th class="px-3 py-2">
                    Node
                  </th>
                  <th class="px-3 py-2">
                    Type
                  </th>
                  <th class="px-3 py-2 text-right">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(n, i) in pagerank.topNodes.slice(0, 12)"
                  :key="n.nodeName"
                  class="border-b border-default/60"
                  :class="i % 2 ? 'bg-elevated/20' : ''"
                >
                  <td class="px-3 py-2 font-mono text-xs">
                    {{ n.nodeName }}
                  </td>
                  <td class="px-3 py-2 text-xs text-muted">
                    {{ n.nodeType[0] }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-xs">
                    {{ n.score.toFixed(4) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <section v-if="communities">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        BOM modules (Louvain)
      </h2>
      <p class="mb-4 text-sm text-muted">
        {{ communities.intro }}
      </p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="c in communities.communities"
          :key="c.id"
          class="rounded-xl border border-default bg-elevated/40 p-4"
        >
          <div class="mb-2 flex items-center justify-between gap-2">
            <span class="font-semibold text-highlighted">Module {{ c.id }}</span>
            <UBadge
              color="neutral"
              variant="subtle"
              size="sm"
            >
              {{ c.size.toLocaleString() }} products
            </UBadge>
          </div>
          <p
            v-if="c.commentary"
            class="mb-3 text-xs text-muted"
          >
            {{ c.commentary }}
          </p>
          <div class="flex flex-wrap gap-1">
            <UBadge
              v-for="entry in c.composition.slice(0, 5)"
              :key="entry.group"
              color="primary"
              variant="outline"
              size="sm"
            >
              {{ entry.group }}: {{ entry.count }}
            </UBadge>
          </div>
        </div>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Graph explorer
      </h2>
      <p class="mb-4 text-sm text-muted">
        The full BOM is not shipped. Explore the complete facility lane map (12 nodes) or a capped BOM neighborhood around a high-signal product.
      </p>

      <div class="mb-4 flex flex-wrap items-end gap-4">
        <div class="flex gap-2">
          <UButton
            :variant="explorerTab === 'facility' ? 'solid' : 'outline'"
            color="primary"
            size="sm"
            @click="explorerTab = 'facility'"
          >
            Facility lanes
          </UButton>
          <UButton
            :variant="explorerTab === 'bom' ? 'solid' : 'outline'"
            color="primary"
            size="sm"
            @click="explorerTab = 'bom'"
          >
            BOM neighborhood
          </UButton>
        </div>
        <div
          v-if="explorerTab === 'bom'"
          class="min-w-[240px] max-w-md flex-1"
        >
          <USelect
            v-model="selectedProductSlug"
            :items="productItems"
            placeholder="Select product"
          />
        </div>
      </div>

      <ClientOnly v-if="explorerTab === 'facility' && facilityGraph?.nodes?.length">
        <GraphView
          :nodes="facilityGraph.nodes"
          :relationships="facilityGraph.relationships"
          :colors="facilityColors"
          height="480px"
        />
        <template #fallback>
          <div class="rounded-lg border border-default bg-elevated/30 p-8 text-center text-sm text-muted">
            Loading facility graph…
          </div>
        </template>
      </ClientOnly>

      <template v-else-if="explorerTab === 'bom'">
        <p
          v-if="bomGraph?.meta"
          class="mb-3 text-xs text-muted"
        >
          Focus <strong>{{ bomGraph.meta.focusProduct }}</strong> —
          {{ bomGraph.meta.nodeCount }} nodes / {{ bomGraph.meta.relCount }} relationships
          <span v-if="bomGraph.meta.capped"> (capped for readability)</span>.
        </p>
        <div
          v-if="bomStatus === 'pending'"
          class="rounded-lg border border-default bg-elevated/30 p-8 text-center text-sm text-muted"
        >
          Loading BOM subgraph…
        </div>
        <UAlert
          v-else-if="bomError"
          color="error"
          variant="subtle"
          title="Could not load BOM subgraph"
          :description="String(bomError)"
        />
        <ClientOnly v-else-if="bomGraph?.nodes?.length">
          <GraphView
            :nodes="bomGraph.nodes"
            :relationships="bomGraph.relationships"
            :colors="bomColors"
            height="520px"
          />
          <template #fallback>
            <div class="rounded-lg border border-default bg-elevated/30 p-8 text-center text-sm text-muted">
              Loading graph view…
            </div>
          </template>
        </ClientOnly>
      </template>
    </section>
  </ProjectLayout>
</template>
