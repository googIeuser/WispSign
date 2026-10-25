<script lang="ts">
  import { certExpiry, coversDevice } from '../lib/certRules'
  import { t } from '../lib/i18n'
  import type { Cert } from '../lib/types'

  type Props = { cert: Cert; connectedUdid: string | null }
  let { cert, connectedUdid }: Props = $props()

  const YEAR_DAYS = 365
  const TONES = { ok: 'good', soon: 'soon', expired: 'bad' } as const

  const expiry = $derived(certExpiry(cert.expires))
  const days = $derived(expiry?.days ?? null)
  const tone = $derived(expiry ? TONES[expiry.state] : 'bad')
  const fill = $derived(days === null ? 0 : Math.max(0, Math.min(1, days / YEAR_DAYS)))
  const covers = $derived(connectedUdid !== null && coversDevice(cert.devices, connectedUdid, cert.all_devices))
</script>

<div class="flex flex-col gap-4 p-4">
  <div class="flex items-start gap-3">
    <div class="seal" aria-hidden="true">◉</div>
    <div class="min-w-0 flex-1">
      <div class="truncate font-display text-[14px] font-bold tracking-tight">{cert.nickname}</div>
      <div class="truncate font-display text-[11px] text-muted">{cert.team_id}</div>
    </div>
    {#if cert.broken}
      <span class="flag broken">{t('certs.broken')}</span>
    {:else}
      <span class="flag" class:off={!cert.has_push}>
        {cert.has_push ? t('certs.push_yes') : t('certs.push_no')}
      </span>
    {/if}
  </div>

  {#if cert.broken}
    <p class="m-0 text-[12px] text-danger">{t('certs.broken_text')}</p>
  {:else}
    <div>
      <div class="mb-1.5 flex items-baseline justify-between text-[12px]">
        <span class="tone-{tone} font-display">
          {expiry === null ? '—' : expiry.state === 'expired' ? t('certs.expired') : t('certs.days_left', { days: expiry.days })}
        </span>
        <span class="text-muted">
          {cert.is_wildcard ? t('certs.wildcard') : t('certs.single_app')}
        </span>
      </div>
      <div class="meter" aria-hidden="true">
        <div class="meter-fill tone-bg-{tone}" style:transform="scaleX({fill})"></div>
      </div>
    </div>

    <div class="flex items-center gap-2 text-[12px] text-muted">
      <span>
        {cert.all_devices ? t('certs.all_devices') : cert.devices.length ? t('certs.devices_count', { count: cert.devices.length }) : t('certs.no_devices')}
      </span>
      {#if connectedUdid}
        <span aria-hidden="true">·</span>
        <span class:text-accent={covers} class:text-danger={!covers}>
          {covers ? t('certs.covers_device') : t('certs.misses_device')}
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .seal {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    color: var(--color-accent);
    background: var(--color-accent-dark);
    box-shadow: inset 0 0 0 1px rgb(198 255 61 / 0.2);
  }
  .flag {
    font-family: var(--font-display);
    font-size: 11px;
    padding: 2px 9px;
    border-radius: 999px;
    color: var(--color-accent);
    background: var(--color-accent-dark);
  }
  .flag.broken {
    color: var(--color-danger);
    background: rgb(255 107 94 / 0.1);
  }
  .flag.off {
    color: var(--color-warn);
    background: rgb(255 194 71 / 0.1);
  }
  .meter {
    height: 4px;
    border-radius: 999px;
    background: var(--color-line);
    overflow: hidden;
  }
  .meter-fill {
    height: 100%;
    transform-origin: left;
    border-radius: 999px;
    transition: transform 400ms var(--ease-out-quint);
  }
  .tone-good {
    color: var(--color-ink);
  }
  .tone-soon {
    color: var(--color-warn);
  }
  .tone-bad {
    color: var(--color-danger);
  }
  .tone-bg-good {
    background: var(--color-accent);
  }
  .tone-bg-soon {
    background: var(--color-warn);
  }
  .tone-bg-bad {
    background: var(--color-danger);
  }
</style>
