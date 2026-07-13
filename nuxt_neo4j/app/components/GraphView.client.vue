<script setup lang="ts">
import type { GraphNode, GraphRel } from '~/types/contract'

type PositionSnapshot = { id: string, x: number, y: number }

/** Session-scoped layout cache so remounts keep user rearrangements. */
const positionCache = new Map<string, PositionSnapshot[]>()

const props = withDefaults(defineProps<{
  nodes: GraphNode[]
  relationships: GraphRel[]
  colors?: Record<string, string>
  height?: string
  /** Master switch — false keeps the previous static (non-interactive) behavior. */
  interactive?: boolean
  zoom?: boolean
  pan?: boolean
  dragNodes?: boolean
  select?: boolean
  persistPositions?: boolean
  /** Explicit cache key; defaults to a fingerprint of node/rel ids. */
  persistKey?: string
}>(), {
  colors: undefined,
  height: '600px',
  interactive: true,
  zoom: true,
  pan: true,
  dragNodes: true,
  select: true,
  persistPositions: true,
  persistKey: undefined
})

const emit = defineEmits<{
  select: [node: GraphNode | null]
}>()

const DEFAULT_PALETTE = [
  '#00C16A', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#14B8A6', '#F97316', '#6366F1', '#84CC16'
]

const container = ref<HTMLElement | null>(null)
const root = ref<HTMLElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let nvl: any = null
let interactions: { destroy: () => void }[] = []
let resizeObserver: ResizeObserver | null = null
let visibilityObserver: IntersectionObserver | null = null
const renderError = ref<string | null>(null)
const isVisible = ref(false)
let renderGeneration = 0
let healAttempts = 0
let pendingTimer: ReturnType<typeof setTimeout> | null = null

/** Mobile touch: NVL Zoom/Pan/Drag only listen to wheel/mouse. */
type TouchGesture
  = {
    mode: 'pinch'
    startDist: number
    startZoom: number
    startPan: { x: number, y: number }
  }
  | {
    mode: 'pan'
    startX: number
    startY: number
    startPan: { x: number, y: number }
  }
  | {
    mode: 'dragNode'
    id: string
    startX: number
    startY: number
    nodeX: number
    nodeY: number
  }
let touchGesture: TouchGesture | null = null
let touchListenersAttached = false

const selectedNodeId = ref<string | null>(null)

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  return props.nodes.find(n => n.id === selectedNodeId.value) ?? null
})

const showHint = computed(() =>
  props.interactive && (props.zoom || props.pan || props.dragNodes || props.select)
)

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

function graphFingerprint(): string {
  if (props.persistKey) return props.persistKey
  const nodeIds = props.nodes.map(n => n.id).sort().join('|')
  const relIds = props.relationships.map(r => r.id).sort().join('|')
  return `${nodeIds}::${relIds}`
}

function mapped(saved: PositionSnapshot[] | null) {
  const posById = saved ? new Map(saved.map(p => [p.id, p])) : null
  const nvlNodes = props.nodes.map((n) => {
    const base: {
      id: string
      caption: string
      color: string | undefined
      size: number
      x?: number
      y?: number
    } = {
      id: n.id,
      caption: n.caption ?? n.id,
      color: colorMap.value[labelOf(n)],
      size: nodeSize(n)
    }
    const pos = posById?.get(n.id)
    if (pos) {
      base.x = pos.x
      base.y = pos.y
    }
    return base
  })
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
  return canvas.width < 2 || canvas.height < 2
}

function destroyInteractions() {
  for (const h of interactions) {
    try {
      h.destroy()
    } catch {
      // ignore teardown errors from already-destroyed handlers
    }
  }
  interactions = []
  detachTouchGestures()
}

function destroyNvl() {
  destroyInteractions()
  if (nvl) {
    try {
      nvl.destroy()
    } catch {
      // ignore
    }
    nvl = null
  }
}

function touchDistance(a: Touch, b: Touch): number {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
}

function touchDelta(clientX: number, clientY: number, startX: number, startY: number) {
  const zoom = typeof nvl?.getScale === 'function' ? nvl.getScale() : 1
  const dpr = window.devicePixelRatio || 1
  return {
    dx: ((clientX - startX) / zoom) * dpr,
    dy: ((clientY - startY) / zoom) * dpr
  }
}

