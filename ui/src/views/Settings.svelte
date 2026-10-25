<script lang="ts">
  import { onMount } from 'svelte'
  import ErrorBox from '../components/ErrorBox.svelte'
  import ViewShell from '../components/ViewShell.svelte'
  import { call, type WispErr } from '../lib/api'
  import { formatSize, isAbsoluteDir } from '../lib/format'
  import { locale, setLocale, t, type Locale } from '../lib/i18n'
  import { pushToast } from '../lib/toast'
  import type { Settings } from '../lib/types'

  type Update = { current: string; status: 'available' | 'current' | 'failed'; latest: string | null }

  const UPDATE_TEXT = { available: 'settings.update_available', current: 'settings.up_to_date', failed: 'settings.update_failed' }

  const LANGUAGES: { id: Locale; label: string }[] = [
    { id: 'tr', label: 'Türkçe' },
    { id: 'en', label: 'English' },
  ]

  let version = $state('')
  let updatesEnabled = $state(false) // the build has a release repo to check
  let dir = $state('')
  let savedDir = $state('')
  let dirError = $state<string | null>(null)
  let saveError = $state<WispErr | null>(null)
  let saving = $state(false)
  let checking = $state(false)
  let update = $state<Update | null>(null)
  let updateError = $state<WispErr | null>(null)
  let confirmClear = $state(false)
  let clearing = $state(false)
  let clearError = $state<WispErr | null>(null)

  onMount(async () => {
    const res = await call<{ version: string; settings: Settings; updates: boolean }>('get_state')
    if (!res.ok) return (saveError = res.error)
    version = res.data.version
    updatesEnabled = res.data.updates
    dir = savedDir = res.data.settings.download_dir
  })

  async function saveDir(event: SubmitEvent) {
    event.preventDefault()
    saveError = null
    const value = dir.trim()
    dirError = isAbsoluteDir(value) ? null : t('settings.dir_invalid')
    if (dirError) return
    saving = true
    const res = await call<Settings>('settings_set', { download_dir: value })
    saving = false
    if (!res.ok) return (saveError = res.error)
    dir = savedDir = res.data.download_dir
    pushToast({ kind: 'info', text: t('settings.saved') })
  }

  async function pickFolder() {
    const res = await call<string | null>('pick_folder')
    if (!res.ok) return (saveError = res.error)
    if (!res.data) return
    dir = res.data // still validated and saved with "Kaydet"
    dirError = null
  }

  async function clearCache() {
    clearing = true
    clearError = null
    const res = await call<number>('cache_clear')
    clearing = false
    confirmClear = false
    if (!res.ok) return (clearError = res.error)
    pushToast({ kind: 'info', text: t('settings.cache_cleared', { size: formatSize(res.data) ?? '0 B' }) })
  }

  async function checkUpdate() {
    checking = true
    updateError = null
    const res = await call<Update>('check_update')
    checking = false
    if (res.ok) update = res.data
    else updateError = res.error
  }
</script>

