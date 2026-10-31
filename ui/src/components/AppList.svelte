<script lang="ts" generics="T">
  import type { Snippet } from 'svelte'
  import { nextIndex, uniqueKeys } from '../lib/listNav'

  type Props = {
    items: T[]
    key: (item: T) => string
    selected: string | null
    onSelect: (key: string) => void
    label: string
    row: Snippet<[T, boolean]>
    layout?: 'list' | 'grid'
  }
  let { items, key, selected, onSelect, label, row, layout = 'list' }: Props = $props()

  let listEl: HTMLElement | undefined = $state()


  const keys = $derived(uniqueKeys(items.map(key)))
  const rows = $derived(items.map((item, i) => ({ item, key: keys[i] })))
  const selectedIndex = $derived(keys.indexOf(selected ?? ''))
  const tabStop = $derived(selectedIndex >= 0 ? selectedIndex : 0)

  function focusAt(index: number) {
    const options = listEl?.querySelectorAll<HTMLElement>('[role="option"]')
    options?.[index]?.focus()
  }

  function onKeydown(event: KeyboardEvent, index: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(keys[index])
      return
    }
    const next = nextIndex(event.key, index, items.length)
    if (next === null) return
    event.preventDefault()
    onSelect(keys[next])
    focusAt(next)
  }
</script>

<div
  bind:this={listEl}
  role="listbox"
  aria-label={label}
  class={layout === 'grid' ? 'grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3' : 'flex flex-col gap-2'}
>
  {#each rows as { item, key: rowKey }, i (rowKey)}
    {@const isSelected = rowKey === selected}
    <div
      role="option"
      aria-selected={isSelected}
      tabindex={i === tabStop ? 0 : -1}
      class="row option"
      style:animation-delay="{Math.min(i, 12) * 28}ms"
      onclick={() => onSelect(rowKey)}
      onkeydown={(event) => onKeydown(event, i)}
    >
      {@render row(item, isSelected)}
    </div>
  {/each}
</div>

<style>
  .option {
    position: relative;
    cursor: pointer;
    outline: none;
    animation: rise 260ms var(--ease-out-quint) backwards;
  }
  .option::before {
    content: '';
    position: absolute;
    left: -1px;
    top: 22%;
    bottom: 22%;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: var(--color-accent);
    opacity: 0;
    transform: scaleY(0.4);
    transition:
      opacity 180ms,
      transform 220ms var(--ease-out-quint);
  }
  .option[aria-selected='true'] {
    background: linear-gradient(90deg, rgb(198 255 61 / 0.07), #121212 55%);
    box-shadow: 0 0 0 1px rgb(198 255 61 / 0.15), 0 10px 30px -18px rgb(198 255 61 / 0.6);
  }
  .option[aria-selected='true']::before {
    opacity: 1;
    transform: scaleY(1);
  }
  .option:focus-visible {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px rgb(198 255 61 / 0.25);
  }
  .option:active {
    transform: translateX(2px) scale(0.995);
  }
</style>
