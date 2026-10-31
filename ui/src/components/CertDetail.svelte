<script lang="ts">
  import { call, type WispErr } from '../lib/api'
  import { coversDevice } from '../lib/certRules'
  import { formatDate } from '../lib/format'
  import { locale, t } from '../lib/i18n'
  import { pushToast } from '../lib/toast'
  import type { Cert, Warning } from '../lib/types'
  import CertWarnings from './CertWarnings.svelte'
  import ErrorBox from './ErrorBox.svelte'

  type Props = { cert: Cert; connectedUdid: string | null; onRemoved: (id: string) => void }
  let { cert, connectedUdid, onRemoved }: Props = $props()

  let warnings = $state<Warning[]>([])
  let validateError = $state<WispErr | null>(null)
  let confirming = $state(false)
  let removing = $state(false)

  $effect(() => {
    let stale = false
    warnings = []
    validateError = null
    if (cert.broken) return
    void call<Warning[]>('certs_validate', cert.id, connectedUdid).then((res) => {
      if (stale) return
      if (res.ok) warnings = res.data
      else validateError = res.error
    })
    return () => {
      stale = true
    }
  })

  async function remove() {
    removing = true
    const res = await call('certs_remove', cert.id)
    removing = false
    if (!res.ok) {
      pushToast({ kind: 'error', text: '', error: res.error })
      return
    }
    pushToast({ kind: 'info', text: t('certs.removed') })
    onRemoved(cert.id)
  }
</script>

<article class="rise flex flex-col gap-5">
  <header>
    <div class="seal mb-4" aria-hidden="true">◉</div>
    <h3 class="m-0 font-display text-[20px] leading-tight font-bold tracking-tight break-words">{cert.nickname}</h3>
    <p class="mt-1 mb-0 text-[12px] break-words text-muted">{cert.common_name}</p>
  </header>

  {#if cert.broken}
    <p class="m-0 text-[13px] text-danger" role="alert">{t('certs.broken_text')}</p>
  {:else}
    <CertWarnings {warnings} />
    {#if validateError}<ErrorBox error={validateError} />{/if}

    <dl class="m-0 grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
      <div>
        <dt class="label">{t('certs.team')}</dt>
        <dd class="font-display">{cert.team_id}</dd>
      </div>
      <div>
        <dt class="label">{t('certs.push')}</dt>
        <dd class:text-accent={cert.has_push} class:text-warn={!cert.has_push}>
          {cert.has_push ? t('certs.push_yes') : t('certs.push_no')}
        </dd>
      </div>
      <div>
        <dt class="label">{t('certs.expires')}</dt>
        <dd>{formatDate(cert.expires, $locale)}</dd>
      </div>
      <div>
        <dt class="label">{t('certs.added')}</dt>
        <dd>{formatDate(cert.added_at, $locale)}</dd>
      </div>
      <div class="col-span-2">
        <dt class="label">{t('certs.app_id')}</dt>
        <dd class="font-display text-[12px] break-all">{cert.app_id}</dd>
      </div>
    </dl>

    <section>
      <h4 class="label m-0 mb-2">
        {cert.all_devices ? t('certs.all_devices') : cert.devices.length ? t('certs.devices_count', { count: cert.devices.length }) : t('certs.no_devices')}
      </h4>
      {#if cert.all_devices}
        <p class="m-0 text-[12px] text-muted">{t('certs.all_devices_text')}</p>
      {:else if cert.devices.length}
        <ul class="m-0 flex list-none flex-col gap-1 p-0">
          {#each cert.devices as udid (udid)}
            {@const current = connectedUdid !== null && coversDevice([udid], connectedUdid)}
            <li class="udid" class:current>
              <span class="truncate">{udid}</span>
              {#if current}<span class="pill">{t('certs.this_device')}</span>{/if}
            </li>
          {/each}
        </ul>
      {:else}
        <p class="m-0 text-[12px] text-muted">{t('certs.no_devices_text')}</p>
      {/if}
    </section>
  {/if}

  <div class="border-t border-line pt-4">
    {#if confirming}
      <p class="m-0 mb-3 text-[13px]">{t('certs.remove_confirm')}</p>
      <div class="flex gap-2">
        <button type="button" class="btn danger" disabled={removing} onclick={remove}>{t('common.remove')}</button>
        <button type="button" class="btn" onclick={() => (confirming = false)}>{t('common.cancel')}</button>
      </div>
    {:else}
      <button type="button" class="btn" onclick={() => (confirming = true)}>{t('common.remove')}</button>
    {/if}
  </div>
</article>

<style>
  .seal {
    display: grid;
    place-items: center;
    width: 64px;
    height: 64px;
    border-radius: 18px;
    font-size: 28px;
    color: var(--color-accent);
    background: var(--color-accent-dark);
    box-shadow:
      inset 0 0 0 1px rgb(198 255 61 / 0.25),
      0 18px 48px -14px rgb(198 255 61 / 0.45);
  }
  dd {
    margin: 3px 0 0;
  }
  .udid {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 8px;
    font-family: var(--font-display);
    font-size: 11px;
    color: var(--color-muted);
    background: var(--color-raised);
  }
  .udid.current {
    color: var(--color-ink);
    box-shadow: inset 0 0 0 1px rgb(198 255 61 / 0.3);
  }
  .danger:hover {
    border-color: var(--color-danger);
    color: var(--color-danger);
  }
</style>
