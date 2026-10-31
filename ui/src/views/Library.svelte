<script lang="ts">
  import { onMount, untrack } from 'svelte'
  import AppIcon from '../components/AppIcon.svelte'
  import AppList from '../components/AppList.svelte'
  import EmptyState from '../components/EmptyState.svelte'
  import ErrorBox from '../components/ErrorBox.svelte'
  import SignPanel from '../components/SignPanel.svelte'
  import SkeletonList from '../components/SkeletonList.svelte'
  import ViewShell from '../components/ViewShell.svelte'
  import { call, type WispErr } from '../lib/api'
  import { droppedIpas, hostHandlesDrops } from '../lib/drop'
  import { hostOf } from '../lib/format'
  import { t } from '../lib/i18n'
  import { library, libraryIcon, libraryStatus, loadLibrary } from '../lib/stores'
  import { pushToast } from '../lib/toast'
  import type { LibraryEntry } from '../lib/types'

  let selected = $state<string | null>(null)
  let error = $state<WispErr | null>(null)
  let icons = $state<Record<string, string | null>>({})
  let dragging = $state(false)
  let busy = $state(false)
  let confirmRemove = $state(false)

  const entry = $derived($library.find((e) => e.id === selected) ?? null)

  onMount(async () => {
    error = await loadLibrary()
  })

  $effect(() => {
    const known = untrack(() => icons)
    for (const e of $library) {
      if (e.id in known) continue
      void libraryIcon(e.id).then((src) => (icons = { ...icons, [e.id]: src }))
    }
  })

  $effect(() => {
    void selected
    confirmRemove = false
  })

  async function addFiles() {
    busy = true
    const res = await call<LibraryEntry[]>('library_add_files')
    busy = false
    if (!res.ok) return pushToast({ kind: 'error', text: '', error: res.error })
    if (res.data.length) {
      pushToast({ kind: 'info', text: t('library.added', { count: res.data.length }) })
      await loadLibrary()
    }
  }

  async function onDrop(event: DragEvent) {
    event.preventDefault()
    dragging = false
    if (hostHandlesDrops(window)) return
    const found = droppedIpas(event.dataTransfer?.files ?? [])
    if (found.unresolved || (found.ignored && !found.paths.length)) {
      pushToast({ kind: 'info', text: t(found.unresolved ? 'library.drop_unsupported' : 'library.drop_not_ipa') })
    }
    let added = 0
    for (const path of found.paths) {
      const res = await call<LibraryEntry>('library_add_path', path)
      if (res.ok) added++
      else pushToast({ kind: 'error', text: '', error: res.error })
    }
    if (added) {
      pushToast({ kind: 'info', text: t('library.added', { count: added }) })
      await loadLibrary()
    }
  }

  function onDragOver(event: DragEvent) {
    if (!event.dataTransfer?.types.includes('Files')) return
    event.preventDefault()
    dragging = true
  }

  async function remove(id: string) {
    const res = await call('library_remove', id)
    if (!res.ok) return pushToast({ kind: 'error', text: '', error: res.error })
    selected = null
    await loadLibrary()
  }

  const sourceLabel = (e: LibraryEntry) => (e.source === 'file' ? t('library.source_file') : hostOf(e.source))
</script>

<svelte:window
  ondragover={onDragOver}
  ondragleave={(e) => e.relatedTarget === null && (dragging = false)}
  ondrop={onDrop}
/>

<ViewShell title={t('nav.library')} count={$libraryStatus === 'ready' ? $library.length : undefined}>
  {#snippet actions()}
    <button type="button" class="btn btn-primary" disabled={busy} onclick={addFiles}>{t('library.add')}</button>
  {/snippet}

  {#if dragging}
    <div class="drop rise" aria-hidden="true">
      <div class="font-display text-[15px] font-bold text-accent">{t('library.drop_here')}</div>
    </div>
  {/if}

  {#if error}<div class="mb-4"><ErrorBox {error} /></div>{/if}

  {#if $libraryStatus !== 'ready'}
    <SkeletonList rows={3} />
  {:else if $library.length === 0}
    <EmptyState glyph="▤" title={t('library.empty_title')} text={t('library.empty_text')}>
      {#snippet action()}
        <button type="button" class="btn btn-primary" disabled={busy} onclick={addFiles}>{t('library.add')}</button>
      {/snippet}
    </EmptyState>
  {:else}
    <AppList items={$library} key={(e) => e.id} {selected} onSelect={(id) => (selected = id)} label={t('library.list')}>
      {#snippet row(e: LibraryEntry)}
        <div class="flex items-center gap-3 p-3">
          <AppIcon name={e.name} src={icons[e.id]} size={42} />
          <div class="min-w-0 flex-1">
            <div class="truncate text-[14px] font-semibold">{e.name}</div>
            <div class="truncate font-display text-[11px] text-muted">{e.bundle_id} · {e.version}</div>
          </div>
          <span class="pill shrink-0">{sourceLabel(e)}</span>
        </div>
      {/snippet}
    </AppList>
    <p class="mt-5 mb-0 text-center text-[12px] text-muted">{t('library.drop_hint')}</p>
  {/if}

  {#snippet detail()}
    {#if entry}
      {#key entry.id}
        <div class="rise flex flex-col gap-5">
          <header class="flex items-center gap-4">
            <AppIcon name={entry.name} src={icons[entry.id]} size={64} glow />
            <div class="min-w-0">
              <h3 class="m-0 truncate font-display text-[20px] font-bold tracking-tight">{entry.name}</h3>
              <p class="mt-1 mb-0 truncate font-display text-[11px] text-muted">{entry.version} · {sourceLabel(entry)}</p>
            </div>
          </header>
          <SignPanel {entry} />
          <div class="border-t border-line pt-4">
            {#if confirmRemove}
              <p class="m-0 mb-3 text-[13px]">{t(entry.owned ? 'library.remove_confirm' : 'library.remove_confirm_keep')}</p>
              <div class="flex gap-2">
                <button type="button" class="btn" onclick={() => remove(entry.id)}>{t('common.remove')}</button>
                <button type="button" class="btn" onclick={() => (confirmRemove = false)}>{t('common.cancel')}</button>
              </div>
            {:else}
              <button type="button" class="btn" onclick={() => (confirmRemove = true)}>{t('common.remove')}</button>
            {/if}
          </div>
        </div>
      {/key}
    {:else}
      <p class="m-0 text-[13px] text-muted">{t('library.select_prompt')}</p>
    {/if}
  {/snippet}
</ViewShell>

<style>
  .drop {
    position: fixed;
    inset: 12px;
    z-index: 40;
    display: grid;
    place-items: center;
    border: 2px dashed var(--color-accent);
    border-radius: 18px;
    background: rgb(11 11 11 / 0.82);
    backdrop-filter: blur(4px);
    pointer-events: none;
  }
</style>
