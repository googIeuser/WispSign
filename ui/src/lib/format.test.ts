import { describe, expect, test } from 'vitest'
import {
  formatSize,
  hostOf,
  hueFor,
  isAbsoluteDir,
  isValidBundleId,
  matchesQuery,
  safeImageSrc,
} from './format'

describe('safeImageSrc', () => {
  test('keeps https and inline png data only', () => {
    expect(safeImageSrc('https://cdn.example.com/a.png')).toBe('https://cdn.example.com/a.png')
    expect(safeImageSrc('data:image/png;base64,iVBOR')).toBe('data:image/png;base64,iVBOR')
  })

  test('rejects other schemes, junk and empty values', () => {
    for (const bad of [
      'http://example.com/a.png',
      'javascript:alert(1)',
      'file:///C:/a.png',
      'data:text/html;base64,PHNjcmlwdD4=',
      '//example.com/a.png',
      'https://',
      '',
      null,
      undefined,
      42,
    ]) {
      expect(safeImageSrc(bad)).toBeNull()
    }
  })
})

describe('formatSize', () => {
  test('uses binary units with one decimal', () => {
    expect(formatSize(96_000_000)).toBe('91.6 MB')
    expect(formatSize(512)).toBe('512 B')
    expect(formatSize(2048)).toBe('2.0 KB')
    expect(formatSize(3 * 1024 ** 3)).toBe('3.0 GB')
  })

  test('returns null for unknown sizes', () => {
    expect(formatSize(null)).toBeNull()
    expect(formatSize(-1)).toBeNull()
    expect(formatSize(Number.NaN)).toBeNull()
  })
})

describe('isAbsoluteDir', () => {
  test('accepts drive and UNC paths', () => {
    expect(isAbsoluteDir('C:\\Users\\demo\\ipas')).toBe(true)
    expect(isAbsoluteDir('d:/ipas')).toBe(true)
    expect(isAbsoluteDir('\\\\server\\share\\ipas')).toBe(true)
  })
  test('rejects relative and empty paths', () => {
    for (const bad of ['', '   ', 'ipas', 'relative\\path', 'C:ipas', '..\\x', '/tmp']) {
      expect(isAbsoluteDir(bad)).toBe(false)
    }
  })
})

describe('isValidBundleId', () => {
  test('accepts reverse-DNS ids', () => {
    expect(isValidBundleId('com.example.demo')).toBe(true)
    expect(isValidBundleId('net.whats-app.App2')).toBe(true)
  })
  test('rejects empty, spaced or malformed ids', () => {
    for (const bad of ['', 'com', 'com..x', '.com.x', 'com.x.', 'com x.y', 'com.ä.x']) {
      expect(isValidBundleId(bad)).toBe(false)
    }
  })
})

describe('matchesQuery', () => {
  test('matches any field case-insensitively, empty query matches all', () => {
    expect(matchesQuery('', ['Demo App'])).toBe(true)
    expect(matchesQuery('demo', ['Demo App', null])).toBe(true)
    expect(matchesQuery('EXAMPLE', ['Demo App', 'com.example.demo'])).toBe(true)
    expect(matchesQuery('other', ['Demo App', undefined])).toBe(false)
  })
})

describe('hueFor', () => {
  test('is stable and within the hue circle', () => {
    expect(hueFor('Demo App')).toBe(hueFor('Demo App'))
    expect(hueFor('Demo App')).toBeGreaterThanOrEqual(0)
    expect(hueFor('Demo App')).toBeLessThan(360)
  })
})

describe('hostOf', () => {
  test('shows the host, or the raw text when unparsable', () => {
    expect(hostOf('https://repo.example.com/a.json')).toBe('repo.example.com')
    expect(hostOf('not a url')).toBe('not a url')
  })
})
