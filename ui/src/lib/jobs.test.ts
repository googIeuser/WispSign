import { get } from 'svelte/store'
import { beforeEach, describe, expect, test } from 'vitest'
import { dispatchEvent, type Result } from './api'
import { clearJob, jobs, trackJob } from './jobs'

const ok = <T>(data: T): Result<T> => ({ ok: true, data })

beforeEach(() => {
  delete window.pywebview
  jobs.set({})
})

describe('trackJob', () => {
  test('records progress and the result under the key', async () => {
    window.pywebview = {
      api: {
        sign_and_install: async () => {
          setTimeout(() => dispatchEvent({ job: 'j1', type: 'progress', step: 'sign' }), 0)
          setTimeout(() => dispatchEvent({ job: 'j1', type: 'done', result: 7 }), 5)
          return ok('j1')
        },
        job_result: async () => ok(null),
      },
    }
    const done = trackJob('sign:x', 'sign_and_install', [])
    expect(get(jobs)['sign:x']).toMatchObject({ status: 'running' })
    await done
    expect(get(jobs)['sign:x']).toEqual({ status: 'done', step: 'sign', result: 7 })
  })

  test('records the mapped error when the job fails to start', async () => {
    const error = { code: 'error.no_device', params: {}, detail: '' }
    window.pywebview = { api: { sign_and_install: async () => ({ ok: false, error }) } }
    await trackJob('sign:y', 'sign_and_install', [])
    expect(get(jobs)['sign:y']).toEqual({ status: 'error', error })
  })

  test('ignores a second start while running and clearJob forgets the key', async () => {
    let starts = 0
    window.pywebview = {
      api: {
        repo_download: async () => {
          starts++
          setTimeout(() => dispatchEvent({ job: 'j2', type: 'done', result: null }), 5)
          return ok('j2')
        },
        job_result: async () => ok(null),
      },
    }
    const first = trackJob('dl', 'repo_download', [])
    await trackJob('dl', 'repo_download', [])
    await first
    expect(starts).toBe(1)
    clearJob('dl')
    expect(get(jobs).dl).toBeUndefined()
  })
})
