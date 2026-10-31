import { flushSync, mount, unmount } from 'svelte'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Result } from '../lib/api'
import { locale } from '../lib/i18n'
import { jobs } from '../lib/jobs'
import type { Cert, LibraryEntry, Warning } from '../lib/types'
import SignPanel from './SignPanel.svelte'

const call = vi.hoisted(() => vi.fn())
vi.mock('../lib/api', async (original) => ({
  ...await original<typeof import('../lib/api')>(),
  call,
}))

const cert: Cert = {
  id: 'a1b2c3d4e5f6', nickname: 'Demo', team_id: 'ABCDE12345', common_name: 'Demo',
  app_id: '*', is_wildcard: true, has_push: true, devices: ['U1'],
  all_devices: false,
  expires: '2030-01-01T00:00:00Z', added_at: '2026-10-24T12:00:00Z', broken: false,
}
const entry: LibraryEntry = {
  id: 'entry', name: 'Demo', bundle_id: 'com.example.demo', version: '1',
  path: 'demo.ipa', source: 'file', added_at: '2026-10-24T12:00:00Z', owned: true,
}
let validate: (bundle: string) => Promise<Result<Warning[]>>
let mounted: ReturnType<typeof mount> | null = null

beforeEach(() => {
  locale.set('tr')
  jobs.set({})
  validate = async () => ({ ok: true, data: [] })
  call.mockReset().mockImplementation(async (method: string, ...args: unknown[]) => {
    if (method === 'certs_list') return { ok: true, data: [cert] }
    if (method === 'device_list') return { ok: true, data: [{ udid: 'U1', name: 'Demo iPhone', ios: '18', model: 'Demo' }] }
    if (method === 'certs_validate') return validate(args[2] as string)
    throw new Error(`Unexpected call: ${method}`)
  })
})

afterEach(() => {
  if (mounted) unmount(mounted)
  mounted = null
  document.body.innerHTML = ''
})

async function render() {
  mounted = mount(SignPanel, { target: document.body, props: { entry } })
  flushSync()
  await vi.waitFor(() => expect(document.body.textContent).toContain('Demo iPhone'))
  return [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('İmzala ve Yükle'))!
}

test.each(['warn.expired', 'warn.device_missing', 'warn.app_id_mismatch'])(
  'signing is disabled for %s', async (code) => {
    validate = async () => ({ ok: true, data: [{ code, params: {} }] })
    const button = await render()
    await vi.waitFor(() => expect(document.querySelector('.badge.danger')).not.toBeNull())
    expect(button.disabled).toBe(true)
  },
)

test('signing stays disabled until validation finishes', async () => {
  let finish!: (result: Result<Warning[]>) => void
  validate = () => new Promise((resolve) => { finish = resolve })
  const button = await render()
  expect(button.disabled).toBe(true)
  finish({ ok: true, data: [] })
  await vi.waitFor(() => expect(button.disabled).toBe(false))
})

test('a failed validation keeps signing disabled', async () => {
  validate = async () => ({ ok: false, error: { code: 'error.cert_meta_corrupt', params: {}, detail: '' } })
  const button = await render()
  await vi.waitFor(() => expect(document.body.textContent).toContain('Sertifika kaydı bozulmuş'))
  expect(button.disabled).toBe(true)
})

test('missing push and a near expiry are warnings that still allow signing', async () => {
  validate = async () => ({ ok: true, data: [
    { code: 'warn.no_push', params: {} }, { code: 'warn.expires_soon', params: { days: 3 } },
  ] })
  const button = await render()
  await vi.waitFor(() => expect(button.disabled).toBe(false))
})

const advancedToggle = () =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('Gelişmiş seçenekler'))!

function openAdvanced() {
  advancedToggle().click()
  flushSync()
}

test('advanced options start collapsed and hide bundle ID, name and icon', async () => {
  await render()
  const toggle = advancedToggle()
  expect(toggle.getAttribute('aria-expanded')).toBe('false')
  expect(document.querySelector('input[type="radio"][value="change"]')).toBeNull()
  expect(document.body.textContent).not.toContain('PNG seç')
})

test('opening advanced options reveals the bundle ID, name and icon controls', async () => {
  await render()
  openAdvanced()
  const toggle = advancedToggle()
  expect(toggle.getAttribute('aria-expanded')).toBe('true')
  expect(document.getElementById(toggle.getAttribute('aria-controls')!)).not.toBeNull()
  expect(document.querySelector('input[type="radio"][value="change"]')).not.toBeNull()
  expect(document.body.textContent).toContain('PNG seç')
})

test('a changed value stays and is marked when advanced options are collapsed', async () => {
  await render()
  expect(document.body.textContent).not.toContain('özelleştirildi')
  openAdvanced()
  const name = document.querySelector<HTMLInputElement>('input[placeholder="Demo"]')!
  name.value = 'Kendi Adım'
  name.dispatchEvent(new Event('input', { bubbles: true }))
  flushSync()
  openAdvanced()
  expect(advancedToggle().getAttribute('aria-expanded')).toBe('false')
  expect(advancedToggle().textContent).toContain('özelleştirildi')
  openAdvanced()
  expect(document.querySelector<HTMLInputElement>('input[placeholder="Demo"]')!.value).toBe('Kendi Adım')
})

test('changing bundle ID invalidates the previous successful validation', async () => {
  validate = (bundle) => bundle === 'com.example.demo'
    ? Promise.resolve({ ok: true, data: [] }) : new Promise(() => {})
  const button = await render()
  await vi.waitFor(() => expect(button.disabled).toBe(false))
  openAdvanced()
  const change = document.querySelector<HTMLInputElement>('input[type="radio"][value="change"]')!
  change.click()
  flushSync()
  const input = document.querySelector<HTMLInputElement>('input[aria-label="Yeni bundle ID"]')!
  input.value = 'com.example.other'
  input.dispatchEvent(new Event('input', { bubbles: true }))
  flushSync()
  expect(button.disabled).toBe(true)
})
