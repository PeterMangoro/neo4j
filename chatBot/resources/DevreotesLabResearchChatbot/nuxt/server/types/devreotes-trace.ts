import type { DevreotesResult, DevreotesThemesMeta } from '../utils/devreotesNdjson'

/** Persisted audit snapshot (no duplicate answer text). */
export type DevreotesTrace = {
  trace_version: 1
  backend: 'http' | 'bridge'
  query_type?: string
  query_type_label?: string
  routed_key?: string | null
  results_count?: number
  sources?: string[]
  retrieval_preview?: unknown[]
  abstained?: boolean
  abstain_reason?: string | null
  tool_calls_log?: Array<{ name?: string; args?: Record<string, unknown> }>
  themes_meta?: DevreotesThemesMeta
}

export function buildDevreotesTrace(
  result: DevreotesResult,
  backend: 'http' | 'bridge'
): DevreotesTrace {
  return {
    trace_version: 1,
    backend,
    query_type: result.query_type,
    query_type_label: result.query_type_label,
    routed_key: result.routed_key ?? null,
    results_count: result.results_count,
    sources: result.sources,
    retrieval_preview: result.retrieval_preview,
    abstained: result.abstained,
    abstain_reason: result.abstain_reason ?? null,
    tool_calls_log: result.tool_calls_log,
    themes_meta: result.themes_meta,
  }
}
