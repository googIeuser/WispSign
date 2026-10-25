<script lang="ts">
  import { onMount } from 'svelte'
  import AppDetail from '../components/AppDetail.svelte'
  import AppIcon from '../components/AppIcon.svelte'
  import AppList from '../components/AppList.svelte'
  import EmptyState from '../components/EmptyState.svelte'
  import ErrorBox from '../components/ErrorBox.svelte'
  import RepoAddForm from '../components/RepoAddForm.svelte'
  import SkeletonList from '../components/SkeletonList.svelte'
  import ViewShell from '../components/ViewShell.svelte'
  import { formatSize, hostOf, matchesQuery } from '../lib/format'
  import { t } from '../lib/i18n'
  import { uniqueKeys } from '../lib/listNav'
  import type { RepoApp } from '../lib/repoState'
  import { ensureLibrary, ensureRepos, refreshRepos, removeRepo, repos, reposError, reposStatus } from '../lib/stores'

  let query = $state('')
  let filter = $state<string | null>(null)
  let adding = $state(false)
  let selected = $state<string | null>(null)

  onMount(() => {
    ensureRepos()
    ensureLibrary()
  })

  const baseKey = (app: RepoApp) => `${app.repo_url}|${app.bundle_id}`
  const repoName = (url: string) => $repos.find((e) => e.url === url)?.repo?.name ?? url

  const filterEntry = $derived(filter ? $repos.find((e) => e.url === filter) : undefined)
  const apps = $derived(
    $repos
      .filter((e) => !filter || e.url === filter)
      .flatMap((e) => e.repo?.apps ?? [])
      .filter((app) => matchesQuery(query, [app.name, app.bundle_id, app.developer])),
  )
  // Row keys stay unique even if a repo ever lists one bundle ID twice.
  const appKeys = $derived(uniqueKeys(apps.map(baseKey)))
  const keyByApp = $derived(new Map(apps.map((app, i) => [app, appKeys[i]])))
  const appKey = (app: RepoApp) => keyByApp.get(app) ?? baseKey(app)
  const selectedApp = $derived(apps[appKeys.indexOf(selected ?? '')] ?? null)
  const loading = $derived($reposStatus !== 'ready' && $repos.length === 0)

  $effect(() => {
    if (filter && !$repos.some((e) => e.url === filter)) filter = null
  })
</script>