<ViewShell title={t('nav.settings')}>
  <div class="flex max-w-[620px] flex-col gap-4">
    <section class="card" aria-labelledby="set-lang">
      <div>
        <h2 id="set-lang" class="title">{t('settings.language')}</h2>
        <p class="hint">{t('settings.language_hint')}</p>
      </div>
      <div class="segmented" role="group" aria-labelledby="set-lang">
        {#each LANGUAGES as lang (lang.id)}
          <button type="button" aria-pressed={$locale === lang.id} onclick={() => setLocale(lang.id)}>{lang.label}</button>
        {/each}
      </div>
    </section>

    <section class="card flex-col !items-stretch" aria-labelledby="set-dir">
      <div>
        <h2 id="set-dir" class="title">{t('settings.download_dir')}</h2>
        <p class="hint">{t('settings.download_dir_hint')}</p>
      </div>
      <form class="flex gap-2" novalidate onsubmit={saveDir}>
        <input
          class="field min-w-0 flex-1 font-display text-[12px]"
          aria-label={t('settings.download_dir')}
          aria-invalid={!!dirError}
          aria-describedby={dirError ? 'dir-error' : undefined}
          spellcheck="false"
          bind:value={dir}
          oninput={() => (dirError = null)}
        />
        <button type="button" class="btn shrink-0" onclick={pickFolder}>{t('settings.dir_pick')}</button>
        <button type="submit" class="btn btn-primary" disabled={saving || dir.trim() === savedDir}>{t('common.save')}</button>
      </form>
      {#if dirError}<p id="dir-error" class="m-0 text-[12px] text-danger">{dirError}</p>{/if}
      {#if saveError}<ErrorBox error={saveError} />{/if}
    </section>

    <section class="card flex-col !items-stretch" aria-labelledby="set-cache">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 id="set-cache" class="title">{t('settings.cache')}</h2>
          <p class="hint">{t('settings.cache_hint')}</p>
        </div>
        {#if !confirmClear}
          <button type="button" class="btn shrink-0" onclick={() => (confirmClear = true)}>{t('settings.cache_clear')}</button>
        {/if}
      </div>
      {#if confirmClear}
        <div class="confirm rise flex items-center justify-between gap-3">
          <p class="m-0 text-[13px]">{t('settings.cache_confirm')}</p>
          <div class="flex shrink-0 gap-2">
            <button type="button" class="btn btn-primary" disabled={clearing} onclick={clearCache}>
              {t('settings.cache_confirm_button')}
            </button>
            <button type="button" class="btn" disabled={clearing} onclick={() => (confirmClear = false)}>
              {t('common.cancel')}
            </button>
          </div>
        </div>
      {/if}
      {#if clearError}<ErrorBox error={clearError} />{/if}
    </section>

    <section class="card" aria-labelledby="set-ver">
      <div class="min-w-0">
        <h2 id="set-ver" class="title">{t('settings.version')}</h2>
        <p class="hint">
          <span class="font-display text-ink">{version ? `v${version}` : '…'}</span>
          {#if update}
            <span class:text-danger={update.status === 'failed'}>
              · {t(UPDATE_TEXT[update.status], { version: update.latest ?? '' })}
            </span>
          {/if}
        </p>
      </div>
      {#if updatesEnabled}
        <button type="button" class="btn" disabled={checking} onclick={checkUpdate}>
          {checking ? t('settings.checking') : t('settings.check_update')}
        </button>
      {/if}
    </section>
    {#if updateError}<ErrorBox error={updateError} />{/if}
  </div>

  {#snippet detail()}
    <div class="rise flex flex-col items-start gap-4">
      <div class="logo" aria-hidden="true">◆</div>
      <div>
        <h3 class="m-0 font-display text-[20px] font-bold tracking-tight">{t('app.name')}</h3>
        <p class="mt-1 mb-0 text-[13px] text-muted">{t('app.tagline')}</p>
      </div>
      <p class="m-0 text-[12px] leading-relaxed text-muted">{t('settings.about')}</p>
    </div>
  {/snippet}
</ViewShell>

<style>
  .card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 18px 20px;
    border-radius: 14px;
    border: 1px solid var(--color-line);
    background: #111;
  }
  .title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 700;
  }
  .hint {
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--color-muted);
  }
  .segmented {
    display: inline-flex;
    padding: 3px;
    border-radius: 10px;
    border: 1px solid var(--color-line-strong);
    background: var(--color-bg);
  }
  .segmented button {
    border: 0;
    padding: 6px 14px;
    border-radius: 7px;
    background: transparent;
    color: var(--color-muted);
    font-family: var(--font-display);
    font-size: 12px;
    cursor: pointer;
    transition:
      color 160ms,
      background-color 160ms;
  }
  .segmented button:hover {
    color: var(--color-ink);
  }
  .segmented button[aria-pressed='true'] {
    color: var(--color-bg);
    background: var(--color-accent);
    font-weight: 700;
  }
  .confirm {
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid var(--color-line-strong);
    background: var(--color-raised);
  }
  .logo {
    display: grid;
    place-items: center;
    width: 64px;
    height: 64px;
    border-radius: 18px;
    font-size: 28px;
    color: var(--color-bg);
    background: var(--color-accent);
    box-shadow: 0 18px 48px -12px rgb(198 255 61 / 0.6);
  }
</style>
