<script lang="ts">
  import { t } from '../lib/i18n'

  type Props = { rows?: number }
  let { rows = 4 }: Props = $props()
</script>

<div class="flex flex-col gap-2" role="status" aria-label={t('common.loading')}>
  {#each Array.from({ length: rows }, (_, i) => i) as i (i)}
    <div class="row flex items-center gap-3 p-3" style:animation-delay="{i * 90}ms">
      <div class="shimmer h-10 w-10 rounded-[10px]"></div>
      <div class="flex flex-1 flex-col gap-2">
        <div class="shimmer h-3 w-2/5 rounded"></div>
        <div class="shimmer h-2.5 w-1/4 rounded"></div>
      </div>
    </div>
  {/each}
</div>

<style>
  .row {
    animation: breathe 1.4s ease-in-out infinite;
  }
  .shimmer {
    background: var(--color-line-strong);
  }
  @keyframes breathe {
    50% {
      opacity: 0.45;
    }
  }
</style>
