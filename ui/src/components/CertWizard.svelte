<script lang="ts">
  import { call, type WispErr } from '../lib/api'
  import { t } from '../lib/i18n'
  import type { Cert, Warning } from '../lib/types'
  import CertWarnings from './CertWarnings.svelte'
  import ErrorBox from './ErrorBox.svelte'

  type Props = { connectedUdid: string | null; onDone: (cert: Cert) => void; onCancel: () => void }
  let { connectedUdid, onDone, onCancel }: Props = $props()

  type Stage = 'form' | 'picking' | 'verify'
  const STAGES = ['certs.wizard_info', 'certs.wizard_p12', 'certs.wizard_profile', 'certs.wizard_verify']

  let stage = $state<Stage>('form')
  let nickname = $state('')
  let password = $state('')
  let error = $state<WispErr | null>(null)
  let cancelled = $state(false)
  let imported = $state<Cert | null>(null)
  let warnings = $state<Warning[] | null>(null)
  let validateError = $state<WispErr | null>(null)

  const activeStage = $derived(stage === 'form' ? 0 : stage === 'picking' ? 1 : 3)
  const canSubmit = $derived(nickname.trim().length > 0 && stage === 'form')

  async function submit(event: SubmitEvent) {
    event.preventDefault()
    if (!canSubmit) return
    error = null
    cancelled = false
    stage = 'picking'
    const res = await call<Cert | null>('certs_import', nickname.trim(), password)
    password = ''
    if (!res.ok) {
      error = res.error
      stage = 'form'
      return
    }
    if (!res.data) {
      cancelled = true
      stage = 'form'
      return
    }
    imported = res.data
    stage = 'verify'
    const check = await call<Warning[]>('certs_validate', res.data.id, connectedUdid)
    if (check.ok) warnings = check.data
    else validateError = check.error
  }
</script>

<section class="rise flex flex-col gap-5" aria-label={t('certs.wizard_title')}>
  <header>
    <h3 class="m-0 font-display text-[18px] font-bold tracking-tight">{t('certs.wizard_title')}</h3>
    <p class="mt-1 mb-0 text-[12px] text-muted">{t('certs.wizard_hint')}</p>
  </header>

  <ol class="stepper m-0 grid list-none grid-cols-4 gap-1.5 p-0" class:busy={stage === 'picking'}>
    {#each STAGES as key, i (key)}
      <li class:done={i < activeStage} class:now={i === activeStage || (stage === 'picking' && i === 2)}>
        <span class="bar" aria-hidden="true"></span>
        <span class="font-display text-[10px]">{t(key)}</span>
      </li>
    {/each}
  </ol>

  {#if stage === 'verify' && imported}
    <div class="flex flex-col gap-3">
      <p class="m-0 font-display text-[14px] font-bold">{t('certs.imported', { name: imported.nickname })}</p>
      {#if validateError}
        <ErrorBox error={validateError} />
      {:else if warnings === null}
        <p class="m-0 text-[13px] text-muted">{t('certs.verifying')}</p>
      {:else}
        {#if warnings.length === 0 && connectedUdid}
          <p class="ok m-0">{t('certs.all_good')}</p>
        {:else}
          <CertWarnings {warnings} />
        {/if}
        {#if !connectedUdid}
          <p class="m-0 text-[13px] text-muted">{t('certs.device_unchecked')}</p>
        {/if}
      {/if}
      <button type="button" class="btn btn-primary" onclick={() => imported && onDone(imported)}>
        {t('common.done')}
      </button>
    </div>
  {:else}
    <form class="flex flex-col gap-4" onsubmit={submit}>
      <label class="flex flex-col gap-1.5">
        <span class="label">{t('certs.nickname')}</span>
        <input class="field" bind:value={nickname} maxlength="80" disabled={stage !== 'form'} required />
      </label>
      <label class="flex flex-col gap-1.5">
        <span class="label">{t('certs.password')}</span>
        <input class="field" type="password" bind:value={password} autocomplete="off" disabled={stage !== 'form'} />
      </label>
      {#if error}<ErrorBox {error} />{/if}
      {#if cancelled}<p class="m-0 text-[12px] text-muted">{t('certs.import_cancelled')}</p>{/if}
      <div class="flex gap-2">
        <button type="submit" class="btn btn-primary flex-1" disabled={!canSubmit}>
          {stage === 'picking' ? t('certs.picking') : t('certs.pick_files')}
        </button>
        <button type="button" class="btn" onclick={onCancel}>{t('common.cancel')}</button>
      </div>
    </form>
  {/if}
</section>

<style>
  .stepper li {
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: var(--color-muted);
  }
  .bar {
    height: 3px;
    border-radius: 999px;
    background: var(--color-line-strong);
    transition: background-color 200ms;
  }
  .stepper li.done .bar,
  .stepper li.now .bar {
    background: var(--color-accent);
  }
  .stepper li.now {
    color: var(--color-accent);
  }
  .stepper.busy li.now .bar {
    animation: pulse-dot 1.1s ease-in-out infinite;
  }
  .stepper li.done {
    color: var(--color-ink);
  }
  .ok {
    padding: 10px 12px;
    border-radius: 10px;
    font-size: 13px;
    color: var(--color-accent);
    background: var(--color-accent-dark);
  }
</style>
