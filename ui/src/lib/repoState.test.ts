import { describe, expect, test } from 'vitest'
import { mergeRepos, refreshEntries, type Repo, type RepoEntry } from './repoState'

const repo = (url: string, name = url): Repo => ({ url, name, icon_url: null, skipped: 0, apps: [] })
const err = { code: 'error.network', params: {}, detail: 'boom' }

describe('refreshEntries', () => {
  test('pairs refresh results with the urls they were fetched for', () => {
    const entries = refreshEntries(
      ['https://a', 'https://b'],
      [repo('https://a', 'A'), { error: err }],
    )
    expect(entries).toEqual([
      { url: 'https://a', repo: repo('https://a', 'A') },
      { url: 'https://b', error: err },
    ])
  })

  test('drops results that are not repos or errors', () => {
    expect(refreshEntries(['https://a'], [42])).toEqual([])
    expect(refreshEntries(['https://a'], 'nope')).toEqual([])
  })
})

describe('mergeRepos', () => {
  test('keeps the current url order and prefers refreshed entries', () => {
    const current: RepoEntry[] = [{ url: 'https://b', repo: repo('https://b', 'old') }]
    const refreshed: RepoEntry[] = [
      { url: 'https://a', repo: repo('https://a') },
      { url: 'https://b', repo: repo('https://b', 'new') },
    ]
    expect(mergeRepos(['https://a', 'https://b'], refreshed, current)).toEqual(refreshed)
  })

  test('keeps a repo added during the refresh and drops one removed during it', () => {
    const current: RepoEntry[] = [{ url: 'https://c', repo: repo('https://c') }]
    const refreshed: RepoEntry[] = [{ url: 'https://a', repo: repo('https://a') }]
    expect(mergeRepos(['https://c'], refreshed, current)).toEqual(current)
  })

  test('urls with no data yet are left out', () => {
    expect(mergeRepos(['https://x'], [], [])).toEqual([])
  })
})
