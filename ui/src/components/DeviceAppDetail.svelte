<script lang="ts">
  import { call } from '../lib/api'
  import { t } from '../lib/i18n'
  import { pushToast } from '../lib/toast'
  import type { DeviceApp } from '../lib/types'
  import AppIcon from './AppIcon.svelte'

  type Props = { app: DeviceApp; udid: string; onRemoved: (bundleId: string) => void }
  let { app, udid, onRemoved }: Props = $props()

  let confirming = $state(false)
  let busy = $state(false)

  async function uninstall() {
    busy = true
    const res = await call('device_uninstall', udid, app.bundle_id)
    busy = false
    if (!res.ok) return pushToast({ kind: 'error', text: '', error: res.error })
    pushToast({ kind: 'info', text: t('device.removed') })
    onRemoved(app.bundle_id)
  }
</script>

<article class="rise flex flex-col gap-5">
  <header class="flex flex-col items-start gap-4">
    <AppIcon name={app.name} size={72} glow />
    <div class="min-w-0">
      <h3 class="m-0 font-display text-[20px] font-bold tracking-tight break-words">{app.name}</h3>
      <p class="mt-1 mb-0 font-display text-[12px] break-all text-muted">{app.bundle_id}</p>
    </div>
  </header>

  <dl class="m-0 grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
    <div>
      <dt class="label">{t('app.version')}</dt>
      <dd class="font-display">{app.version || '—'}</dd>
    </div>
    <div>
      <dt class="label">{t('certs.push')}</dt>
      <dd class:text-accent={app.has_push} class:text-warn={!app.has_push}>
        {app.has_push ? t('certs.push_yes') : t('certs.push_no')}
      </dd>
    </div>
    <div class="col-span-2">
      <dt class="label">{t('device.signer')}</dt>
      <dd class="break-words">{app.signer ?? '—'}</dd>
    </div>
    <div class="col-span-2">
      <dt class="label">{t('certs.app_id')}</dt>
      <dd class="font-display text-[12px] break-all">{app.app_id ?? '—'}</dd>
    </div>
  </dl>

  <div class="border-t border-line pt-4">
    {#if confirming}
      <p class="m-0 mb-3 text-[13px]">{t('device.uninstall_confirm')}</p>
      <div class="flex gap-2">
        <button type="button" class="btn danger" disabled={busy} onclick={uninstall}>
          {busy ? t('device.uninstalling') : t('device.uninstall')}
        </button>
        <button type="button" class="btn" disabled={busy} onclick={() => (confirming = false)}>{t('common.cancel')}</button>
      </div>
    {:else}
      <button type="button" class="btn" onclick={() => (confirming = true)}>{t('device.uninstall')}</button>
    {/if}
  </div>
</article>

<style>
  dd {
    margin: 3px 0 0;
  }
  .danger:hover {
    border-color: var(--color-danger);
    color: var(--color-danger);
  }
</style>
