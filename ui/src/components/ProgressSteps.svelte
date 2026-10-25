<script lang="ts">
  import { t } from '../lib/i18n'

  type Props = { steps: string[]; current: string; percent?: number }
  let { steps, current, percent }: Props = $props()

  const currentIndex = $derived(steps.indexOf(current))
  const fraction = $derived(Math.min(100, Math.max(0, percent ?? 0)) / 100)
</script>

<div class="rise" role="status" aria-label={t('progress.label')}>
  <ol class="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0">
    {#each steps as step, i (step)}
      {@const state = i < currentIndex ? 'done' : i === currentIndex ? 'now' : 'todo'}
      <li
        class="flex items-center gap-2 font-display text-[12px] {state}"
        aria-current={state === 'now' ? 'step' : undefined}
      >
        <span class="dot" aria-hidden="true"></span>
        {t(`step.${step}`)}
        {#if state === 'now' && percent !== undefined}
          <span class="text-accent">{Math.round(percent)}%</span>
        {/if}
      </li>
    {/each}
  </ol>
  {#if percent !== undefined}
    <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-line">
      <div
        class="bar h-full w-full origin-left rounded-full bg-accent"
        style:transform="scaleX({fraction})"
      ></div>
    </div>
  {/if}
</div>

<style>
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: var(--color-line-strong);
  }
  .done {
    color: var(--color-ink);
  }
  .done .dot {
    background: var(--color-accent);
  }
  .now {
    color: var(--color-accent);
  }
  .now .dot {
    background: var(--color-accent);
    animation: pulse-dot 1.1s ease-in-out infinite;
  }
  .todo {
    color: var(--color-muted);
  }
  .bar {
    transition: transform 240ms var(--ease-out-quint);
  }
</style>
