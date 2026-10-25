/** Translations: t(key, params) over the active locale store. */
import { get, writable } from 'svelte/store'
import en from '../locales/en.json'
import tr from '../locales/tr.json'
import { call } from './api'

export type Locale = 'tr' | 'en'
type Catalog = Record<string, string>

const catalogs: Record<Locale, Catalog> = { tr, en }

function detectLocale(): Locale {
  const lang = typeof navigator === 'undefined' ? '' : navigator.language.toLowerCase()
  return lang.startsWith('tr') ? 'tr' : 'en'
}

export const locale = writable<Locale>(detectLocale())

export function t(key: string, params?: Record<string, string | number>): string {
  const message = catalogs[get(locale)][key] ?? catalogs.en[key] ?? key
  if (!params) return message
  return message.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  )
}

/** The language the user chose in settings; otherwise the system language (tr, else en). */
export async function initLocale(): Promise<void> {
  const res = await call<{ language?: string | null }>('settings_get')
  const saved = res.ok ? res.data.language : null
  locale.set(saved === 'tr' || saved === 'en' ? saved : detectLocale())
}

export async function setLocale(next: Locale): Promise<void> {
  locale.set(next)
  await call('settings_set', { language: next })
}
