<script setup lang="ts">
import type {
  Stats,
  QueryResult,
  HealthcareCommunitiesData,
  HealthcareSimilarityData,
  CommunityIndexEntry,
  DrugIndexEntry,
  CuratedGraphData
} from '~/types/contract'

useSeoMeta({
  title: 'Healthcare Adverse Events',
  description: 'FAERS-style adverse-event graph: Cypher analytics, Jaccard patient-journey similarity, Leiden sub-phenotypes, and curated drug/community explorers — fully static, no live database.'
})

const PROJECT = 'healthcare'

const { data: stats } = await useProjectData<Stats>(PROJECT, 'stats')
const { data: queries } = await useProjectData<QueryResult[]>(PROJECT, 'queries')
const { data: similarity } = await useProjectData<HealthcareSimilarityData>(PROJECT, 'similarity')
const { data: communities } = await useProjectData<HealthcareCommunitiesData>(PROJECT, 'communities')
const { data: communityIndex } = await useProjectData<CommunityIndexEntry[]>(PROJECT, 'community_index')
const { data: drugIndex } = await useProjectData<DrugIndexEntry[]>(PROJECT, 'drug_index')

const LABEL_COLORS: Record<string, string> = {
  Case: '#3B82F6',
  Drug: '#EF4444',
  Reaction: '#F59E0B',
  Outcome: '#8B5CF6',
  AgeGroup: '#14B8A6',
  Manufacturer: '#EC4899',
  Therapy: '#64748B',
  ReportSource: '#84CC16'
}

