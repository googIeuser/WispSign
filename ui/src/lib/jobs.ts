/** Background job state keyed by what it is for, so views can unmount and come back. */
import { get, writable } from 'svelte/store'
import { JobError, runJob, type WispErr } from './api'

export type JobState =
  | { status: 'running'; step?: string; percent?: number }
  | { status: 'done'; step?: string; result: unknown }
  | { status: 'error'; step?: string; error: WispErr }

export const jobs = writable<Record<string, JobState>>({})

function put(key: string, state: JobState): void {
  jobs.update((all) => ({ ...all, [key]: state }))
}

export function clearJob(key: string): void {
  jobs.update((all) => Object.fromEntries(Object.entries(all).filter(([k]) => k !== key)))
}

const toWispErr = (exc: unknown): WispErr =>
  exc instanceof JobError ? exc.error : { code: 'error.unknown', params: {}, detail: String(exc) }

/** Start `method` unless a job for `key` is already running; resolves when it settles. */
export async function trackJob(key: string, method: string, args: unknown[]): Promise<void> {
  if (get(jobs)[key]?.status === 'running') return
  put(key, { status: 'running' })
  let step: string | undefined
  try {
    const result = await runJob(method, args, (event) => {
      step = event.step ?? step
      put(key, { status: 'running', step, percent: event.percent })
    })
    put(key, step ? { status: 'done', step, result } : { status: 'done', result })
  } catch (exc) {
    const error = toWispErr(exc)
    put(key, step ? { status: 'error', step, error } : { status: 'error', error })
  }
}
