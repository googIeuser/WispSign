/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// Read from disk: Vitest stubs CSS imports (even ?raw) to an empty string, and under jsdom
// import.meta.url is not a file URL, so resolve from the ui/ root that Vitest runs in.
const css = readFileSync('src/lib/theme.css', 'utf8')

// WCAG 2.x AA for normal-size text.
const AA = 4.5

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!match) throw new Error(`missing token --${name}`)
  return match[1]
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const SURFACES = ['bg', 'panel', 'raised', 'accent-dark', 'danger-dark']

test.each(SURFACES)('muted text is readable on %s', (surface) => {
  expect(contrast(token('color-muted'), token(`color-${surface}`))).toBeGreaterThanOrEqual(AA)
})

test.each(SURFACES)('placeholder text is readable on %s', (surface) => {
  expect(contrast(token('color-placeholder'), token(`color-${surface}`))).toBeGreaterThanOrEqual(AA)
})
