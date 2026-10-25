import { beforeEach, describe, expect, test, vi } from 'vitest'
import { call, dispatchEvent, onEvent, onLibraryChanged, runJob, type JobEvent, type Result } from './api'

const ok = <T>(data: T): Result<T> => ({ ok: true, data })

type Api = Record<string, (...a: unknown[]) => Promise<Result<unknown>>>

function installBridge(api: Api) {
  window.pywebview = { api }
}

beforeEach(() => {
  delete window.pywebview
})

describe('runJob', () => {
  test('resolves with a job that finished before the id arrived', async () => {
    const done: JobEvent = { job: 'fast1', type: 'done', result: { n: 1 } }
    installBridge({
      repos_refresh: async () => {
        dispatchEvent(done) // the event beats the id
        return ok('fast1')
      },
      job_result: async () => ok(null),
    })
    await expect(runJob('repos_refresh')).resolves.toEqual({ n: 1 })
  })

  test('falls back to job_result when no event was seen', async () => {
    installBridge({
      repos_refresh: async () => ok('fast2'),
      job_result: async () => ok({ job: 'fast2', type: 'done', result: 'x' }),
    })
    await expect(runJob('repos_refresh')).resolves.toBe('x')
  })

  test('reports progress and rejects with the job error', async () => {
    const onProgress = vi.fn()
    installBridge({
      sign_and_install: async () => {
        setTimeout(() => {
          dispatchEvent({ job: 'slow1', type: 'progress', step: 'sign' })
          dispatchEvent({
            job: 'slow1',
            type: 'error',
            error: { code: 'error.identifier_mismatch', params: {}, detail: '' },
          })
        }, 0)
        return ok('slow1')
      },
      job_result: async () => ok(null),
    })
    await expect(runJob('sign_and_install', [], onProgress)).rejects.toMatchObject({
      error: { code: 'error.identifier_mismatch' },
    })
    expect(onProgress).toHaveBeenCalledWith(expect.objectContaining({ step: 'sign' }))
  })
})

describe('call readiness', () => {
  test('waits for a late-attached method after pywebviewready', async () => {
    const api: Api = {} // pywebview creates the api object empty
    window.pywebview = { api }
    const pending = call<string>('settings_get')
    setTimeout(() => {
      api.settings_get = async () => ok('late')
      window.dispatchEvent(new CustomEvent('pywebviewready'))
    }, 0)
    await expect(pending).resolves.toEqual(ok('late'))
  })

  test('answers error.unknown when the method never appears', async () => {
    vi.useFakeTimers()
    window.pywebview = { api: {} }
    const pending = call('never_there')
    await vi.advanceTimersByTimeAsync(5001)
    await expect(pending).resolves.toMatchObject({ ok: false, error: { code: 'error.unknown' } })
    vi.useRealTimers()
  })
})

describe('dispatchEvent', () => {
  test('ignores malformed events and isolates throwing handlers', () => {
    const good = vi.fn()
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    const offBad = onEvent(() => {
      throw new Error('boom')
    })
    const offGood = onEvent(good)
    ;[null, undefined, 'str', 42, {}, { job: 1, type: 'done' }, { job: 'a', type: 'weird' }].forEach(
      (e) => dispatchEvent(e),
    )
    expect(good).not.toHaveBeenCalled()
    expect(errors).not.toHaveBeenCalled()
    dispatchEvent({ job: 'iso1', type: 'progress' })
    expect(good).toHaveBeenCalledTimes(1)
    expect(errors).toHaveBeenCalledTimes(1)
    offBad()
    offGood()
    errors.mockRestore()
  })

  test('library_changed reaches only library listeners, never job handlers', () => {
    const job = vi.fn()
    const lib = vi.fn()
    const offJob = onEvent(job)
    const offLib = onLibraryChanged(lib)
    const event = { type: 'library_changed', added: 1, ignored: 0, unresolved: 0, errors: [] }
    dispatchEvent(event)
    dispatchEvent({ type: 'library_changed' }) // malformed: ignored
    expect(lib).toHaveBeenCalledTimes(1)
    expect(lib).toHaveBeenCalledWith(event)
    expect(job).not.toHaveBeenCalled()
    offJob()
    offLib()
  })

  test('an unknown event type does not reject a running job', async () => {
    installBridge({
      m: async () => {
        setTimeout(() => {
          dispatchEvent({ job: 'unk1', type: 'bogus' })
          dispatchEvent({ job: 'unk1', type: 'done', result: 7 })
        }, 0)
        return ok('unk1')
      },
      job_result: async () => ok(null),
    })
    await expect(runJob('m')).resolves.toBe(7)
  })
})

describe('runJob failures', () => {
  test('rejects with the error when job_result fails and no event arrived', async () => {
    installBridge({
      m: async () => ok('lost1'),
      job_result: async () => ({
        ok: false,
        error: { code: 'error.unknown', params: {}, detail: 'gone' },
      }),
    })
    await expect(runJob('m')).rejects.toMatchObject({ error: { code: 'error.unknown' } })
  })

  test('drops late events of an already settled job', async () => {
    const seen = vi.fn()
    installBridge({
      m: async () => ok('late1'),
      job_result: async () => ok({ job: 'late1', type: 'done', result: 1 }),
    })
    await expect(runJob('m')).resolves.toBe(1)
    // A second runJob reusing the id must not see the stale terminal event.
    dispatchEvent({ job: 'late1', type: 'error', error: { code: 'x', params: {}, detail: '' } })
    installBridge({ m: async () => ok('late1'), job_result: async () => ok(null) })
    const second = runJob('m').then(seen, seen)
    await new Promise((r) => setTimeout(r, 10))
    expect(seen).not.toHaveBeenCalled() // still pending: stale event was dropped
    void second
  })
})
