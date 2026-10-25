/** App-wide state shared by the views: navigation, repos, library and downloads. */
import { get, writable } from 'svelte/store'
import { call, JobError, onLibraryChanged, runJob, type LibraryChangedEvent, type WispErr } from './api'
import { t } from './i18n'
import { clearJob, jobs, trackJob } from './jobs'
import { mergeRepos, refreshEntries, type Repo, type RepoApp, type RepoEntry } from './repoState'
import { pushToast } from './toast'
import type { Device, LibraryEntry, ViewId } from './types'

export const activeView = writable<ViewId>('repos')

// --- repos -------------------------------------------------------------

export const repos = writable<RepoEntry[]>([])
export const reposStatus = writable<'idle' | 'loading' | 'ready'>('idle')
export const reposError = writable<WispErr | null>(null)

const errorOf = (exc: unknown): WispErr =>
  exc instanceof JobError ? exc.error : { code: 'error.unknown', params: {}, detail: String(exc) }

export async function refreshRepos(): Promise<void> {
  if (get(reposStatus) === 'loading') return
  reposStatus.set('loading')
  reposError.set(null)
  try {
    const before = await call<string[]>('repos_list')
    if (!before.ok) throw new JobError(before.error)
    const results = before.data.length ? await runJob<unknown>('repos_refresh') : []
    const refreshed = refreshEntries(before.data, results)
    const after = await call<string[]>('repos_list')
    const urls = after.ok ? after.data : before.data
    repos.set(mergeRepos(urls, refreshed, get(repos)))
  } catch (exc) {
    reposError.set(errorOf(exc))
  } finally {
    reposStatus.set('ready')
  }
}

export function ensureRepos(): void {
  if (get(reposStatus) === 'idle') void refreshRepos()
}

/** Add a repo; resolves with an error to show inline, or null on success. */
export async function addRepo(url: string): Promise<WispErr | null> {
  const res = await call<Repo>('repos_add', url)
  if (!res.ok) return res.error
  const entry: RepoEntry = { url: res.data.url, repo: res.data }
  repos.update((list) =>
    list.some((e) => e.url === entry.url)
      ? list.map((e) => (e.url === entry.url ? entry : e))
      : [...list, entry],
  )
  pushToast({ kind: 'info', text: t('repos.added', { name: res.data.name }) })
  return null
}

export async function removeRepo(url: string): Promise<void> {
  const res = await call('repos_remove', url)
  if (!res.ok) {
    pushToast({ kind: 'error', text: '', error: res.error })
    return
  }
  repos.update((list) => list.filter((e) => e.url !== url))
  pushToast({ kind: 'info', text: t('repos.removed') })
}

export const downloadKey = (app: RepoApp) => `download:${app.repo_url}|${app.bundle_id}`

export async function downloadApp(app: RepoApp): Promise<void> {
  const key = downloadKey(app)
  await trackJob(key, 'repo_download', [app.repo_url, app.bundle_id])
  const state = get(jobs)[key]
  if (state?.status === 'done') {
    pushToast({ kind: 'info', text: t('repos.downloaded') })
    await loadLibrary()
    clearJob(key) // from here "in library" comes from the library list itself
  } else if (state?.status === 'error') {
    pushToast({ kind: 'error', text: '', error: state.error })
  }
}

// --- library -----------------------------------------------------------

export const library = writable<LibraryEntry[]>([])
export const libraryStatus = writable<'idle' | 'loading' | 'ready'>('idle')

export async function loadLibrary(): Promise<WispErr | null> {
  if (get(libraryStatus) === 'idle') libraryStatus.set('loading')
  const res = await call<LibraryEntry[]>('library_list')
  libraryStatus.set('ready')
  if (!res.ok) return res.error
  library.set(res.data)
  return null
}

export function ensureLibrary(): void {
  if (get(libraryStatus) === 'idle') void loadLibrary()
}

const iconCache = new Map<string, Promise<string | null>>()

/** Data URL of a library entry's icon (cached per id). */
export function libraryIcon(id: string): Promise<string | null> {
  let icon = iconCache.get(id)
  if (!icon) {
    icon = call<string | null>('library_icon', id).then((res) => (res.ok ? res.data : null))
    iconCache.set(id, icon)
  }
  return icon
}

// --- devices -----------------------------------------------------------

export type DeviceScan = { devices: Device[]; error: WispErr | null }

export async function scanDevices(): Promise<DeviceScan> {
  const res = await call<Device[]>('device_list')
  return res.ok ? { devices: res.data, error: null } : { devices: [], error: res.error }
}

// --- native file drops ---------------------------------------------------

/** The desktop host adds natively dropped files itself, then broadcasts the outcome. */
export async function handleHostDrop(event: LibraryChangedEvent): Promise<void> {
  for (const err of event.errors) pushToast({ kind: 'error', text: '', error: err })
  if (event.unresolved) pushToast({ kind: 'info', text: t('library.drop_unsupported') })
  else if (event.ignored && !event.added && !event.errors.length) {
    pushToast({ kind: 'info', text: t('library.drop_not_ipa') })
  }
  if (event.added) {
    pushToast({ kind: 'info', text: t('library.added', { count: event.added }) })
    await loadLibrary()
  }
}

/** Listen for host drops in every view; returns the unsubscribe function. */
export function initHostEvents(): () => void {
  return onLibraryChanged((event) => void handleHostDrop(event))
}