function hitNodeAt(clientX: number, clientY: number): {
  id: string
  x: number
  y: number
} | null {
  if (!nvl) return null
  try {
    const hits = nvl.getHits(
      { clientX, clientY } as MouseEvent,
      ['node'],
      { hitNodeMarginWidth: 24 }
    )
    const nodes = hits?.nvlTargets?.nodes ?? []
    const hit = nodes.find((n: { insideNode?: boolean }) => n.insideNode) ?? nodes[0]
    if (!hit?.data?.id) return null
    const coords = hit.targetCoordinates
    if (coords && typeof coords.x === 'number' && typeof coords.y === 'number') {
      return { id: String(hit.data.id), x: coords.x, y: coords.y }
    }
    const pos = (nvl.getNodePositions() as { id: string, x: number, y: number }[])
      .find(p => p.id === hit.data.id)
    if (!pos) return null
    return { id: String(hit.data.id), x: pos.x, y: pos.y }
  } catch {
    return null
  }
}

function onTouchStart(e: TouchEvent) {
  if (!nvl || !props.interactive) return
  if (e.touches.length === 2 && props.zoom) {
    e.preventDefault()
    const t0 = e.touches[0]!
    const t1 = e.touches[1]!
    touchGesture = {
      mode: 'pinch',
      startDist: Math.max(touchDistance(t0, t1), 1),
      startZoom: typeof nvl.getScale === 'function' ? nvl.getScale() : 1,
      startPan: nvl.getPan()
    }
    return
  }
  if (e.touches.length !== 1) return
  const t = e.touches[0]!

  if (props.dragNodes) {
    const hit = hitNodeAt(t.clientX, t.clientY)
    if (hit) {
      e.preventDefault()
      touchGesture = {
        mode: 'dragNode',
        id: hit.id,
        startX: t.clientX,
        startY: t.clientY,
        nodeX: hit.x,
        nodeY: hit.y
      }
      return
    }
  }

  if (props.pan) {
    e.preventDefault()
    touchGesture = {
      mode: 'pan',
      startX: t.clientX,
      startY: t.clientY,
      startPan: nvl.getPan()
    }
  }
}

function onTouchMove(e: TouchEvent) {
  if (!nvl || !touchGesture) return

  if (touchGesture.mode === 'pinch' && e.touches.length === 2 && props.zoom) {
    e.preventDefault()
    const dist = Math.max(touchDistance(e.touches[0]!, e.touches[1]!), 1)
    const ratio = dist / touchGesture.startDist
    const limits = typeof nvl.getZoomLimits === 'function'
      ? nvl.getZoomLimits()
      : { minZoom: 0.05, maxZoom: 10 }
    const nextZoom = Math.min(
      limits.maxZoom,
      Math.max(limits.minZoom, touchGesture.startZoom * ratio)
    )
    const zoom = touchGesture.startZoom
    const { x, y } = touchGesture.startPan
    const el = container.value
    if (!el) return
    const rect = el.getBoundingClientRect()
    const midX = ((e.touches[0]!.clientX + e.touches[1]!.clientX) / 2) - rect.left
    const midY = ((e.touches[0]!.clientY + e.touches[1]!.clientY) / 2) - rect.top
    const panX = x + (midX / zoom - midX / nextZoom)
    const panY = y + (midY / zoom - midY / nextZoom)
    nvl.setZoomAndPan(nextZoom, panX, panY)
    return
  }

  if (touchGesture.mode === 'dragNode' && e.touches.length === 1 && props.dragNodes) {
    e.preventDefault()
    const t = e.touches[0]!
    const { dx, dy } = touchDelta(t.clientX, t.clientY, touchGesture.startX, touchGesture.startY)
    nvl.setNodePositions(
      [{
        id: touchGesture.id,
        x: touchGesture.nodeX + dx,
        y: touchGesture.nodeY + dy,
        pinned: true
      }],
      true
    )
    return
  }

  if (touchGesture.mode === 'pan' && e.touches.length === 1 && props.pan) {
    e.preventDefault()
    const t = e.touches[0]!
    const { dx, dy } = touchDelta(t.clientX, t.clientY, touchGesture.startX, touchGesture.startY)
    // Match NVL PanInteraction: pan moves opposite to finger so content follows the drag.
    nvl.setPan(touchGesture.startPan.x - dx, touchGesture.startPan.y - dy)
  }
}

