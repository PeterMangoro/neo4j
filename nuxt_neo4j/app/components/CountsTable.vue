<script setup lang="ts">
import type { CountEntry, RelCountEntry } from '~/types/contract'

defineProps<{
  nodeCounts: CountEntry[]
  relCounts: RelCountEntry[]
}>()
</script>

<template>
  <div class="grid gap-6 md:grid-cols-2">
    <div>
      <h4 class="mb-2 text-sm font-semibold text-highlighted">
        Nodes by label
      </h4>
      <table class="w-full text-sm">
        <tbody>
          <tr
            v-for="entry in nodeCounts"
            :key="entry.label"
            class="border-b border-default/60"
          >
            <td class="px-3 py-1.5">
              {{ entry.label }}
            </td>
            <td class="px-3 py-1.5 text-right tabular-nums text-muted">
              {{ entry.count.toLocaleString() }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div>
      <h4 class="mb-2 text-sm font-semibold text-highlighted">
        Relationships by type
      </h4>
      <table class="w-full text-sm">
        <tbody>
          <tr
            v-for="entry in relCounts"
            :key="entry.type"
            class="border-b border-default/60"
          >
            <td class="px-3 py-1.5">
              {{ entry.type }}
            </td>
            <td class="px-3 py-1.5 text-right tabular-nums text-muted">
              {{ entry.count.toLocaleString() }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
