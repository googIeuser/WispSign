/** Bridge client: typed calls over window.pywebview.api and job event plumbing. */

export type WispErr = { code: string; params: Record<string, unknown>; detail: string }
export type Result<T> = { ok: true; data: T } | { ok: false; error: WispErr }
export type JobEvent = {
  job: string
  type: 'progress' | 'done' | 'error'
  step?: string
  percent?: number
  result?: unknown
  error?: WispErr
}

/** Broadcast by the host after it handled a native file drop. */
export type LibraryChangedEvent = {
  type: 'library_changed'
  added: number
  ignored: number
  unresolved: number
  errors: WispErr[]
}

type Backend = Record<string, (...args: unknown[]) => Promise<Result<unknown>>>

declare global {
  interface Window {
    pywebview?: { api: Backend }
    __wisp?: (event: unknown) => void
  }
}

const READY_TIMEOUT_MS = 5000
const MAX_BUFFERED_JOBS = 50

export const isMock = typeof location !== 'undefined' && new URLSearchParams(location.search).has('mock')

const failure = (code: string, detail = ''): Result<never> => ({
  ok: false,
  error: { code, params: {}, detail },
})

// --- events -----------------------------------------------------------

const handlers = new Set<(e: JobEvent) => void>()

export function onEvent(handler: (e: JobEvent) => void): () => void {
  handlers.add(handler)
  return () => handlers.delete(handler)
}

const EVENT_TYPES = ['progress', 'done', 'error']

function isJobEvent(value: unknown): value is JobEvent {
  if (typeof value !== 'object' || value === null) return false
  const e = value as Record<string, unknown>
  return typeof e.job === 'string' && typeof e.type === 'string' && EVENT_TYPES.includes(e.type)
}

const libraryHandlers = new Set<(e: LibraryChangedEvent) => void>()

export function onLibraryChanged(handler: (e: LibraryChangedEvent) => void): () => void {
  libraryHandlers.add(handler)
  return () => libraryHandlers.delete(handler)
}

function isLibraryChanged(value: unknown): value is LibraryChangedEvent {
  if (typeof value !== 'object' || value === null) return false
  const e = value as Record<string, unknown>
  return e.type === 'library_changed' && typeof e.added === 'number' && Array.isArray(e.errors)
}

/** Deliver a bridge event to every handler; malformed events are ignored. */
export function dispatchEvent(event: unknown): void {
  if (isLibraryChanged(event)) {
    for (const handler of [...libraryHandlers]) {
      try {
        handler(event)
      } catch (exc) {
        console.error('library event handler failed', exc)
      }
    }
    return
  }
  if (!isJobEvent(event)) return
  for (const handler of [...handlers]) {
    try {
      handler(event)
    } catch (exc) {
      console.error('job event handler failed', exc)
    }
  }
}

if (typeof window !== 'undefined') window.__wisp = dispatchEvent

// --- backend ----------------------------------------------------------

let mockBackend: Promise<Backend> | null = null

const apiHas = (method: string): boolean =>
  typeof window.pywebview?.api?.[method] === 'function'

/**
 * pywebview creates window.pywebview.api early as an empty object, attaches
 * the methods (js/api.js _createApi) and then fires `pywebviewready`
 * (js/finish.js). Wait until the requested method really exists.
 */
async function resolveBackend(method: string): Promise<Backend | null> {
  if (isMock) {
    mockBackend ??= import('./mockApi').then(
      (m) => m.createMockApi(dispatchEvent, new URLSearchParams(location.search)) as Backend,
    )
    return mockBackend
  }
  if (apiHas(method)) return window.pywebview!.api
  return new Promise((resolve) => {
    const finish = (api: Backend | null) => {
      window.removeEventListener('pywebviewready', check)
      clearTimeout(timer)
      resolve(api)
    }
    const check = () => {
      if (apiHas(method)) finish(window.pywebview!.api)
    }
    const timer = setTimeout(() => finish(null), READY_TIMEOUT_MS)
    window.addEventListener('pywebviewready', check)
    check()
  })
}

export function call<T>(method: string, ...args: unknown[]): Promise<Result<T>> {
  return resolveBackend(method).then(async (backend) => {
    const fn = backend?.[method]
    if (!fn) return failure('error.unknown', `bridge unavailable: ${method}`)
    try {
      return (await fn(...args)) as Result<T>
    } catch (exc) {
      return failure('error.unknown', String(exc))
    }
  })
}

// --- jobs ---------------------------------------------------------------

export class JobError extends Error {
  readonly error: WispErr
  constructor(error: WispErr) {
    super(error.code)
    this.error = error
  }
}

/** Events that arrived for job ids no runJob knows yet (fast jobs). */
const orphanEvents = new Map<string, JobEvent[]>()
const watchers = new Map<string, (e: JobEvent) => void>()
/** Ids of jobs runJob already settled; their late events are dropped. */
const settledIds = new Set<string>()
const MAX_SETTLED_IDS = 200

function markSettled(id: string): void {
  settledIds.add(id)
  while (settledIds.size > MAX_SETTLED_IDS) {
    settledIds.delete(settledIds.values().next().value as string)
  }
}

onEvent((event) => {
  if (settledIds.has(event.job)) return
  const watcher = watchers.get(event.job)
  if (watcher) return watcher(event)
  const list = orphanEvents.get(event.job) ?? []
  list.push(event)
  orphanEvents.set(event.job, list)
  while (orphanEvents.size > MAX_BUFFERED_JOBS) {
    orphanEvents.delete(orphanEvents.keys().next().value as string)
  }
})

/**
 * Start a job method and resolve with its result. Safe against jobs that
 * finish before the id reaches JS: buffered events are replayed and the
 * terminal event is also fetched with job_result(id).
 */
export async function runJob<T = unknown>(
  method: string,
  args: unknown[] = [],
  onProgress?: (e: JobEvent) => void,
): Promise<T> {
  const started = await call<string>(method, ...args)
  if (!started.ok) throw new JobError(started.error)
  const id = started.data

  return new Promise<T>((resolve, reject) => {
    let settled = false
    const handle = (event: JobEvent) => {
      if (settled) return
      if (event.type === 'progress') return onProgress?.(event)
      settled = true
      watchers.delete(id)
      markSettled(id)
      if (event.type === 'done') resolve(event.result as T)
      else reject(new JobError(event.error ?? { code: 'error.unknown', params: {}, detail: '' }))
    }
    const fail = (error: WispErr) => {
      if (settled) return
      settled = true
      watchers.delete(id)
      markSettled(id)
      reject(new JobError(error))
    }
    watchers.set(id, handle)
    const buffered = orphanEvents.get(id) ?? []
    orphanEvents.delete(id)
    buffered.forEach(handle)
    if (settled) return
    void call<JobEvent | null>('job_result', id).then((res) => {
      if (!res.ok) fail(res.error)
      else if (isJobEvent(res.data)) handle(res.data)
    })
  })
}
