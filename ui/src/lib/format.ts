

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB']


export function safeImageSrc(value: unknown): string | null {
  if (typeof value !== 'string' || !value) return null
  if (value.startsWith('data:image/png;base64,')) return value
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && url.hostname ? url.href : null
  } catch {
    return null
  }
}

export function formatSize(bytes: number | null | undefined): string | null {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return null
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit++
  }
  return unit === 0 ? `${value} B` : `${value.toFixed(1)} ${UNITS[unit]}`
}

export function formatDate(iso: string, locale: string): string {
  const at = Date.parse(iso)
  if (Number.isNaN(at)) return iso
  return new Date(at).toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
}


export function isAbsoluteDir(path: string): boolean {
  const value = path.trim()
  return /^[A-Za-z]:[\\/]/.test(value) || /^\\\\[^\\]+\\[^\\]+/.test(value)
}


export function isValidBundleId(value: string): boolean {
  return /^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/.test(value)
}

export function matchesQuery(query: string, fields: (string | null | undefined)[]): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return fields.some((field) => typeof field === 'string' && field.toLowerCase().includes(needle))
}


export function hueFor(text: string): number {
  let hash = 0
  for (const char of text) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return hash % 360
}


export function hostOf(url: string): string {
  try {
    return new URL(url).host || url
  } catch {
    return url
  }
}
