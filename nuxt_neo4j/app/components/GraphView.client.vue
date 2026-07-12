<script setup lang="ts">
import type { GraphNode, GraphRel } from '~/types/contract'

const props = withDefaults(defineProps<{
  nodes: GraphNode[]
  relationships: GraphRel[]
  colors?: Record<string, string>
  height?: string
}>(), {
  colors: undefined,
  height: '600px'
})

const DEFAULT_PALETTE = [
  '#00C16A', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#14B8A6', '#F97316', '#6366F1', '#84CC16'
]

const container = ref<HTMLElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let nvl: any = null
let resizeObserver: ResizeObserver | null = null
const renderError = ref<string | null>(null)

function labelOf(node: GraphNode): string {
  return node.labels?.[0] ?? 'Node'
}

// Stable label -> color map, honoring an explicit `colors` prop override.
const colorMap = computed<Record<string, string>>(() => {
  const labels = [...new Set(props.nodes.map(labelOf))].sort()
  const map: Record<string, string> = {}
  labels.forEach((label, i) => {
    map[label] = props.colors?.[label] ?? DEFAULT_PALETTE[i % DEFAULT_PALETTE.length]!
  })
  return map
})

const legend = computed(() => Object.entries(colorMap.value).map(([label, color]) => ({ label, color })))

function nodeSize(node: GraphNode): number {
  if (typeof node.score === 'number') return 16 + Math.min(node.score, 1) * 28
  return 22
}

function mapped() {
  const nvlNodes = props.nodes.map(n => ({
    id: n.id,
    caption: n.caption ?? n.id,
    color: colorMap.value[labelOf(n)],
    size: nodeSize(n)
  }))
  const nvlRels = props.relationships.map(r => ({
    id: r.id,
    from: r.from,
    to: r.to,
    caption: r.type
  }))
  return { nvlNodes, nvlRels }
}

async function render() {
  if (!container.value) return
  await nextTick()
  try {
    const { NVL } = await import('@neo4j-nvl/base')
    if (nvl) {
      nvl.destroy()
      nvl = null
    }
    const { nvlNodes, nvlRels } = mapped()
    nvl = new NVL(
      container.value,
      nvlNodes,
      nvlRels,
      {
        // Canvas renderer is the reliable choice for bundled apps and is the only
        // one that draws captions/arrowheads; web workers don't resolve under Vite,
        // so run layout on the main thread (graphs here are small). No telemetry.
        renderer: 'canvas',
        disableWebGL: true,
        disableWebWorkers: true,
        disableTelemetry: true,
        initialZoom: 0.75,
        layout: 'forceDirected'
      },
      {
        onLayoutDone: () => {
          if (nvl && nvlNodes.length) nvl.fit(nvlNodes.map(n => n.id))
        }
      }
    )
    renderError.value = null
  } catch (err) {
    renderError.value = err instanceof Error ? err.message : String(err)
    console.error('[GraphView] failed to render NVL graph:', err)
  }
}

onMounted(() => {
  render()
  if (container.value && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      if (nvl && props.nodes.length) nvl.fit(props.nodes.map(n => n.id))
    })
    resizeObserver.observe(container.value)
  }
})

watch(() => [props.nodes, props.relationships], render, { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (nvl) {
    nvl.destroy()
    nvl = null
  }
})
</script>

<template>
  <div class="space-y-3">
    <div
      v-if="legend.length"
      class="flex flex-wrap items-center gap-x-4 gap-y-2"
    >
      <span
        v-for="entry in legend"
        :key="entry.label"
        class="inline-flex items-center gap-1.5 text-sm text-muted"
      >
        <span
          class="size-3 rounded-full"
          :style="{ backgroundColor: entry.color }"
        />
        {{ entry.label }}
      </span>
    </div>

    <div class="relative w-full">
      <div
        ref="container"
        class="w-full rounded-lg border border-default bg-elevated/30 overflow-hidden"
        :style="{ height }"
      />
      <div
        v-if="renderError"
        class="absolute inset-0 flex items-center justify-center p-4 text-center text-sm text-error"
      >
        Graph failed to render: {{ renderError }}
      </div>
      <div
        v-else-if="!nodes.length"
        class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted"
      >
        No graph data to display.
      </div>
    </div>
  </div>
</template>
