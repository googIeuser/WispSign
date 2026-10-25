import { flushSync, mount, unmount } from 'svelte'
import { afterEach, describe, expect, test } from 'vitest'
import { locale } from '../lib/i18n'
import type { Cert } from '../lib/types'
import CertCard from './CertCard.svelte'

const DAY_MS = 86_400_000
const cert = (patch: Partial<Cert>): Cert => ({
  id: 'a1b2c3d4e5f6',
  nickname: 'Demo',
  team_id: 'ABCDE12345',
  common_name: 'Apple Development: Demo',
  app_id: '*',
  is_wildcard: true,
  has_push: true,
  devices: ['00008110-000A1B2C'],
  all_devices: false,
  expires: new Date(Date.now() + 200 * DAY_MS).toISOString(),
  added_at: '2026-10-24T12:00:00Z',
  broken: false,
  ...patch,
})

let mounted: Record<string, unknown> | null = null
function render(c: Cert, connectedUdid: string | null) {
  locale.set('tr')
  mounted = mount(CertCard, { target: document.body, props: { cert: c, connectedUdid } })
  flushSync()
  return document.body.textContent ?? ''
}

afterEach(() => {
  if (mounted) unmount(mounted)
  mounted = null
  document.body.innerHTML = ''
})

describe('CertCard follows the backend rules', () => {
  test('explicit all-device permission is shown as covering the phone', () => {
    const text = render(cert({ devices: [], all_devices: true }), 'ANY')
    expect(text).toContain('tüm cihazlar')
    expect(text).not.toContain('kayıtlı değil')
  })

  test('a profile without device authorization is not shown as covering the phone', () => {
    const text = render(cert({ devices: [] }), '00008110-000A1B2C')
    expect(text).not.toContain('tüm cihazlar')
    expect(text).toContain('bu iPhone kayıtlı değil')
  })

  test('UDIDs compare case-insensitively', () => {
    const text = render(cert({ devices: ['00008110-000a1b2c'] }), '00008110-000A1B2C')
    expect(text).not.toContain('kayıtlı değil')
  })

  test('a missing device is still flagged', () => {
    expect(render(cert({ devices: ['OTHER'] }), '00008110-000A1B2C')).toContain('bu iPhone kayıtlı değil')
  })

  test('exactly fourteen days left is not "soon" yet', () => {
    render(cert({ expires: new Date(Date.now() + 14 * DAY_MS + 60_000).toISOString() }), null)
    expect(document.querySelector('.tone-good')?.textContent).toContain('14 gün kaldı')
  })

  test('a broken record is shown as broken, without expiry or devices', () => {
    const text = render(cert({ broken: true, devices: [] }), '00008110-000A1B2C')
    expect(text).toContain('bozuk')
    expect(text).not.toContain('gün kaldı')
    expect(text).not.toContain('cihaz')
  })
})
