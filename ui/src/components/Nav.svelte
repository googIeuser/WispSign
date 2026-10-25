<script lang="ts">
  import { isMock } from '../lib/api'
  import { t } from '../lib/i18n'

  type Props = { active: string; onSelect: (id: string) => void }
  let { active, onSelect }: Props = $props()

  const items = [
    { id: 'repos', label: 'nav.repos', glyph: '◈' },
    { id: 'library', label: 'nav.library', glyph: '▤' },
    { id: 'certs', label: 'nav.certs', glyph: '◉' },
    { id: 'device', label: 'nav.device', glyph: '▢' },
    { id: 'settings', label: 'nav.settings', glyph: '✱' },
  ]
</script>

<nav class="flex h-full flex-col gap-1 px-3 py-4" aria-label={t('nav.label')}>
  <div class="mb-5 px-2">
    <div class="font-display text-[15px] font-bold tracking-tight text-accent">
      <span aria-hidden="true">◆</span>
      {t('app.name')}
    </div>
    <div class="label mt-0.5">{t('app.tagline')}</div>
    {#if isMock}<div class="label mt-2 text-accent">{t('app.demo')}</div>{/if}
  </div>
  {#each items as item (item.id)}
    <button
      type="button"
      class="nav-item"
      class:on={active === item.id}
      aria-current={active === item.id ? 'page' : undefined}
      onclick={() => onSelect(item.id)}
    >
      <span class="glyph" aria-hidden="true">{item.glyph}</span>
      <span>{t(item.label)}</span>
    </button>
  {/each}
</nav>

<style>
  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 10px;
    border: 0;
    border-radius: 9px;
    background: transparent;
    color: #8a8a8a;
    font-family: var(--font-display);
    font-size: 13px;
    text-align: left;
    cursor: pointer;
    transition:
      transform 160ms var(--ease-out-quint),
      color 160ms,
      background-color 160ms;
  }
  .nav-item:hover {
    color: var(--color-ink);
    background: var(--color-raised);
    transform: translateX(3px);
  }
  .nav-item:active {
    transform: translateX(3px) scale(0.98);
  }
  .nav-item.on {
    color: var(--color-bg);
    background: var(--color-accent);
    font-weight: 700;
    transform: none;
  }
  .glyph {
    width: 16px;
    text-align: center;
    opacity: 0.8;
  }
</style>