function onTouchEnd(e: TouchEvent) {
  if (touchGesture?.mode === 'dragNode' && e.touches.length === 0) {
    if (nvl && typeof nvl.pinNode === 'function') {
      try {
        nvl.pinNode(touchGesture.id)
      } catch {
        // ignore
      }
    }
    savePositions()
  }
  if (e.touches.length < 2 && touchGesture?.mode === 'pinch') {
    touchGesture = null
  }
  if (e.touches.length === 0) {
    touchGesture = null
  }
}

function attachTouchGestures() {
  const el = container.value
  if (!el || touchListenersAttached || !props.interactive) return
  if (!props.zoom && !props.pan && !props.dragNodes) return
  el.addEventListener('touchstart', onTouchStart, { passive: false })
  el.addEventListener('touchmove', onTouchMove, { passive: false })
  el.addEventListener('touchend', onTouchEnd)
  el.addEventListener('touchcancel', onTouchEnd)
  touchListenersAttached = true
}

function detachTouchGestures() {
  const el = container.value
  touchGesture = null
  if (!el || !touchListenersAttached) return
  el.removeEventListener('touchstart', onTouchStart)
  el.removeEventListener('touchmove', onTouchMove)
  el.removeEventListener('touchend', onTouchEnd)
  el.removeEventListener('touchcancel', onTouchEnd)
  touchListenersAttached = false
}

function nudgeZoom(factor: number) {
  if (!nvl || !props.zoom) return
  const zoom = typeof nvl.getScale === 'function' ? nvl.getScale() : 1
  const pan = nvl.getPan()
  const limits = typeof nvl.getZoomLimits === 'function'
    ? nvl.getZoomLimits()
    : { minZoom: 0.05, maxZoom: 10 }
  const next = Math.min(limits.maxZoom, Math.max(limits.minZoom, zoom * factor))
  const el = container.value
  if (!el) {
    nvl.setZoom(next)
    return
  }
  const rect = el.getBoundingClientRect()
  const midX = rect.width / 2
  const midY = rect.height / 2
  const panX = pan.x + (midX / zoom - midX / next)
  const panY = pan.y + (midY / zoom - midY / next)
  nvl.setZoomAndPan(next, panX, panY)
}

function fitGraph() {
  if (!nvl || !props.nodes.length) return
  nvl.fit(props.nodes.map(n => n.id))
}

function clearSelection() {
  selectedNodeId.value = null
  emit('select', null)
  if (nvl && typeof nvl.updateElementsInGraph === 'function') {
    // Clear selected flags if NVL still has the graph.
    try {
      const ids = props.nodes.map(n => ({ id: n.id, selected: false }))
      nvl.updateElementsInGraph(ids, [])
    } catch {
      // ignore
    }
  }
}

function selectNode(nodeId: string | null) {
  if (!props.select) return
  selectedNodeId.value = nodeId
  const graphNode = nodeId ? props.nodes.find(n => n.id === nodeId) ?? null : null
  emit('select', graphNode)
}

function savePositions() {
  if (!props.persistPositions || !nvl) return
  try {
    const positions = nvl.getNodePositions() as PositionSnapshot[]
    if (!positions?.length) return
    positionCache.set(
      graphFingerprint(),
      positions.map(p => ({ id: p.id, x: p.x, y: p.y }))
    )
  } catch (err) {
    console.warn('[GraphView] failed to snapshot positions:', err)
  }
}

async function attachInteractions() {
  if (!nvl || !props.interactive) return

  const {
    ZoomInteraction,
    PanInteraction,
    DragNodeInteraction,
    ClickInteraction,
    HoverInteraction
  } = await import('@neo4j-nvl/interaction-handlers')

  if (props.zoom) {
    interactions.push(new ZoomInteraction(nvl))
  }
  if (props.pan) {
    interactions.push(new PanInteraction(nvl))
  }
  if (props.dragNodes) {
    const drag = new DragNodeInteraction(nvl)
    drag.updateCallback('onDragEnd', (...args: unknown[]) => {
      const nodes = (args[0] ?? []) as { id: string }[]
      savePositions()
      // Pin dragged nodes so force layout doesn't spring them back.
      if (nvl && typeof nvl.pinNode === 'function') {
        for (const node of nodes) {
          try {
            nvl.pinNode(node.id)
          } catch {
            // ignore
          }
        }
      }
    })
    interactions.push(drag)
  }
  if (props.select) {
    const click = new ClickInteraction(nvl, { selectOnClick: true })
    click.updateCallback('onNodeClick', (...args: unknown[]) => {
      const node = args[0] as { id: string }
      selectNode(node.id)
    })
    click.updateCallback('onCanvasClick', () => {
      clearSelection()
    })
    interactions.push(click)

    const hover = new HoverInteraction(nvl, { drawShadowOnHover: true })
    interactions.push(hover)
  }
}

