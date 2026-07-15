<script setup lang="ts">
useSeoMeta({
  title: 'Neo4j Capstone Demos',
  description: 'Interactive demos of Neo4j graph projects: music knowledge graph, movie recommendations, healthcare adverse events, and supply-chain risk.'
})

const projects = [
  {
    to: '/music-knowledge-graph',
    icon: 'i-lucide-disc-3',
    title: 'Music Knowledge Graph',
    status: 'Live',
    statusColor: 'success' as const,
    summary: 'Chinook music catalog as a property graph: artists, albums, tracks, genres, and composers with graded Cypher queries and a client-side explorer.',
    highlights: ['5,007 nodes', '13,381 relationships', 'Interactive filters']
  },
  {
    to: '/movie-recommender',
    icon: 'i-lucide-clapperboard',
    title: 'Movie Recommender',
    status: 'Live',
    statusColor: 'success' as const,
    summary: 'Hybrid movie recommendations built with Neo4j Graph Data Science: Jaccard similarity, FastRP embeddings, and Louvain communities.',
    highlights: ['GDS similarity', 'Embedding neighbors', 'Community clusters']
  },
  {
    to: '/healthcare',
    icon: 'i-lucide-heart-pulse',
    title: 'Healthcare Adverse Events',
    status: 'Live',
    statusColor: 'success' as const,
    summary: 'FAERS-style adverse-event reporting graph with Cypher analytics and GDS for drug–reaction patterns and patient safety insights.',
    highlights: ['11,381 nodes', 'Leiden phenotypes', 'Drug neighborhoods']
  },
  {
    to: '/supply-chain',
    icon: 'i-lucide-network',
    title: 'Supply-Chain Risk',
    status: 'Live',
    statusColor: 'success' as const,
    summary: 'Multi-tier automotive production network analysis: PageRank influence, community structure, and BOM exploration for risk spotting.',
    highlights: ['28k products', 'PageRank chokepoints', 'BOM explorer']
  }
]
</script>

<template>
  <div>
    <UPageSection
      title="Projects"
      description="Interactive demos of Neo4j graph projects: music knowledge graph, movie recommendations, healthcare adverse events, and supply-chain risk."
    >
      <div class="grid gap-4 sm:grid-cols-2">
        <NuxtLink
          v-for="project in projects"
          :key="project.to"
          :to="project.to"
          class="group flex flex-col gap-4 rounded-xl border border-default bg-elevated/40 p-5 transition-colors hover:border-primary hover:bg-elevated"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <UIcon
                :name="project.icon"
                class="size-5"
              />
            </div>
            <UBadge
              :color="project.statusColor"
              variant="subtle"
              size="sm"
            >
              {{ project.status }}
            </UBadge>
          </div>

          <div class="space-y-2">
            <h3 class="text-lg font-semibold text-highlighted group-hover:text-primary">
              {{ project.title }}
            </h3>
            <p class="text-sm text-muted">
              {{ project.summary }}
            </p>
          </div>

          <ul class="mt-auto flex flex-wrap gap-2">
            <li
              v-for="item in project.highlights"
              :key="item"
            >
              <UBadge
                color="neutral"
                variant="outline"
                size="sm"
              >
                {{ item }}
              </UBadge>
            </li>
          </ul>

          <span class="inline-flex items-center gap-1 text-sm font-medium text-primary">
            Open demo
            <UIcon
              name="i-lucide-arrow-right"
              class="size-4 transition-transform group-hover:translate-x-0.5"
            />
          </span>
        </NuxtLink>
      </div>
    </UPageSection>
  </div>
</template>
