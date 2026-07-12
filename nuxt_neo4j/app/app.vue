<script setup>
useHead({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: 'en'
  }
})

const title = 'Neo4j Capstone Demos'
const description = 'Interactive static demos of Neo4j graph projects: music knowledge graph, movie recommendations, healthcare adverse events, and supply-chain risk.'

const navItems = [
  { label: 'Music KG', to: '/music-knowledge-graph' },
  { label: 'Recommender', to: '/movie-recommender' },
  { label: 'Healthcare', to: '/healthcare' },
  { label: 'Supply Chain', to: '/supply-chain' }
]

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description,
  twitterCard: 'summary_large_image'
})
</script>

<template>
  <UApp>
    <UHeader>
      <template #left>
        <NuxtLink
          to="/"
          aria-label="Home"
        >
          <AppLogo class="w-auto h-6 shrink-0" />
        </NuxtLink>
      </template>

      <UNavigationMenu :items="navItems" />

      <template #right>
        <UColorModeButton />
      </template>
    </UHeader>

    <UMain>
      <NuxtPage />
    </UMain>

    <USeparator icon="i-simple-icons-nuxtdotjs" />

    <UFooter>
      <template #left>
        <p class="text-sm text-muted">
          Neo4j Capstone Demos • © {{ new Date().getFullYear() }}
        </p>
      </template>

      <template #right>
        <UButton
          to="https://github.com/PeterMangoro/neo4j"
          target="_blank"
          icon="i-simple-icons-github"
          aria-label="GitHub"
          color="neutral"
          variant="ghost"
        />
      </template>
    </UFooter>
  </UApp>
</template>
