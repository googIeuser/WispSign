<script lang="ts">
  import type { Snippet } from 'svelte'
  import { t } from '../lib/i18n'

  type Props = {
    title: string
    count?: number
    actions?: Snippet
    toolbar?: Snippet
    children: Snippet
    detail?: Snippet
  }
  let { title, count, actions, toolbar, children, detail }: Props = $props()
</script>

<main class="flex min-w-0 flex-col overflow-hidden">
  <header class="flex min-h-[61px] items-center gap-3 border-b border-line px-6 py-3">
    <h1 class="m-0 font-display text-[18px] font-bold tracking-tight">{title}</h1>
    {#if count !== undefined}
      <span class="pill" aria-label={t('common.count', { count })}>{count}</span>
    {/if}
    <div class="ml-auto flex items-center gap-2">{@render actions?.()}</div>
  </header>
  {#if toolbar}
    <div class="border-b border-line px-6 py-3">{@render toolbar()}</div>
  {/if}
  <section class="rise min-h-0 flex-1 overflow-y-auto p-6" id="center">
    {@render children()}
  </section>
</main>

<aside class="detail flex min-w-0 flex-col border-l border-line bg-panel" aria-label={t('detail.title')}>
  <header class="flex min-h-[61px] items-center border-b border-line px-5 py-3">
    <h2 class="label m-0">{t('detail.title')}</h2>
  </header>
  <div class="min-h-0 flex-1 overflow-y-auto p-5" id="detail">
    {#if detail}
      {@render detail()}
    {:else}
      <p class="m-0 text-[13px] text-muted">{t('common.select_prompt')}</p>
    {/if}
  </div>
</aside>

<style>
  .detail {
    background:
      radial-gradient(120% 60% at 100% 0%, rgb(198 255 61 / 0.05), transparent 60%),
      var(--color-panel);
  }
</style>
