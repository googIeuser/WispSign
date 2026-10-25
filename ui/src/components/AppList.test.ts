import { createRawSnippet, flushSync, mount, unmount } from 'svelte'
import { afterEach, describe, expect, test } from 'vitest'
import type { RepoApp } from '../lib/repoState'
import { repos, reposStatus, libraryStatus } from '../lib/stores'
import Repos from '../views/Repos.svelte'
import AppList from './AppList.svelte'

const app = (name: string): RepoApp => ({
  repo_url: 'https://example.com/repo.json',
  name,
  bundle_id: 'com.example.demo',
  version: '1.0',
  download_url: 'https://example.com/demo.ipa',
  icon_url: null,
  size: null,
  description: '',
  developer: null,
})

let mounted: Record<string, unknown> | null = null

afterEach(() => {
  if (mounted) unmount(mounted)
  mounted = null
  document.body.innerHTML = ''
})

describe('duplicate bundle IDs', () => {
  test('AppList renders items whose keys collide', () => {
    const row = createRawSnippet((item: () => RepoApp) => ({
      render: () => `<span>${item().name}</span>`,
    }))
    mounted = mount(AppList<RepoApp>, {
      target: document.body,
      props: {
        items: [app('Demo App'), app('Demo App Copy')],
        key: (a: RepoApp) => `${a.repo_url}|${a.bundle_id}`,
        selected: null,
        onSelect: () => {},
        label: 'apps',
        row,
      },
    })
    flushSync()
    expect(document.querySelectorAll('[role="option"]')).toHaveLength(2)
  })

  test('Repos view lists two apps with the same bundle ID', () => {
    reposStatus.set('ready')
    libraryStatus.set('ready')
    const url = 'https://example.com/repo.json'
    repos.set([
      { url, repo: { url, name: 'Demo Repo', icon_url: null, skipped: 0, apps: [app('Demo App'), app('Demo App Copy')] } },
    ])
    mounted = mount(Repos, { target: document.body })
    flushSync()
    const options = document.querySelectorAll('[role="option"]')
    expect(options).toHaveLength(2)
    ;(options[1] as HTMLElement).click()
    flushSync()
    expect(options[1].getAttribute('aria-selected')).toBe('true')
    expect(options[0].getAttribute('aria-selected')).toBe('false')
  })
})
