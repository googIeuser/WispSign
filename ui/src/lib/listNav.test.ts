import { describe, expect, test } from 'vitest'
import { nextIndex, uniqueKeys } from './listNav'

describe('nextIndex', () => {
  test('arrows move and clamp at the ends', () => {
    expect(nextIndex('ArrowDown', 0, 3)).toBe(1)
    expect(nextIndex('ArrowDown', 2, 3)).toBe(2)
    expect(nextIndex('ArrowUp', 1, 3)).toBe(0)
    expect(nextIndex('ArrowUp', 0, 3)).toBe(0)
  })

  test('Home and End jump, other keys are ignored', () => {
    expect(nextIndex('Home', 2, 3)).toBe(0)
    expect(nextIndex('End', 0, 3)).toBe(2)
    expect(nextIndex('a', 1, 3)).toBeNull()
  })

  test('starts from the first item when nothing is focused, ignores empty lists', () => {
    expect(nextIndex('ArrowDown', -1, 3)).toBe(0)
    expect(nextIndex('ArrowDown', 0, 0)).toBeNull()
  })
})

describe('uniqueKeys', () => {
  test('keeps distinct keys and suffixes later duplicates', () => {
    expect(uniqueKeys(['a', 'b'])).toEqual(['a', 'b'])
    expect(uniqueKeys(['a', 'a', 'b', 'a'])).toEqual(['a', 'a#2', 'b', 'a#3'])
  })

  test('a suffix never collides with a real key', () => {
    const keys = uniqueKeys(['a#2', 'a', 'a'])
    expect(new Set(keys).size).toBe(3)
  })
})
