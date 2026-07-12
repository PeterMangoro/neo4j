// Loads a precomputed JSON file for a project from the static public/data tree.
//
// Default mode prerenders the data into the static HTML (read from disk during
// `nuxt generate`, fetched over HTTP on the client) - ideal for small payloads
// like stats/queries. Pass `{ clientOnly: true }` for large files (e.g. big
// graph dumps) that should be lazily fetched in the browser and never inlined.
//
// Usage:
//   const { data } = useProjectData<Stats>('music-knowledge-graph', 'stats')
//   const { data } = useProjectData<GraphData>('music-knowledge-graph', 'graph', { clientOnly: true })
export function useProjectData<T>(
  project: string,
  file: string,
  opts: { clientOnly?: boolean } = {}
) {
  const path = `/data/${project}/${file}.json`
  const key = `project-data-${project}-${file}`

  const handler = async (): Promise<T> => {
    // On the server (prerender) read straight from disk so the data is inlined
    // into the static HTML. This branch never runs when `server: false`.
    if (import.meta.server) {
      const { readFile } = await import('node:fs/promises')
      const { join } = await import('node:path')
      const abs = join(process.cwd(), 'public', 'data', project, `${file}.json`)
      return JSON.parse(await readFile(abs, 'utf-8')) as T
    }
    return (await $fetch(path)) as T
  }

  return useAsyncData(key, handler, { server: !opts.clientOnly, lazy: opts.clientOnly })
}
