<script lang="ts">
  import { BLOCKING_CERT_WARNINGS } from '../lib/certRules'
  import { t } from '../lib/i18n'
  import type { Warning } from '../lib/types'

  type Props = { warnings: Warning[] }
  let { warnings }: Props = $props()

  const text = (w: Warning) =>
    t(w.code, Object.fromEntries(Object.entries(w.params ?? {}).map(([k, v]) => [k, String(v)])))
</script>

{#if warnings.length}
  <ul class="m-0 flex list-none flex-col gap-1.5 p-0" aria-label={t('warn.label')}>
    {#each warnings as w (w.code)}
      <li class="badge rise" class:danger={BLOCKING_CERT_WARNINGS.has(w.code)}>
        <span class="mark" aria-hidden="true">!</span>
        <span>{text(w)}</span>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .badge {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 9px;
    font-size: 12px;
    line-height: 1.4;
    color: var(--color-warn);
    background: rgb(255 194 71 / 0.08);
    border: 1px solid rgb(255 194 71 / 0.25);
  }
  .badge.danger {
    color: var(--color-danger);
    background: rgb(255 107 94 / 0.08);
    border-color: rgb(255 107 94 / 0.3);
  }
  .mark {
    flex: none;
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    margin-top: 1px;
    border-radius: 999px;
    font-family: var(--font-display);
    font-size: 10px;
    font-weight: 700;
    border: 1.5px solid currentColor;
  }
</style>
