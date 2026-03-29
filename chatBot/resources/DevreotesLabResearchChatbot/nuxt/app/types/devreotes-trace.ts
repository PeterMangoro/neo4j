/** Client-safe mirror of server DevreotesTrace (audit / retrieval snapshot). */
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
}
