<script setup lang="ts">
import type { Highlight } from '~/types/contract'

defineProps<{
  highlights: Highlight[]
}>()
</script>

<template>
  <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
    <UCard
      v-for="(item, i) in highlights"
      :key="i"
      :ui="{ body: 'p-4 sm:p-4' }"
    >
      <p class="text-2xl font-bold text-highlighted tabular-nums">
        {{ item.value }}
      </p>
      <p class="mt-1 text-sm text-muted">
        {{ item.label }}
      </p>
    </UCard>
  </div>
</template>
