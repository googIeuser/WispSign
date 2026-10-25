<script lang="ts">
  import type { Snippet } from 'svelte'

  type Props = { glyph: string; title: string; text: string; action?: Snippet }
  let { glyph, title, text, action }: Props = $props()
</script>

<div class="rise mx-auto flex max-w-[380px] flex-col items-center px-4 py-14 text-center">
  <div class="halo mb-5 grid h-16 w-16 place-items-center rounded-2xl font-display text-[26px] text-accent" aria-hidden="true">
    {glyph}
  </div>
  <h2 class="m-0 font-display text-[15px] font-bold tracking-tight">{title}</h2>
  <p class="mt-2 mb-5 text-[13px] text-muted">{text}</p>
  {@render action?.()}
</div>

<style>
  .halo {
    background: var(--color-accent-dark);
    box-shadow:
      inset 0 0 0 1px rgb(198 255 61 / 0.25),
      0 0 40px -6px rgb(198 255 61 / 0.35);
  }
</style>
