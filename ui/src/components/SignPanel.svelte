<script lang="ts">
  import { onMount } from 'svelte'
  import { call, type WispErr } from '../lib/api'
  import { BLOCKING_CERT_WARNINGS } from '../lib/certRules'
  import { isValidBundleId } from '../lib/format'
  import { t } from '../lib/i18n'
  import { clearJob, jobs, trackJob } from '../lib/jobs'
  import { activeView, scanDevices, type DeviceScan } from '../lib/stores'
  import type { Cert, LibraryEntry, Warning } from '../lib/types'
  import CertWarnings from './CertWarnings.svelte'
  import ErrorBox from './ErrorBox.svelte'
  import ProgressSteps from './ProgressSteps.svelte'

  type Props = { entry: LibraryEntry }
  let { entry }: Props = $props()

  const STEPS = ['extract', 'sign', 'verify', 'pack', 'install']

  let certs = $state<Cert[] | null>(null)
  let scan = $state<DeviceScan | null>(null)
  let certId = $state('')
  let bundleMode = $state<'keep' | 'change'>('keep')
  let bundleId = $state('')
  let displayName = $state('')
  let iconPath = $state<string | null>(null)
  let warnings = $state<Warning[]>([])
  let certsError = $state<WispErr | null>(null)
  let validateError = $state<WispErr | null>(null)
  let validatedFor = $state<string | null>(null)
  let advancedOpen = $state(false)

  const device = $derived(scan?.devices[0] ?? null)
  const jobKey = $derived(`sign:${entry.id}`)
  const job = $derived($jobs[jobKey])
  const running = $derived(job?.status === 'running')
  const bundleInvalid = $derived(bundleMode === 'change' && !isValidBundleId(bundleId.trim()))
  const iconName = $derived(iconPath?.split(/[\\/]/).pop() ?? '')

  const customized = $derived(bundleMode === 'change' || !!displayName.trim() || !!iconPath)

  const targetBundleId = $derived(bundleMode === 'change' && !bundleInvalid ? bundleId.trim() : entry.bundle_id)
  const validationKey = $derived(JSON.stringify([certId, device?.udid ?? null, targetBundleId]))
  const canSign = $derived(
    !!device && !!certId && !running && !bundleInvalid && !validateError &&
    validatedFor === validationKey && !warnings.some((w) => BLOCKING_CERT_WARNINGS.has(w.code)),
  )

  async function loadDevices() {
    scan = null
    scan = await scanDevices()
  }

  async function loadCerts() {
    certsError = null
    const res = await call<Cert[]>('certs_list')
    if (!res.ok) {
      certsError = res.error
      return
    }
    certs = res.data.filter((c) => !c.broken)
    if (!certs.some((c) => c.id === certId)) certId = certs[0]?.id ?? ''
  }

  onMount(async () => {
    bundleId = entry.bundle_id
    await Promise.all([loadCerts(), loadDevices()])
  })

  $effect(() => {
    const id = certId
    const udid = device?.udid ?? null
    const bundle = targetBundleId
    const key = validationKey
    warnings = []
    validateError = null
    validatedFor = null
    if (!id) return
    let stale = false
    void call<Warning[]>('certs_validate', id, udid, bundle).then((res) => {
      if (stale) return
      if (res.ok) {
        warnings = res.data
        validatedFor = key
      }
      else validateError = res.error
    })
    return () => {
      stale = true
    }
  })

  async function pickIcon() {
    const res = await call<string | null>('pick_icon')
    if (res.ok && res.data) iconPath = res.data
  }

  function sign() {
    if (!canSign || !device) return
    void trackJob(jobKey, 'sign_and_install', [
      entry.id,
      certId,
      device.udid,
      displayName.trim() || null,
      bundleMode === 'change' ? bundleId.trim() : null,
      iconPath,
    ])
  }
</script>

