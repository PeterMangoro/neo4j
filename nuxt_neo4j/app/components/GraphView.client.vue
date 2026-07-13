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
const root = ref<HTMLElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let nvl: any = null
let resizeObserver: ResizeObserver | null = null
let visibilityObserver: IntersectionObserver | null = null
const renderError = ref<string | null>(null)
const isVisible = ref(false)
let renderGeneration = 0
let healAttempts = 0
let pendingTimer: ReturnType<typeof setTimeout> | null = null

function afterLayout(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  })
}

function labelOf(node: GraphNode): string {
  return node.labels?.[0] ?? 'Node'
}

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
  // Deduplicate undirected pairs so NVL doesn't choke on A→B + B→A duplicates.
  const seen = new Set<string>()
  const nvlRels: { id: string, from: string, to: string, caption: string }[] = []
  for (const r of props.relationships) {
    const a = r.from < r.to ? r.from : r.to
    const b = r.from < r.to ? r.to : r.from
    const key = `${r.type}:${a}:${b}`
    if (seen.has(key)) continue
    seen.add(key)
    nvlRels.push({
      id: r.id,
      from: r.from,
      to: r.to,
      caption: r.type
    })
  }
  return { nvlNodes, nvlRels }
}

function canvasLooksEmpty(): boolean {
  if (!container.value) return true
  const canvas = container.value.querySelector('canvas')
  if (!canvas) return true
  // Zero-size canvas = not actually painted yet
  return canvas.width < 2 || canvas.height < 2
}

async function render() {
  if (!container.value || !isVisible.value) return

  const gen = ++renderGeneration

  if (!props.nodes.length) {
    if (nvl) {
      nvl.destroy()
      nvl = null
    }
    renderError.value = null
    return
  }

  await nextTick()
  await afterLayout()
  if (gen !== renderGeneration || !container.value) return

  // Need a non-zero box before constructing NVL
  const rect = container.value.getBoundingClientRect()
  if (rect.width < 2 || rect.height < 2) {
    scheduleRetry(gen, 50)
    return
  }

  try {
    const { NVL } = await import('@neo4j-nvl/base')
    if (gen !== renderGeneration || !container.value) return

    if (nvl) {
      nvl.destroy()
      nvl = null
    }

    // Clear any leftover canvases from a half-initialized instance
    container.value.replaceChildren()

    const { nvlNodes, nvlRels } = mapped()
    nvl = new NVL(
      container.value,
      nvlNodes,
      nvlRels,
      {
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

    // If NVL created a zero-size / missing canvas, retry shortly after layout settles.
    scheduleRetry(gen, 120)
  } catch (err) {
    renderError.value = err instanceof Error ? err.message : String(err)
    console.error('[GraphView] failed to render NVL graph:', err)
  }
}

function scheduleRetry(gen: number, delayMs: number) {
  if (healAttempts >= 4) return
  if (pendingTimer) clearTimeout(pendingTimer)
  pendingTimer = setTimeout(() => {
    pendingTimer = null
    if (gen !== renderGeneration) return
    if (!isVisible.value || !props.nodes.length) return
    if (canvasLooksEmpty()) {
      healAttempts++
      render()
    }
  }, delayMs)
}

function requestRender() {
  healAttempts = 0
  render()
}

onMounted(() => {
  if (root.value && 'IntersectionObserver' in window) {
    visibilityObserver = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        const nowVisible = !!entry?.isIntersecting
        if (nowVisible && !isVisible.value) {
          isVisible.value = true
          requestRender()
        } else if (!nowVisible) {
          isVisible.value = false
        }
      },
      { root: null, threshold: 0.05, rootMargin: '80px' }
    )
    visibilityObserver.observe(root.value)
  } else {
    // Fallback when IntersectionObserver is unavailable
    isVisible.value = true
    requestRender()
  }

  if (container.value && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      if (!isVisible.value || !nvl || !props.nodes.length) return
      if (canvasLooksEmpty()) {
        requestRender()
        return
      }
      nvl.fit(props.nodes.map(n => n.id))
    })
    resizeObserver.observe(container.value)
  }
})

watch(
  () => [props.nodes, props.relationships] as const,
  () => {
    requestRender()
  },
  { deep: true, flush: 'post' }
)

watch(
  () => props.colors,
  () => {
    requestRender()
  },
  { deep: true, flush: 'post' }
)

onBeforeUnmount(() => {
  if (pendingTimer) clearTimeout(pendingTimer)
  visibilityObserver?.disconnect()
  visibilityObserver = null
  resizeObserver?.disconnect()
  resizeObserver = null
  if (nvl) {
    nvl.destroy()
    nvl = null
  }
})
</script>

<template>
  <div
    ref="root"
    class="space-y-3"
  >
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
