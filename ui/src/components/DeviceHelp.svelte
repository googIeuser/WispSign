<script lang="ts">
  import { t } from '../lib/i18n'

  type Props = { usbmuxMissing?: boolean; busy?: boolean; onRetry: () => void }
  let { usbmuxMissing = false, busy = false, onRetry }: Props = $props()

  const STEPS = [
    { title: 'device.help_apple_title', text: 'device.help_apple_text' },
    { title: 'device.help_trust_title', text: 'device.help_trust_text' },
    { title: 'device.help_cable_title', text: 'device.help_cable_text' },
  ]
</script>

<div class="rise mx-auto flex max-w-[460px] flex-col gap-6 py-6">
  <div class="flex items-center gap-4">
    <div class="phone" aria-hidden="true"><span></span></div>
    <div>
      <h2 class="m-0 font-display text-[17px] font-bold tracking-tight">{t('device.help_title')}</h2>
      <p class="mt-1 mb-0 text-[13px] text-muted">
        {usbmuxMissing ? t('error.usbmux_missing') : t('device.help_intro')}
      </p>
    </div>
  </div>

  <ol class="m-0 flex list-none flex-col gap-2 p-0">
    {#each STEPS as step, i (step.title)}
      <li class="row flex gap-3 p-4" class:highlight={usbmuxMissing && i === 0}>
        <span class="num" aria-hidden="true">{i + 1}</span>
        <div>
          <h3 class="m-0 text-[13px] font-semibold">{t(step.title)}</h3>
          <p class="mt-1 mb-0 text-[12px] text-muted">{t(step.text)}</p>
        </div>
      </li>
    {/each}
  </ol>

  <button type="button" class="btn btn-primary self-start" disabled={busy} onclick={onRetry}>
    {busy ? t('device.searching') : t('common.retry')}
  </button>
</div>

<style>
  .phone {
    position: relative;
    flex: none;
    width: 46px;
    height: 74px;
    border-radius: 12px;
    border: 2px solid var(--color-line-strong);
    background: linear-gradient(180deg, #151515, #0d0d0d);
  }
  .phone span {
    position: absolute;
    left: 50%;
    bottom: -14px;
    width: 2px;
    height: 12px;
    background: var(--color-accent);
    box-shadow: 0 0 10px var(--color-accent);
    animation: pulse-dot 1.4s ease-in-out infinite;
  }
  .num {
    flex: none;
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border-radius: 999px;
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 700;
    color: var(--color-accent);
    background: var(--color-accent-dark);
  }
  .highlight {
    border-color: rgb(198 255 61 / 0.45);
  }
</style>
