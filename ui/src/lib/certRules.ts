/** Certificate rules shared by the cards and the mock; they mirror certs/store.py validate. */
import type { Warning } from './types'

const DAY_MS = 86_400_000
export const BLOCKING_CERT_WARNINGS = new Set(['warn.expired', 'warn.device_missing', 'warn.app_id_mismatch'])

/** "Expires soon" below this many whole days left (EXPIRES_SOON_DAYS in certs/store.py). */
export const EXPIRES_SOON_DAYS = 14

export type ExpiryState = 'ok' | 'soon' | 'expired'
export type Expiry = { days: number; state: ExpiryState }

/** Whole days left (floored) and the state, or null for an unparsable date. */
export function certExpiry(iso: string, now: number = Date.now()): Expiry | null {
  const at = Date.parse(iso)
  if (Number.isNaN(at)) return null
  const left = at - now
  const days = Math.floor(left / DAY_MS)
  if (left <= 0) return { days, state: 'expired' }
  return { days, state: days < EXPIRES_SOON_DAYS ? 'soon' : 'ok' }
}

/** Unlisted devices require the profile's explicit ProvisionsAllDevices flag. */
export function coversDevice(devices: string[], udid: string, allDevices = false): boolean {
  const wanted = udid.toLowerCase()
  return allDevices === true || devices.some((d) => d.toLowerCase() === wanted)
}

/** Explicit App IDs must equal the bundle ID; `prefix.*` must prefix it. */
export function appIdMatches(appId: string, bundleId: string): boolean {
  return appId.endsWith('*') ? bundleId.startsWith(appId.slice(0, -1)) : appId === bundleId
}

type CertFacts = { expires: string; devices: string[]; all_devices?: boolean; has_push: boolean; app_id: string }

/** The warnings certs_validate returns for these facts (bundleId: the ID being signed). */
export function certWarnings(
  cert: CertFacts,
  udid: string | null,
  bundleId: string | null = null,
  now: number = Date.now(),
): Warning[] {
  const warnings: Warning[] = []
  const expiry = certExpiry(cert.expires, now)
  if (expiry?.state === 'expired') warnings.push({ code: 'warn.expired', params: {} })
  else if (expiry?.state === 'soon') warnings.push({ code: 'warn.expires_soon', params: { days: expiry.days } })
  if (udid && !coversDevice(cert.devices, udid, cert.all_devices)) warnings.push({ code: 'warn.device_missing', params: {} })
  if (!cert.has_push) warnings.push({ code: 'warn.no_push', params: {} })
  if (bundleId && !appIdMatches(cert.app_id, bundleId)) {
    warnings.push({ code: 'warn.app_id_mismatch', params: { app_id: cert.app_id, bundle_id: bundleId } })
  }
  return warnings
}
