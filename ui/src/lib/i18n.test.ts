import { describe, expect, test } from 'vitest'
import codes from './codes.json'
import tr from '../locales/tr.json'
import en from '../locales/en.json'
import { locale, t } from './i18n'

const keys = (o: object) => Object.keys(o).sort()

describe('i18n', () => {
  test('locales have identical keys', () => expect(keys(tr)).toEqual(keys(en)))

  test('every backend code has a message', () => {
    const trMap = tr as Record<string, string>
    const enMap = en as Record<string, string>
    codes.forEach((c) => {
      expect(trMap[c]).toBeTruthy()
      expect(enMap[c]).toBeTruthy()
    })
  })

  test('error texts follow the spec table', () => {
    const trMap = tr as Record<string, string>
    expect(trMap['error.identifier_mismatch']).toBe(
      'Uygulama telefonda farklı bir sertifikayla yüklü. Aynı sertifikayı seç ya da eskisini sil.',
    )
    expect(trMap['error.verify_failed']).toBe('İmza doğrulanamadı; yükleme denenmedi.')
    expect(trMap['error.signature_invalid']).toMatch(/süresi dolmuş.*iptal.*profilde kayıtlı değil/)
  })

  test('t interpolates params', () => expect(t('warn.expires_soon', { days: 3 })).toContain('3'))

  test('t follows the locale store and falls back to the key', () => {
    locale.set('tr')
    expect(t('nav.repos')).toBe('Repolar')
    locale.set('en')
    expect(t('nav.repos')).toBe('Repos')
    expect(t('no.such.key')).toBe('no.such.key')
  })
})
