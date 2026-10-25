import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { dispatchEvent } from './api'
import { hostHandlesDrops } from './drop'
import { initHostEvents, library } from './stores'
import { toasts } from './toast'
import { get } from 'svelte/store'

const entry = { id: 'e1', name: 'App', bundle_id: 'a.b', version: '1', path: 'a.ipa', source: 'file' }
const base = { type: 'library_changed', added: 0, ignored: 0, unresolved: 0, errors: [] as unknown[] }
const settle = () => new Promise((r) => setTimeout(r, 0))

let listCalls = 0
let off: () => void

beforeEach(() => {
  listCalls = 0
  toasts.set([])
  library.set([])
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: { library_list: async () => (listCalls++, { ok: true, data: [entry] }) },
  }
  off = initHostEvents()
})

afterEach(() => {
  off()
  delete (window as unknown as { pywebview?: unknown }).pywebview
})

describe('host drop events (app level)', () => {
  test('added files refresh the library store and show a toast', async () => {
    dispatchEvent({ ...base, added: 1 })
    await settle()
    expect(listCalls).toBe(1)
    expect(get(library)).toEqual([entry])
    expect(get(toasts).map((t) => t.kind)).toEqual(['info'])
  })

  test('errors become error toasts without refreshing', async () => {
    const error = { code: 'error.ipa_invalid', params: {}, detail: '' }
    dispatchEvent({ ...base, errors: [error] })
    await settle()
    expect(listCalls).toBe(0)
    expect(get(toasts)[0]).toMatchObject({ kind: 'error', error })
  })

  test('only non-ipa files or unresolved paths show an info toast', async () => {
    dispatchEvent({ ...base, ignored: 1 })
    dispatchEvent({ ...base, unresolved: 1 })
    await settle()
    expect(get(toasts)).toHaveLength(2)
    expect(listCalls).toBe(0)
  })

  test('unsubscribing stops handling', async () => {
    off()
    dispatchEvent({ ...base, added: 1 })
    await settle()
    expect(listCalls).toBe(0)
    off = initHostEvents()
  })
})

describe('hostHandlesDrops', () => {
  test('true only when pywebview is present', () => {
    expect(hostHandlesDrops({})).toBe(false)
    expect(hostHandlesDrops({ pywebview: { api: {} } })).toBe(true)
  })
})
