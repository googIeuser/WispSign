<script lang="ts">
  import { onMount } from 'svelte'
  import Nav from './components/Nav.svelte'
  import Toast from './components/Toast.svelte'
  import { initLocale, locale } from './lib/i18n'
  import { activeView, initHostEvents } from './lib/stores'
  import type { ViewId } from './lib/types'
  import Certs from './views/Certs.svelte'
  import Device from './views/Device.svelte'
  import Library from './views/Library.svelte'
  import Repos from './views/Repos.svelte'
  import Settings from './views/Settings.svelte'

  const VIEWS = { repos: Repos, library: Library, certs: Certs, device: Device, settings: Settings }
  const View = $derived(VIEWS[$activeView])

  onMount(() => {
    void initLocale()
    return initHostEvents()
  })
</script>

<!-- A file dropped outside a drop target must not navigate the window away. -->
<svelte:window ondragover={(e) => e.preventDefault()} ondrop={(e) => e.preventDefault()} />

{#key $locale}
  <div class="grid h-full grid-cols-[208px_minmax(0,1fr)_340px]">
    <aside class="border-r border-line bg-bg">
      <Nav active={$activeView} onSelect={(id) => activeView.set(id as ViewId)} />
    </aside>
    <View />
  </div>
{/key}

<Toast />
