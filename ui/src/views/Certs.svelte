<script lang="ts">
  import { onMount } from 'svelte'
  import AppList from '../components/AppList.svelte'
  import CertCard from '../components/CertCard.svelte'
  import CertDetail from '../components/CertDetail.svelte'
  import CertWizard from '../components/CertWizard.svelte'
  import EmptyState from '../components/EmptyState.svelte'
  import ErrorBox from '../components/ErrorBox.svelte'
  import SkeletonList from '../components/SkeletonList.svelte'
  import ViewShell from '../components/ViewShell.svelte'
  import { call, type WispErr } from '../lib/api'
  import { t } from '../lib/i18n'
  import { scanDevices } from '../lib/stores'
  import type { Cert } from '../lib/types'

  let certs = $state<Cert[] | null>(null)
  let error = $state<WispErr | null>(null)
  let selected = $state<string | null>(null)
  let wizard = $state(false)
  let udid = $state<string | null>(null)

  const cert = $derived(certs?.find((c) => c.id === selected) ?? null)

  async function load() {
    const res = await call<Cert[]>('certs_list')
    if (res.ok) {
      certs = res.data
      error = null
    } else {
      certs = certs ?? []
      error = res.error
    }
  }

  onMount(() => {
    void load()
    void scanDevices().then((scan) => (udid = scan.devices[0]?.udid ?? null))
  })

  function openWizard() {
    selected = null
    wizard = true
  }

  async function imported(added: Cert) {
    wizard = false
    await load()
    selected = added.id
  }

  function removed(id: string) {
    certs = (certs ?? []).filter((c) => c.id !== id)
    selected = null
  }
</script>

<ViewShell title={t('nav.certs')} count={certs?.length}>
  {#snippet actions()}
    <button type="button" class="btn btn-primary" disabled={wizard} onclick={openWizard}>{t('certs.add')}</button>
  {/snippet}

  {#if error}<div class="mb-4"><ErrorBox {error} /></div>{/if}

  {#if certs === null}
    <SkeletonList rows={2} />
  {:else if certs.length === 0}
    <EmptyState glyph="◉" title={t('certs.empty_title')} text={t('certs.empty_text')}>
      {#snippet action()}
        {#if !wizard}
          <button type="button" class="btn btn-primary" onclick={openWizard}>{t('certs.add')}</button>
        {/if}
      {/snippet}
    </EmptyState>
  {:else}
    <AppList
      items={certs}
      key={(c) => c.id}
      {selected}
      onSelect={(id) => ((selected = id), (wizard = false))}
      label={t('certs.list')}
      layout="grid"
    >
      {#snippet row(c: Cert)}
        <CertCard cert={c} connectedUdid={udid} />
      {/snippet}
    </AppList>
  {/if}

  {#snippet detail()}
    {#if wizard}
      <CertWizard connectedUdid={udid} onDone={imported} onCancel={() => (wizard = false)} />
    {:else if cert}
      {#key cert.id}
        <CertDetail {cert} connectedUdid={udid} onRemoved={removed} />
      {/key}
    {:else}
      <p class="m-0 text-[13px] text-muted">{t('certs.select_prompt')}</p>
    {/if}
  {/snippet}
</ViewShell>
