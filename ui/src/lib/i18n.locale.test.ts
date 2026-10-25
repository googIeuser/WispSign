import { get } from 'svelte/store'
import { afterEach, describe, expect, test, vi } from 'vitest'

const settings = vi.hoisted(() => ({ language: null as string | null }))
vi.mock('./api', () => ({
  call: vi.fn(async () => ({ ok: true, data: { language: settings.language } })),
}))

import { initLocale, locale } from './i18n'

function browserLanguage(value: string) {
  vi.spyOn(navigator, 'language', 'get').mockReturnValue(value)
}

afterEach(() => vi.restoreAllMocks())

describe('initLocale', () => {
  test('no saved language: Turkish system language gives tr', async () => {
    settings.language = null
    locale.set('en')
    browserLanguage('tr-TR')
    await initLocale()
    expect(get(locale)).toBe('tr')
  })

  test('no saved language: any other system language falls back to en', async () => {
    settings.language = null
    locale.set('tr')
    browserLanguage('de-DE')
    await initLocale()
    expect(get(locale)).toBe('en')
  })

  test('a language the user chose wins over the system language', async () => {
    settings.language = 'en'
    browserLanguage('tr-TR')
    await initLocale()
    expect(get(locale)).toBe('en')
  })
})
