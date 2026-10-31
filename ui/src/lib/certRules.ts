
import type { Warning } from './types'

const DAY_MS = 86_400_000
export const BLOCKING_CERT_WARNINGS = new Set(['warn.expired', 'warn.device_missing', 'warn.app_id_mismatch'])


export const EXPIRES_SOON_DAYS = 14

export type ExpiryState = 'ok' | 'soon' | 'expired'
export type Expiry = { days: number; state: ExpiryState }


export function certExpiry(iso: string, now: number = Date.now()): Expiry | null {
  const at = Date.parse(iso)
  if (Number.isNaN(at)) return null
  const left = at - now
  const days = Math.floor(left / DAY_MS)
  if (left <= 0) return { days, state: 'expired' }
  return { days, state: days < EXPIRES_SOON_DAYS ? 'soon' : 'ok' }
}


export function coversDevice(devices: string[], udid: string, allDevices = false): boolean {
  const wanted = udid.toLowerCase()
  return allDevices === true || devices.some((d) => d.toLowerCase() === wanted)
}


export function appIdMatches(appId: string, bundleId: string): boolean {
  return appId.endsWith('*') ? bundleId.startsWith(appId.slice(0, -1)) : appId === bundleId
}

type CertFacts = { expires: string; devices: string[]; all_devices?: boolean; has_push: boolean; app_id: string }


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
