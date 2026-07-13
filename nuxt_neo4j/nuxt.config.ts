// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@nuxt/hints',
    '@nuxt/image',
    '@nuxt/test-utils',
    '@nuxtjs/seo'
  ],

  devtools: {
    enabled: true
  },

  css: ['~/assets/css/main.css'],

  // Keep old assignment-style URLs working after the slug rename.
  routeRules: {
    '/ass1': { redirect: '/music-knowledge-graph' },
    '/ass2': { redirect: '/healthcare' },
    '/recommender': { redirect: '/movie-recommender' },
    '/finalproject': { redirect: '/supply-chain' }
  },

  compatibilityDate: '2025-01-15',

  nitro: {
    prerender: {
      crawlLinks: true,
      routes: ['/']
    }
  },

  // NVL is imported dynamically inside a .client.vue component, so it never runs on
  // the server. Let Vite pre-bundle it (and its CommonJS layout deps cytoscape +
  // cose-bilkent) via esbuild so their default exports are interop'd correctly.
  // Do NOT add it to build.transpile: that pulls it into the source graph as
  // noExternal, where Vite skips CJS->ESM interop and the import fails.
  vite: {
    optimizeDeps: {
      include: ['@neo4j-nvl/base', '@neo4j-nvl/interaction-handlers', 'cytoscape', 'cytoscape-cose-bilkent']
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})
