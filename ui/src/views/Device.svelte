<script lang="ts">
  import { onMount } from 'svelte'
  import AppList from '../components/AppList.svelte'
  import DeviceAppDetail from '../components/DeviceAppDetail.svelte'
  import DeviceHelp from '../components/DeviceHelp.svelte'
  import ErrorBox from '../components/ErrorBox.svelte'
  import SkeletonList from '../components/SkeletonList.svelte'
  import ViewShell from '../components/ViewShell.svelte'
  import { call, type WispErr } from '../lib/api'
  import { matchesQuery } from '../lib/format'
  import { t } from '../lib/i18n'
  import { scanDevices, type DeviceScan } from '../lib/stores'
  import type { DeviceApp } from '../lib/types'

  let scan = $state<DeviceScan | null>(null)
  let scanning = $state(false)
  let udid = $state<string | null>(null)
  let apps = $state<DeviceApp[] | null>(null)
  let appsError = $state<WispErr | null>(null)
  let selected = $state<string | null>(null)
  let query = $state('')

  const device = $derived(scan?.devices.find((d) => d.udid === udid) ?? null)
  const showHelp = $derived(
    !!scan && (scan.error?.code === 'error.usbmux_missing' || (!scan.error && scan.devices.length === 0)),
  )
  const visible = $derived((apps ?? []).filter((a) => matchesQuery(query, [a.name, a.bundle_id])))
  const app = $derived(apps?.find((a) => a.bundle_id === selected) ?? null)

  async function rescan() {
    scanning = true
    scan = await scanDevices()
    scanning = false
    if (!scan.devices.some((d) => d.udid === udid)) udid = scan.devices[0]?.udid ?? null
    await loadApps()
  }

  async function loadApps() {
    apps = null
    appsError = null
    selected = null
    if (!udid) return
    const res = await call<DeviceApp[]>('device_apps', udid)
    if (res.ok) {
      apps = res.data
    } else {
      apps = []
      appsError = res.error
    }
  }

  function removed(bundleId: string) {
    apps = (apps ?? []).filter((a) => a.bundle_id !== bundleId)
    selected = null
  }

  onMount(rescan)
</script>

<ViewShell title={t('nav.device')} count={apps && device ? apps.length : undefined}>
  {#snippet actions()}
    <button type="button" class="btn" disabled={scanning} onclick={rescan}>{t('common.refresh')}</button>
  {/snippet}

  {#if !scan}
    <SkeletonList rows={3} />
  {:else if showHelp}
    <DeviceHelp usbmuxMissing={scan.error?.code === 'error.usbmux_missing'} busy={scanning} onRetry={rescan} />
  {:else if scan.error}
    <ErrorBox error={scan.error} />
    <button type="button" class="btn mt-4" disabled={scanning} onclick={rescan}>{t('common.retry')}</button>
  {:else if device}
    <div class="hero rise mb-6 flex items-center gap-4 p-4">
      <div class="phone" aria-hidden="true"></div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h2 class="m-0 truncate font-display text-[17px] font-bold tracking-tight">{device.name}</h2>
          <span class="live"><span class="dot" aria-hidden="true"></span>{t('device.connected')}</span>
        </div>
        <p class="mt-1 mb-0 font-display text-[12px] text-muted">iOS {device.ios} · {device.model}</p>
      </div>
      {#if scan.devices.length > 1}
        <select
          class="field text-[12px]"
          aria-label={t('device.pick')}
          value={udid}
          onchange={(e) => {
            udid = e.currentTarget.value
            void loadApps()
          }}
        >
          {#each scan.devices as d (d.udid)}<option value={d.udid}>{d.name}</option>{/each}
        </select>
      {/if}
    </div>

    <div class="mb-3 flex items-center justify-between gap-3">
      <h3 class="label m-0">{t('device.apps')}</h3>
      <input class="field w-[220px] text-[13px]" type="search" placeholder={t('device.search')} aria-label={t('device.search')} bind:value={query} />
    </div>
    {#if appsError}<div class="mb-3"><ErrorBox error={appsError} /></div>{/if}
    {#if apps === null}
      <SkeletonList rows={3} />
    {:else if visible.length === 0}
      <p class="m-0 py-8 text-center text-[13px] text-muted">{apps.length ? t('device.no_match') : t('device.no_apps')}</p>
    {:else}
      <AppList items={visible} key={(a) => a.bundle_id} {selected} onSelect={(id) => (selected = id)} label={t('device.apps')}>
        {#snippet row(a: DeviceApp)}
          <div class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <div class="truncate text-[14px] font-semibold">{a.name}</div>
              <div class="truncate font-display text-[11px] text-muted">{a.version}</div>
            </div>
            <span class="pill shrink-0" class:off={!a.has_push}>{a.has_push ? t('certs.push_yes') : t('certs.push_no')}</span>
          </div>
        {/snippet}
      </AppList>
    {/if}
  {/if}

  {#snippet detail()}
    {#if app && udid}
      {#key app.bundle_id}
        <DeviceAppDetail {app} {udid} onRemoved={removed} />
      {/key}
    {:else}
      <p class="m-0 text-[13px] text-muted">{t('device.select_prompt')}</p>
    {/if}
  {/snippet}
</ViewShell>

<style>
  .hero {
    border-radius: 16px;
    border: 1px solid var(--color-line-strong);
    background:
      radial-gradient(80% 140% at 0% 0%, rgb(198 255 61 / 0.08), transparent 60%),
      var(--color-raised);
  }
  .phone {
    width: 34px;
    height: 56px;
    border-radius: 9px;
    border: 2px solid var(--color-accent);
    box-shadow: 0 0 24px -4px rgb(198 255 61 / 0.6);
  }
  .live {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-display);
    font-size: 11px;
    color: var(--color-accent);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 999px;
    background: var(--color-accent);
    animation: pulse-dot 1.6s ease-in-out infinite;
  }
  .pill.off {
    color: var(--color-warn);
    background: rgb(255 194 71 / 0.1);
  }
</style>