// --- Schema SVG --------------------------------------------------------
const SCHEMA_R = 34
const schemaPos: Record<string, { x: number, y: number }> = {
  Manufacturer: { x: 90, y: 70 },
  Case: { x: 320, y: 200 },
  Drug: { x: 560, y: 70 },
  Reaction: { x: 560, y: 200 },
  Outcome: { x: 560, y: 330 },
  AgeGroup: { x: 90, y: 330 }
}
const schemaRels = [
  { id: 'REGISTERED', from: 'Manufacturer', to: 'Case', type: 'REGISTERED' },
  { id: 'IS_PRIMARY_SUSPECT', from: 'Case', to: 'Drug', type: 'IS_PRIMARY_SUSPECT' },
  { id: 'HAS_REACTION', from: 'Case', to: 'Reaction', type: 'HAS_REACTION' },
  { id: 'RESULTED_IN', from: 'Case', to: 'Outcome', type: 'RESULTED_IN' },
  { id: 'FALLS_UNDER', from: 'Case', to: 'AgeGroup', type: 'FALLS_UNDER' }
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

// Split queries: EDA vs analytics
const edaQueries = computed(() =>
  (queries.value ?? []).filter(q => q.id.startsWith('eda-'))
)
const analyticsQueries = computed(() =>
  (queries.value ?? []).filter(q => q.id.startsWith('analytics-'))
)

// --- Explorer ----------------------------------------------------------
type ExplorerTab = 'community' | 'drug'
const explorerTab = ref<ExplorerTab>('community')

const communityItems = computed(() =>
  (communityIndex.value ?? []).map(c => ({
    label: `C${c.id} · ${c.size} cases · ${c.label}`,
    value: String(c.id)
  }))
)
const drugItems = computed(() =>
  (drugIndex.value ?? []).map(d => ({
    label: d.source === 'severe'
      ? `${d.name} (${d.severeCases} severe)`
      : `${d.name} (PFIZER · ${d.caseCount} cases)`,
    value: d.slug
  }))
)

const selectedCommunityId = ref<string>('')
const selectedDrugSlug = ref<string>('')

watch(communityIndex, (idx) => {
  if (idx?.length && !selectedCommunityId.value) {
    selectedCommunityId.value = String(idx[0]!.id)
  }
}, { immediate: true })

watch(drugIndex, (idx) => {
  if (idx?.length && !selectedDrugSlug.value) {
    selectedDrugSlug.value = idx[0]!.slug
  }
}, { immediate: true })

const graphFile = computed(() => {
  if (explorerTab.value === 'community') {
    const id = selectedCommunityId.value
    return id ? `graph_community_${id}` : null
  }
  const slug = selectedDrugSlug.value
  return slug ? `graph_drug_${slug}` : null
})

const {
  data: explorerGraph,
  status: explorerStatus,
  error: explorerError
} = await useAsyncData(
  'healthcare-explorer-graph',
  async () => {
    const file = graphFile.value
    if (!file) return null as CuratedGraphData | null
    return await $fetch<CuratedGraphData>(`/data/${PROJECT}/${file}.json`)
  },
  { watch: [graphFile], server: false }
)

function selectCommunity(id: number) {
  explorerTab.value = 'community'
  selectedCommunityId.value = String(id)
}

const explorerMeta = computed(() => explorerGraph.value?.meta ?? null)
</script>

<template>
  <ProjectLayout
    title="Healthcare Adverse Events (FAERS)"
    subtitle="Cypher EDA and analytics on an FDA adverse-event reporting graph, plus GDS Jaccard patient-journey similarity and Leiden sub-phenotypes — curated subgraphs only; no live database at runtime."
    dataset="Source: healthcare-analytics-50.dump · 11,381 nodes · 61,453 relationships · offline GDS precompute"
  >
    <!-- 1. Highlights + counts -->
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
        Cases sit at the center: manufacturers register them, drugs appear as suspects,
        reactions and outcomes hang off each case, and age groups provide demographics.
        (Therapy / ReportSource exist in the dump but are omitted from this schema sketch.)
      </p>
      <div class="rounded-lg border border-default bg-elevated/30 p-4">
        <svg
          viewBox="0 0 660 400"
          class="h-auto w-full text-muted"
          role="img"
          aria-label="FAERS schema: Manufacturer REGISTERED Case; Case links to Drug, Reaction, Outcome, AgeGroup."
        >
          <defs>
            <marker
              id="hc-schema-arrow"
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
              marker-end="url(#hc-schema-arrow)"
            />
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
                font-size="11"
                font-weight="700"
                fill="#ffffff"
              >{{ n.label }}</text>
            </g>
          </g>
        </svg>
      </div>
    </section>

    <!-- 3. EDA -->
    <section v-if="edaQueries.length">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Schema discovery (EDA)
      </h2>
      <p class="mb-4 text-sm text-muted">
        Frozen Cypher from the notebook’s first pass: labels, relationship types, genders, reactions, outcomes.
      </p>
      <div class="space-y-4">
        <QueryResult
          v-for="q in edaQueries"
          :key="q.id"
          :query="q"
        />
      </div>
    </section>

    <!-- 4. Analytics -->
    <section v-if="analyticsQueries.length">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Drug-safety analytics
      </h2>
      <p class="mb-4 text-sm text-muted">
        Deeper questions: top reactions, drugs tied to severe outcomes, manufacturer footprint, and a PFIZER drill-down.
      </p>
      <div class="space-y-4">
        <QueryResult
          v-for="q in analyticsQueries"
          :key="q.id"
          :query="q"
        />
      </div>
    </section>

    <!-- 5. Similarity -->
    <section v-if="similarity">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Similar patient journeys
      </h2>
      <p class="mb-4 text-sm text-muted">
        GDS <code class="text-xs">nodeSimilarity</code> on an undirected Case–Drug–Reaction projection
        (Jaccard, cutoff {{ similarity.cutoff }}). Top pairs share reactions and suspect drugs.
      </p>
      <div class="overflow-x-auto rounded-lg border border-default">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-default bg-elevated/40 text-left text-muted">
              <th class="px-3 py-2 font-medium">
                Case A
              </th>
              <th class="px-3 py-2 font-medium">
                Case B
              </th>
              <th class="px-3 py-2 font-medium">
                Similarity
              </th>
              <th class="px-3 py-2 font-medium">
                Shared reactions
              </th>
              <th class="px-3 py-2 font-medium">
                Shared drugs
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(p, i) in similarity.pairs"
              :key="`${p.case1}-${p.case2}`"
              class="border-b border-default/60"
              :class="i % 2 ? 'bg-elevated/20' : ''"
            >
              <td class="px-3 py-2 font-mono text-xs">
                {{ p.case1 }}
              </td>
              <td class="px-3 py-2 font-mono text-xs">
                {{ p.case2 }}
              </td>
              <td class="px-3 py-2">
                {{ p.similarity.toFixed(2) }}
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-1">
                  <UBadge
                    v-for="r in p.sampleReactions"
                    :key="r"
                    color="warning"
                    variant="subtle"
                    size="sm"
                  >
                    {{ r }}
                  </UBadge>
                </div>
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-1">
                  <UBadge
                    v-for="d in p.sharedDrugs"
                    :key="d"
                    color="error"
                    variant="subtle"
                    size="sm"
                  >
                    {{ d }}
                  </UBadge>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 6. Communities -->
    <section v-if="communities">
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Patient sub-phenotypes (Leiden)
      </h2>
      <p class="mb-4 text-sm text-muted">
        {{ communities.intro }}
        Click a card to open that community’s curated ego-network in the explorer below.
      </p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <button
          v-for="c in communities.communities"
          :key="c.id"
          type="button"
          class="rounded-xl border border-default bg-elevated/40 p-4 text-left transition-colors hover:border-primary hover:bg-elevated"
          :class="explorerTab === 'community' && selectedCommunityId === String(c.id) ? 'border-primary ring-1 ring-primary/40' : ''"
          @click="selectCommunity(c.id)"
        >
          <div class="mb-2 flex items-center justify-between gap-2">
            <span class="font-semibold text-highlighted">Community {{ c.id }}</span>
            <UBadge
              color="neutral"
              variant="subtle"
              size="sm"
            >
              {{ c.size }} cases
            </UBadge>
          </div>
          <p
            v-if="c.commentary"
            class="mb-3 text-xs text-muted"
          >
            {{ c.commentary }}
          </p>
          <div class="space-y-2 text-xs">
            <div v-if="c.topGenders.length">
              <span class="text-muted">Gender:</span>
              {{ c.topGenders.join(', ') }}
            </div>
            <div v-if="c.topAgeGroups.length">
              <span class="text-muted">Age:</span>
              {{ c.topAgeGroups.join(', ') }}
            </div>
            <div class="flex flex-wrap gap-1 pt-1">
              <UBadge
                v-for="r in c.topReactions.slice(0, 4)"
                :key="r"
                color="warning"
                variant="outline"
                size="sm"
              >
                {{ r }}
              </UBadge>
            </div>
          </div>
        </button>
      </div>
    </section>

    <!-- 7. Graph explorer -->
    <section>
      <h2 class="mb-2 text-xl font-semibold text-highlighted">
        Graph explorer
      </h2>
      <p class="mb-4 text-sm text-muted">
        The full graph (~11k nodes) is too dense to ship. Explore curated neighborhoods:
        a sample of cases from a Leiden community, or cases around a high-signal drug.
      </p>

      <div class="mb-4 flex flex-wrap items-end gap-4">
        <div class="flex gap-2">
          <UButton
            :variant="explorerTab === 'community' ? 'solid' : 'outline'"
            color="primary"
            size="sm"
            @click="explorerTab = 'community'"
          >
            By community
          </UButton>
          <UButton
            :variant="explorerTab === 'drug' ? 'solid' : 'outline'"
            color="primary"
            size="sm"
            @click="explorerTab = 'drug'"
          >
            By drug
          </UButton>
        </div>

        <div
          v-if="explorerTab === 'community'"
          class="min-w-[240px] max-w-md flex-1"
        >
          <USelect
            v-model="selectedCommunityId"
            :items="communityItems"
            placeholder="Select community"
          />
        </div>
        <div
          v-else
          class="min-w-[240px] max-w-md flex-1"
        >
          <USelect
            v-model="selectedDrugSlug"
            :items="drugItems"
            placeholder="Select drug"
          />
        </div>
      </div>

      <p
        v-if="explorerMeta"
        class="mb-3 text-xs text-muted"
      >
        Showing {{ explorerMeta.nodeCount }} nodes / {{ explorerMeta.relCount }} relationships
        from {{ explorerMeta.caseCount }} seed cases
        <span v-if="explorerMeta.capped"> (capped for readability)</span>
        <span v-if="explorerMeta.focusDrug"> · focus: {{ explorerMeta.focusDrug }}</span>.
      </p>

      <div
        v-if="explorerStatus === 'pending'"
        class="rounded-lg border border-default bg-elevated/30 p-8 text-center text-sm text-muted"
      >
        Loading subgraph…
      </div>
      <UAlert
        v-else-if="explorerError"
        color="error"
        variant="subtle"
        title="Could not load subgraph"
        :description="String(explorerError)"
      />
      <ClientOnly v-else-if="explorerGraph?.nodes?.length">
        <GraphView
          :nodes="explorerGraph.nodes"
          :relationships="explorerGraph.relationships"
          :colors="LABEL_COLORS"
          height="520px"
        />
        <template #fallback>
          <div class="rounded-lg border border-default bg-elevated/30 p-8 text-center text-sm text-muted">
            Loading graph view…
          </div>
        </template>
      </ClientOnly>
      <div
        v-else
        class="rounded-lg border border-dashed border-default p-8 text-center text-sm text-muted"
      >
        Pick a community or drug to load a curated neighborhood.
      </div>

      <!-- Compact node legend for current graph -->
      <ul
        v-if="explorerGraph?.nodes?.length"
        class="mt-3 flex flex-wrap gap-3 text-xs text-muted"
      >
        <li
          v-for="label in [...new Set(explorerGraph.nodes.map(n => n.labels?.[0] ?? 'Node'))]"
          :key="label"
          class="inline-flex items-center gap-1.5"
        >
          <span
            class="size-2.5 rounded-full"
            :style="{ backgroundColor: LABEL_COLORS[label!] ?? '#64748B' }"
          />
          {{ label }}
        </li>
      </ul>
    </section>
  </ProjectLayout>
</template>
