<script lang="ts">
  import type { WispErr } from '../lib/api'
  import { t } from '../lib/i18n'

  type Props = { error: WispErr }
  let { error }: Props = $props()

  const params = $derived(
    Object.fromEntries(Object.entries(error.params ?? {}).map(([k, v]) => [k, String(v)])),
  )
</script>

<div class="rise rounded-xl border border-danger/40 bg-danger-dark px-4 py-3" role="alert">
  <p class="m-0 text-[13px] text-ink">{t(error.code, params)}</p>
  {#if error.detail}
    <details class="mt-2">
      <summary class="label cursor-pointer select-none hover:text-accent">
        {t('common.details')}
      </summary>
      <pre
        class="mt-2 mb-0 max-h-40 overflow-auto rounded-lg bg-bg p-3 font-display text-[11px] whitespace-pre-wrap text-muted">{error.detail}</pre>
    </details>
  {/if}
</div>
