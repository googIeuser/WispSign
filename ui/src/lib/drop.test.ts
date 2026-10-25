import { describe, expect, test } from 'vitest'
import { droppedIpas } from './drop'

const file = (name: string, extra: Record<string, unknown> = {}) =>
  Object.assign(new File(['x'], name), extra)

describe('droppedIpas', () => {
  test('returns full paths of .ipa files the host exposes', () => {
    const files = [
      file('A.ipa', { pywebviewFullPath: 'C:\\in\\A.ipa' }),
      file('b.IPA', { path: 'C:\\in\\b.IPA' }),
      file('notes.txt', { pywebviewFullPath: 'C:\\in\\notes.txt' }),
    ]
    expect(droppedIpas(files)).toEqual({ paths: ['C:\\in\\A.ipa', 'C:\\in\\b.IPA'], unresolved: 0, ignored: 1 })
  })

  test('counts ipa files whose path is unknown', () => {
    expect(droppedIpas([file('A.ipa'), file('x.png')])).toEqual({ paths: [], unresolved: 1, ignored: 1 })
  })

  test('ignores non-string or relative path properties', () => {
    expect(droppedIpas([file('A.ipa', { path: 42 }), file('B.ipa', { path: 'B.ipa' })])).toEqual({
      paths: [],
      unresolved: 2,
      ignored: 0,
    })
  })
})