async function render() {
  if (!container.value || !isVisible.value) return

  const gen = ++renderGeneration

  if (!props.nodes.length) {
    destroyNvl()
    renderError.value = null
    selectedNodeId.value = null
    return
  }

  await nextTick()
  await afterLayout()
  if (gen !== renderGeneration || !container.value) return

  const rect = container.value.getBoundingClientRect()
  if (rect.width < 2 || rect.height < 2) {
    scheduleRetry(gen, 50)
    return
  }

  try {
    const { NVL } = await import('@neo4j-nvl/base')
    if (gen !== renderGeneration || !container.value) return

    destroyNvl()
    container.value.replaceChildren()

    const saved = props.persistPositions
      ? (positionCache.get(graphFingerprint()) ?? null)
      : null
    const hasSaved = !!saved?.length
    const { nvlNodes, nvlRels } = mapped(saved)

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
        layout: hasSaved ? 'free' : 'forceDirected'
      },
      {
        onLayoutDone: () => {
          if (!nvl || !nvlNodes.length) return
          if (hasSaved) {
            nvl.setNodePositions(
              saved!.map(p => ({ id: p.id, x: p.x, y: p.y })),
              false
            )
          }
          nvl.fit(nvlNodes.map(n => n.id as string))
        }
      }
    )

    await attachInteractions()
    attachTouchGestures()
    if (gen !== renderGeneration) return

    renderError.value = null
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

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && selectedNodeId.value) {
    clearSelection()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)

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
    selectedNodeId.value = null
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

watch(
  () => [
    props.interactive,
    props.zoom,
    props.pan,
    props.dragNodes,
    props.select,
    props.persistPositions,
    props.persistKey
  ] as const,
  () => {
    requestRender()
  }
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (pendingTimer) clearTimeout(pendingTimer)
  visibilityObserver?.disconnect()
  visibilityObserver = null
  resizeObserver?.disconnect()
  resizeObserver = null
  destroyNvl()
})
</script>

<template>
  <div
    ref="root"
    class="space-y-3"
  >
    <div
      v-if="legend.length || showHint"
      class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2"
    >
      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
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
      <p
        v-if="showHint"
        class="text-xs text-muted"
      >
        Scroll or pinch to zoom · drag background to pan · drag nodes to rearrange · click a node for details
      </p>
    </div>

    <div class="relative w-full">
      <div
        v-if="interactive && zoom"
        class="absolute right-3 top-3 z-10 flex flex-col gap-1"
      >
        <UButton
          color="neutral"
          variant="soft"
          size="xs"
          icon="i-lucide-plus"
          aria-label="Zoom in"
          @click="nudgeZoom(1.2)"
        />
        <UButton
          color="neutral"
          variant="soft"
          size="xs"
          icon="i-lucide-minus"
          aria-label="Zoom out"
          @click="nudgeZoom(1 / 1.2)"
        />
        <UButton
          color="neutral"
          variant="soft"
          size="xs"
          icon="i-lucide-scan"
          aria-label="Fit graph"
          @click="fitGraph"
        />
      </div>
      <div
        ref="container"
        class="w-full overflow-hidden rounded-lg border border-default bg-elevated/30"
        :style="{ height, touchAction: 'none', overscrollBehavior: 'contain' }"
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

    <div
      v-if="selectedNode"
      class="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-default bg-elevated/40 px-4 py-3 text-sm"
    >
      <div class="min-w-0 space-y-1">
        <p class="font-semibold text-highlighted">
          {{ selectedNode.caption ?? selectedNode.id }}
        </p>
        <p
          v-if="selectedNode.labels?.length"
          class="text-xs text-muted"
        >
          {{ selectedNode.labels.join(' · ') }}
        </p>
        <p
          v-if="typeof selectedNode.score === 'number'"
          class="font-mono text-xs text-muted"
        >
          score {{ selectedNode.score.toFixed(6) }}
        </p>
      </div>
      <UButton
        color="neutral"
        variant="ghost"
        size="xs"
        @click="clearSelection"
      >
        Clear
      </UButton>
    </div>
  </div>
</template>
