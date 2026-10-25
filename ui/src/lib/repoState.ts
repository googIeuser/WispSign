/** Repo list state: refresh results paired with urls, merged with live edits. */
import type { WispErr } from './api'

export type RepoApp = {
  repo_url: string
  name: string
  bundle_id: string
  version: string
  download_url: string
  icon_url: string | null
  size: number | null
  description: string
  developer: string | null
}

export type Repo = {
  url: string
  name: string
  icon_url: string | null
  skipped: number
  apps: RepoApp[]
}

export type RepoEntry = { url: string; repo?: Repo; error?: WispErr }

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

/** repos_refresh returns one Repo or {error} per url, in repos_list order. */
export function refreshEntries(urls: string[], results: unknown): RepoEntry[] {
  if (!Array.isArray(results)) return []
  const entries: RepoEntry[] = []
  results.forEach((item, i) => {
    if (!isObject(item)) return
    if (isObject(item.error)) {
      if (urls[i]) entries.push({ url: urls[i], error: item.error as WispErr })
    } else if (typeof item.url === 'string' && Array.isArray(item.apps)) {
      entries.push({ url: item.url, repo: item as unknown as Repo })
    }
  })
  return entries
}

/**
 * Entries for `urls` (the backend's current list): refreshed data first,
 * else what the UI already had (a repo added while the refresh ran).
 */
export function mergeRepos(urls: string[], refreshed: RepoEntry[], current: RepoEntry[]): RepoEntry[] {
  const byUrl = (list: RepoEntry[], url: string) => list.find((e) => e.url === url)
  return urls.flatMap((url) => {
    const entry = byUrl(refreshed, url) ?? byUrl(current, url)
    return entry ? [entry] : []
  })
}
