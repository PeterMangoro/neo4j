<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
  dataset?: string
}>()
</script>

<template>
  <UContainer class="py-8 sm:py-12">
    <header class="mb-8 max-w-3xl">
      <div class="mb-3 flex items-center gap-2">
        <UBadge
          color="neutral"
          variant="subtle"
          icon="i-lucide-database"
        >
          Static demo · precomputed, no live database
        </UBadge>
      </div>
      <h1 class="text-3xl font-bold tracking-tight text-highlighted sm:text-4xl">
        {{ title }}
      </h1>
      <p
        v-if="subtitle"
        class="mt-3 text-lg text-muted"
      >
        {{ subtitle }}
      </p>
      <p
        v-if="dataset"
        class="mt-2 text-sm text-dimmed"
      >
        {{ dataset }}
      </p>
    </header>

    <div class="space-y-10">
      <slot />
    </div>
  </UContainer>
</template>
