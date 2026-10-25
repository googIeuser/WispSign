<script lang="ts">
  import { t } from '../lib/i18n'
  import { dismissToast, toasts } from '../lib/toast'
  import ErrorBox from './ErrorBox.svelte'
</script>

<div
  class="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[360px] flex-col gap-2"
  aria-live="polite"
>
  {#each $toasts as toast (toast.id)}
    <div
      class="rise pointer-events-auto rounded-xl border border-line-strong bg-raised p-3 shadow-2xl"
    >
      <div class="flex items-start gap-3">
        <div class="min-w-0 flex-1">
          {#if toast.error}
            <ErrorBox error={toast.error} />
          {:else}
            <p class="m-0 text-[13px]">{toast.text}</p>
          {/if}
        </div>
        <button
          type="button"
          class="close"
          aria-label={t('toast.dismiss')}
          onclick={() => dismissToast(toast.id)}>×</button
        >
      </div>
    </div>
  {/each}
</div>

<style>
  .close {
    border: 0;
    background: transparent;
    color: var(--color-muted);
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 6px;
    transition:
      color 160ms,
      transform 160ms var(--ease-out-quint);
  }
  .close:hover {
    color: var(--color-accent);
    transform: scale(1.15);
  }
</style>
