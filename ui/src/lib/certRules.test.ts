import { describe, expect, test } from 'vitest'
import { appIdMatches, certExpiry, certWarnings, coversDevice, EXPIRES_SOON_DAYS } from './certRules'

const DAY_MS = 86_400_000
const now = Date.parse('2026-10-24T12:00:00Z')
const at = (ms: number) => new Date(now + ms).toISOString()

describe('certExpiry (same rule as certs/store.py validate)', () => {
  test('soon starts below fourteen whole days', () => {
    expect(EXPIRES_SOON_DAYS).toBe(14)
    expect(certExpiry(at(14 * DAY_MS), now)).toEqual({ days: 14, state: 'ok' })
    expect(certExpiry(at(14 * DAY_MS - 1000), now)).toEqual({ days: 13, state: 'soon' })
    expect(certExpiry(at(3 * DAY_MS + 1), now)).toEqual({ days: 3, state: 'soon' })
  })

  test('expired once the moment has passed', () => {
    expect(certExpiry(at(0), now)?.state).toBe('expired')
    expect(certExpiry(at(-DAY_MS), now)?.state).toBe('expired')
    expect(certExpiry(at(1000), now)).toEqual({ days: 0, state: 'soon' })
  })

  test('null for unparsable dates', () => expect(certExpiry('soon', now)).toBeNull())
})

describe('coversDevice', () => {
  test('an empty list does not authorize every device', () => expect(coversDevice([], 'ANY')).toBe(false))
  test('explicit all-device permission covers unlisted devices', () => expect(coversDevice([], 'ANY', true)).toBe(true))
  test('compares UDIDs case-insensitively', () => {
    expect(coversDevice(['00008110-000a1b2c'], '00008110-000A1B2C')).toBe(true)
    expect(coversDevice(['AAA'], 'BBB')).toBe(false)
  })
})

describe('certWarnings', () => {
  const cert = { expires: at(3 * DAY_MS + 1), devices: ['AAA'], has_push: false, app_id: 'com.example.demo' }

  test('matches the card: days, device and push', () => {
    expect(certWarnings(cert, 'bbb', null, now)).toEqual([
      { code: 'warn.expires_soon', params: { days: 3 } },
      { code: 'warn.device_missing', params: {} },
      { code: 'warn.no_push', params: {} },
    ])
    expect(certWarnings({ ...cert, devices: [], has_push: true }, 'bbb', null, now)).toEqual([
      { code: 'warn.expires_soon', params: { days: 3 } },
      { code: 'warn.device_missing', params: {} },
    ])
  })
})

describe('App ID check (same rule as certs/store.py)', () => {
  test('explicit IDs must match, wildcards must prefix', () => {
    expect(appIdMatches('com.example.demo', 'com.example.demo')).toBe(true)
    expect(appIdMatches('com.example.demo', 'com.example.other')).toBe(false)
    expect(appIdMatches('com.example.*', 'com.example.demo')).toBe(true)
    expect(appIdMatches('com.example.*', 'org.example.demo')).toBe(false)
    expect(appIdMatches('*', 'org.example.demo')).toBe(true)
  })

  test('a mismatching bundle ID is warned about', () => {
    const cert = { expires: at(200 * DAY_MS), devices: [], has_push: true, app_id: 'com.example.demo' }
    expect(certWarnings(cert, null, 'com.example.other', now)).toEqual([
      { code: 'warn.app_id_mismatch', params: { app_id: 'com.example.demo', bundle_id: 'com.example.other' } },
    ])
    expect(certWarnings(cert, null, 'com.example.demo', now)).toEqual([])
  })
})
