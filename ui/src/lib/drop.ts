/**
 * Paths of dropped .ipa files. A browser never exposes a dropped file's
 * full path; the host must attach it (`pywebviewFullPath` or `path`).
 */

export type DropResult = { paths: string[]; unresolved: number; ignored: number }

function hostPath(file: File): string | null {
  const record = file as unknown as Record<string, unknown>
  for (const key of ['pywebviewFullPath', 'path']) {
    const value = record[key]
    if (typeof value === 'string' && /^([A-Za-z]:[\\/]|\\\\)/.test(value)) return value
  }
  return null
}

export function droppedIpas(files: Iterable<File>): DropResult {
  const result: DropResult = { paths: [], unresolved: 0, ignored: 0 }
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.ipa')) {
      result.ignored++
      continue
    }
    const path = hostPath(file)
    if (path) result.paths.push(path)
    else result.unresolved++
  }
  return result
}

/** Inside the desktop app the Python host adds dropped files itself. */
export function hostHandlesDrops(win: { pywebview?: unknown }): boolean {
  return Boolean(win.pywebview)
}
