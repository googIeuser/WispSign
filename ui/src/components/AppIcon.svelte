<script lang="ts">
  import { hueFor, safeImageSrc } from '../lib/format'

  type Props = { name: string; src?: string | null; size?: number; glow?: boolean }
  let { name, src = null, size = 40, glow = false }: Props = $props()

  let failed = $state(false)
  const safe = $derived(safeImageSrc(src))
  const hue = $derived(hueFor(name))
  const initial = $derived((name.trim()[0] ?? '?').toUpperCase())
  const radius = $derived(Math.round(size * 0.24))

  $effect(() => {
    void src
    failed = false
  })
</script>

<div
  class="icon"
  class:glow
  style:width="{size}px"
  style:height="{size}px"
  style:border-radius="{radius}px"
  style:--hue={hue}
  aria-hidden="true"
>
  {#if safe && !failed}
    <img src={safe} alt="" loading="lazy" referrerpolicy="no-referrer" onerror={() => (failed = true)} />
  {:else}
    <span class="initial" style:font-size="{Math.round(size * 0.42)}px">{initial}</span>
  {/if}
</div>

<style>
  .icon {
    position: relative;
    flex: none;
    display: grid;
    place-items: center;
    overflow: hidden;
    background: linear-gradient(
      140deg,
      hsl(var(--hue) 70% 42%),
      hsl(calc(var(--hue) + 50) 75% 22%)
    );
    box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.08);
  }
  .icon.glow {
    box-shadow:
      inset 0 0 0 1px rgb(255 255 255 / 0.1),
      0 18px 48px -12px hsl(var(--hue) 80% 45% / 0.55);
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .initial {
    font-family: var(--font-display);
    font-weight: 700;
    color: rgb(255 255 255 / 0.92);
    text-shadow: 0 1px 2px rgb(0 0 0 / 0.35);
  }
</style>
