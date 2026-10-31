

export function nextIndex(key: string, current: number, length: number): number | null {
  if (length === 0) return null
  const last = length - 1
  switch (key) {
    case 'ArrowDown':
    case 'ArrowRight':
      return current < 0 ? 0 : Math.min(last, current + 1)
    case 'ArrowUp':
    case 'ArrowLeft':
      return current < 0 ? 0 : Math.max(0, current - 1)
    case 'Home':
      return 0
    case 'End':
      return last
    default:
      return null
  }
}


export function uniqueKeys(keys: string[]): string[] {
  const seen = new Set(keys)
  const used = new Set<string>()
  return keys.map((key) => {
    if (!used.has(key)) {
      used.add(key)
      return key
    }
    let n = 2
    while (seen.has(`${key}#${n}`) || used.has(`${key}#${n}`)) n++
    const unique = `${key}#${n}`
    used.add(unique)
    return unique
  })
}