<ViewShell title={t('nav.repos')} count={loading ? undefined : apps.length}>
  {#snippet actions()}
    <button
      type="button"
      class="btn"
      aria-label={t('common.refresh')}
      title={t('common.refresh')}
      disabled={$reposStatus === 'loading'}
      onclick={refreshRepos}
    >
      <span class="spin" class:on={$reposStatus === 'loading'} aria-hidden="true">↻</span>
    </button>
    {#if !adding}
      <button type="button" class="btn btn-primary" onclick={() => (adding = true)}>{t('repos.add')}</button>
    {/if}
  {/snippet}

  {#snippet toolbar()}
    <div class="flex flex-col gap-3">
      {#if adding}<RepoAddForm onClose={() => (adding = false)} />{/if}
      <div class="flex flex-wrap items-center gap-2">
        <input
          class="field w-[220px] text-[13px]"
          type="search"
          placeholder={t('repos.search')}
          aria-label={t('repos.search')}
          bind:value={query}
        />
        <div class="flex flex-wrap gap-1.5" role="group" aria-label={t('repos.filter')}>
          <button type="button" class="chip" aria-pressed={filter === null} onclick={() => (filter = null)}>
            {t('repos.all')}
          </button>
          {#each $repos as entry (entry.url)}
            <span class="chip-wrap" class:bad={!!entry.error}>
              <button
                type="button"
                class="chip"
                aria-pressed={filter === entry.url}
                title={entry.url}
                onclick={() => (filter = entry.url)}
              >
                {#if entry.error}<span class="dot" aria-hidden="true"></span>{/if}
                <span class="max-w-[160px] truncate">{entry.repo?.name ?? hostOf(entry.url)}</span>
                {#if entry.repo}<span class="count">{entry.repo.apps.length}</span>{/if}
              </button>
              <button
                type="button"
                class="chip-x"
                aria-label={t('repos.remove', { name: entry.repo?.name ?? entry.url })}
                onclick={() => removeRepo(entry.url)}>×</button
              >
            </span>
          {/each}
        </div>
      </div>
    </div>
  {/snippet}

  {#if $reposError}
    <div class="mb-4"><ErrorBox error={$reposError} /></div>
  {/if}
  {#if filterEntry?.error}
    <div class="mb-4"><ErrorBox error={filterEntry.error} /></div>
  {/if}

  {#if loading}
    <SkeletonList rows={5} />
  {:else if $repos.length === 0}
    <EmptyState glyph="◈" title={t('repos.empty_title')} text={t('repos.empty_text')}>
      {#snippet action()}
        {#if !adding}
          <button type="button" class="btn btn-primary" onclick={() => (adding = true)}>{t('repos.add')}</button>
        {/if}
      {/snippet}
    </EmptyState>
  {:else if apps.length === 0}
    <EmptyState glyph="⌕" title={t('repos.no_match_title')} text={t('repos.no_match_text')}>
      {#snippet action()}
        <button type="button" class="btn" onclick={() => ((query = ''), (filter = null))}>{t('repos.clear_filters')}</button>
      {/snippet}
    </EmptyState>
  {:else}
    <AppList items={apps} key={appKey} {selected} onSelect={(k) => (selected = k)} label={t('repos.apps')}>
      {#snippet row(app: RepoApp)}
        <div class="flex items-center gap-3 p-3">
          <AppIcon name={app.name} src={app.icon_url} size={42} />
          <div class="min-w-0 flex-1">
            <div class="truncate text-[14px] font-semibold">{app.name}</div>
            <div class="truncate font-display text-[11px] text-muted">
              {app.version}{#if formatSize(app.size)}&nbsp;·&nbsp;{formatSize(app.size)}{/if}
            </div>
          </div>
          {#if !filter && $repos.length > 1}
            <span class="max-w-[120px] truncate text-[11px] text-muted">{repoName(app.repo_url)}</span>
          {/if}
        </div>
      {/snippet}
    </AppList>
  {/if}

  {#snippet detail()}
    {#if selectedApp}
      {#key appKey(selectedApp)}
        <AppDetail app={selectedApp} repoName={repoName(selectedApp.repo_url)} />
      {/key}
    {:else}
      <p class="m-0 text-[13px] text-muted">{t('repos.select_prompt')}</p>
    {/if}
  {/snippet}
</ViewShell>

<style>
  .chip-wrap {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    border: 1px solid var(--color-line-strong);
    background: var(--color-raised);
    transition: border-color 160ms;
  }
  .chip-wrap:hover {
    border-color: #3a3a3a;
  }
  .chip-wrap.bad {
    border-color: rgb(255 107 94 / 0.45);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 11px;
    border-radius: 999px;
    border: 1px solid var(--color-line-strong);
    background: var(--color-raised);
    color: var(--color-muted);
    font-family: var(--font-display);
    font-size: 11px;
    cursor: pointer;
    transition:
      color 160ms,
      background-color 160ms,
      transform 160ms var(--ease-out-quint);
  }
  .chip-wrap .chip {
    border: 0;
    background: transparent;
    padding-right: 4px;
  }
  .chip:hover {
    color: var(--color-ink);
  }
  .chip:active {
    transform: scale(0.97);
  }
  .chip[aria-pressed='true'] {
    color: var(--color-bg);
    background: var(--color-accent);
    border-color: var(--color-accent);
    font-weight: 700;
  }
  .chip-wrap:has(.chip[aria-pressed='true']) {
    border-color: var(--color-accent);
    background: var(--color-accent);
  }
  .chip-wrap:has(.chip[aria-pressed='true']) .chip-x {
    color: var(--color-bg);
  }
  .count {
    opacity: 0.7;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: var(--color-danger);
  }
  .chip-x {
    border: 0;
    background: transparent;
    color: var(--color-muted);
    padding: 0 9px 0 4px;
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    border-radius: 999px;
  }
  .chip-x:hover {
    color: var(--color-danger);
  }
  .spin {
    display: inline-block;
  }
  .spin.on {
    animation: spin 0.9s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
