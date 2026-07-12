<script setup lang="ts">
import type { QueryResult } from '~/types/contract'

const props = defineProps<{
  query: QueryResult
}>()

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value)) return value.map(v => String(v)).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const hasRows = computed(() => props.query.rows.length > 0)

const PAGE_SIZE = 10
const page = ref(1)
const pagedRows = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return props.query.rows.slice(start, start + PAGE_SIZE)
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-start justify-between gap-4">
        <div>
          <h3 class="text-base font-semibold text-highlighted">
            {{ query.title }}
          </h3>
          <p
            v-if="query.description"
            class="mt-1 text-sm text-muted"
          >
            {{ query.description }}
          </p>
        </div>
        <UBadge
          color="neutral"
          variant="subtle"
          class="shrink-0"
        >
          {{ query.count }} {{ query.count === 1 ? 'row' : 'rows' }}
        </UBadge>
      </div>
    </template>

    <pre class="mb-4 overflow-x-auto rounded-md bg-muted p-3 text-xs leading-relaxed"><code>{{ query.cypher }}</code></pre>

    <div
      v-if="hasRows"
      class="overflow-x-auto"
    >
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-default text-left text-muted">
            <th
              v-for="col in query.columns"
              :key="col"
              class="px-3 py-2 font-medium"
            >
              {{ col }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in pagedRows"
            :key="i"
            class="border-b border-default/60"
          >
            <td
              v-for="col in query.columns"
              :key="col"
              class="px-3 py-2 align-top"
            >
              {{ formatCell(row[col]) }}
            </td>
          </tr>
        </tbody>
      </table>

      <div
        v-if="query.rows.length > PAGE_SIZE"
        class="mt-4 flex flex-col items-center justify-between gap-3 sm:flex-row"
      >
        <span class="text-xs text-dimmed">
          Showing {{ (page - 1) * PAGE_SIZE + 1 }}–{{ Math.min(page * PAGE_SIZE, query.rows.length) }}
          of {{ query.rows.length.toLocaleString() }} rows
        </span>
        <UPagination
          v-model:page="page"
          :total="query.rows.length"
          :items-per-page="PAGE_SIZE"
          :sibling-count="1"
        />
      </div>
    </div>
    <p
      v-else
      class="text-sm text-muted"
    >
      No rows returned.
    </p>
  </UCard>
</template>