<section class="flex flex-col gap-4" aria-label={t('sign.title')}>
  <div class="device" class:missing={scan && !device}>
    <span class="dot" aria-hidden="true"></span>
    <div class="min-w-0 flex-1">
      <div class="label">{t('sign.target')}</div>
      {#if !scan}
        <div class="text-[13px] text-muted">{t('device.searching')}</div>
      {:else if device}
        <div class="truncate text-[13px]">{device.name} · iOS {device.ios}</div>
      {:else}
        <div class="text-[13px]">{t('sign.no_device')}</div>
      {/if}
    </div>
    <button type="button" class="icon-btn" aria-label={t('common.refresh')} onclick={loadDevices}>↻</button>
  </div>
  {#if scan?.error}<ErrorBox error={scan.error} />{/if}

  {#if certsError}
    <div class="flex flex-col gap-2">
      <ErrorBox error={certsError} />
      <button type="button" class="btn self-start" onclick={loadCerts}>{t('common.retry')}</button>
    </div>
  {:else if certs && certs.length === 0}
    <div class="rounded-xl border border-line p-4 text-[13px]">
      <p class="m-0 mb-3 text-muted">{t('sign.no_certs')}</p>
      <button type="button" class="btn" onclick={() => activeView.set('certs')}>{t('certs.add')}</button>
    </div>
  {:else}
    <label class="flex flex-col gap-1.5">
      <span class="label">{t('sign.cert')}</span>
      <select class="field" bind:value={certId} disabled={!certs || running}>
        {#each certs ?? [] as cert (cert.id)}
          <option value={cert.id}>{cert.nickname}</option>
        {/each}
      </select>
    </label>
    <CertWarnings {warnings} />
    {#if validateError}<ErrorBox error={validateError} />{/if}
  {/if}

  <button
    type="button"
    class="disclosure"
    aria-expanded={advancedOpen}
    aria-controls="sign-advanced"
    onclick={() => (advancedOpen = !advancedOpen)}
  >
    <span class="chevron" aria-hidden="true">›</span>
    <span class="label">{t('sign.advanced')}</span>
    {#if customized && !advancedOpen}<span class="pill">{t('sign.advanced_customized')}</span>{/if}
  </button>

  {#if advancedOpen}
  <div id="sign-advanced" class="rise flex flex-col gap-4">
  <fieldset class="m-0 flex flex-col gap-2 border-0 p-0" disabled={running}>
    <legend class="label mb-1.5 p-0">{t('app.bundle_id')}</legend>
    <div class="segmented" role="radiogroup">
      <label><input type="radio" bind:group={bundleMode} value="keep" />{t('sign.bundle_keep')}</label>
      <label><input type="radio" bind:group={bundleMode} value="change" />{t('sign.bundle_change')}</label>
    </div>
    {#if bundleMode === 'keep'}
      <p class="m-0 font-display text-[12px] break-all text-muted">{entry.bundle_id}</p>
    {:else}
      <input
        class="field font-display text-[12px]"
        aria-label={t('sign.bundle_new')}
        aria-invalid={bundleInvalid}
        bind:value={bundleId}
        spellcheck="false"
      />
      {#if bundleInvalid}
        <p class="m-0 text-[12px] text-danger">{t('sign.bundle_invalid')}</p>
      {/if}
    {/if}
  </fieldset>

  <label class="flex flex-col gap-1.5">
    <span class="label">{t('sign.name')}</span>
    <input class="field" bind:value={displayName} placeholder={entry.name} disabled={running} />
  </label>

  <div class="flex flex-col gap-1.5">
    <span class="label">{t('sign.icon')}</span>
    <div class="flex items-center gap-2">
      <button type="button" class="btn" onclick={pickIcon} disabled={running}>{t('sign.icon_pick')}</button>
      {#if iconPath}
        <span class="min-w-0 flex-1 truncate font-display text-[12px] text-muted" title={iconPath}>{iconName}</span>
        <button type="button" class="icon-btn" aria-label={t('sign.icon_clear')} onclick={() => (iconPath = null)}>×</button>
      {:else}
        <span class="text-[12px] text-muted">{t('sign.icon_none')}</span>
      {/if}
    </div>
  </div>
  </div>
  {/if}

  <div class="mt-1 flex flex-col gap-3 border-t border-line pt-4">
    {#if job?.status === 'done'}
      <div class="done rise" data-testid="job-done" role="status">
        <span class="check" aria-hidden="true">✓</span>
        <div>
          <div class="font-display text-[13px] font-bold">{t('sign.done')}</div>
          <div class="text-[12px] text-muted">{t('sign.done_hint')}</div>
        </div>
      </div>
      <button type="button" class="btn" onclick={() => clearJob(jobKey)}>{t('sign.again')}</button>
    {:else}
      {#if job?.status === 'running'}
        <ProgressSteps steps={STEPS} current={job.step ?? 'extract'} percent={job.step === 'install' ? job.percent : undefined} />
      {:else if job?.status === 'error'}
        <ErrorBox error={job.error} />
      {/if}
      <button type="button" class="btn btn-primary cta" disabled={!canSign} onclick={sign}>
        {running ? t('sign.running') : t('sign.submit')}
      </button>
      {#if scan && !device}
        <p class="m-0 text-[12px] text-muted">{t('sign.need_device')}</p>
      {/if}
    {/if}
  </div>
</section>

<style>
  .device {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 12px;
    border: 1px solid var(--color-line-strong);
    background: var(--color-raised);
  }
  .device .dot {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    flex: none;
    background: var(--color-accent);
    box-shadow: 0 0 6px rgb(198 255 61 / 0.7);
  }
  .device.missing {
    border-color: rgb(255 107 94 / 0.35);
  }
  .device.missing .dot {
    background: var(--color-danger);
    box-shadow: 0 0 6px rgb(255 107 94 / 0.7);
  }
  .icon-btn {
    border: 1px solid transparent;
    background: transparent;
    color: var(--color-muted);
    border-radius: 8px;
    width: 28px;
    height: 28px;
    cursor: pointer;
    font-size: 15px;
    transition:
      color 160ms,
      border-color 160ms,
      transform 200ms var(--ease-out-quint);
  }
  .icon-btn:hover {
    color: var(--color-accent);
    border-color: var(--color-line-strong);
  }
  .icon-btn:active {
    transform: rotate(-45deg) scale(0.92);
  }
  .disclosure {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    border: 0;
    background: transparent;
    color: var(--color-ink);
    cursor: pointer;
    text-align: left;
  }
  .disclosure:hover .label,
  .disclosure:hover .chevron {
    color: var(--color-accent);
  }
  .chevron {
    display: inline-block;
    width: 12px;
    color: var(--color-muted);
    font-size: 15px;
    line-height: 1;
    transition:
      transform 200ms var(--ease-out-quint),
      color 160ms;
  }
  .disclosure[aria-expanded='true'] .chevron {
    transform: rotate(90deg);
  }
  .segmented {
    display: inline-grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    padding: 3px;
    border-radius: 10px;
    border: 1px solid var(--color-line-strong);
    background: var(--color-bg);
  }
  .segmented label {
    position: relative;
    text-align: center;
    padding: 6px 12px;
    border-radius: 7px;
    font-family: var(--font-display);
    font-size: 12px;
    color: var(--color-muted);
    cursor: pointer;
    transition:
      color 160ms,
      background-color 160ms;
  }
  .segmented input {
    position: absolute;
    opacity: 0;
    inset: 0;
    margin: 0;
    cursor: pointer;
  }
  .segmented label:has(input:checked) {
    color: var(--color-bg);
    background: var(--color-accent);
    font-weight: 700;
  }
  .segmented label:has(input:focus-visible) {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .cta {
    padding: 12px 14px;
    font-size: 13px;
    box-shadow: 0 10px 30px -12px rgb(198 255 61 / 0.55);
  }
  .cta:disabled {
    box-shadow: none;
    background: var(--color-raised);
    color: var(--color-muted);
  }
  .done {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--color-accent-dark);
    border: 1px solid rgb(198 255 61 / 0.35);
  }
  .check {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 999px;
    background: var(--color-accent);
    color: var(--color-bg);
    font-weight: 700;
    box-shadow: 0 0 24px rgb(198 255 61 / 0.5);
  }
</style>
