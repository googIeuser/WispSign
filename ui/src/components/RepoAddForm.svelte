<script lang="ts">
  import type { WispErr } from '../lib/api'
  import { t } from '../lib/i18n'
  import { addRepo } from '../lib/stores'
  import ErrorBox from './ErrorBox.svelte'

  type Props = { onClose: () => void }
  let { onClose }: Props = $props()

  let url = $state('')
  let busy = $state(false)
  let error = $state<WispErr | null>(null)
  let input: HTMLInputElement | undefined = $state()

  $effect(() => input?.focus())

  async function submit(event: SubmitEvent) {
    event.preventDefault()
    const value = url.trim()
    if (!value.toLowerCase().startsWith('https://')) {
      error = { code: 'error.url_not_https', params: {}, detail: '' }
      return
    }
    busy = true
    error = await addRepo(value)
    busy = false
    if (!error) onClose()
  }
</script>

<form class="rise flex flex-col gap-3" novalidate onsubmit={submit}>
  <div class="flex items-center gap-2">
    <input
      bind:this={input}
      bind:value={url}
      class="field min-w-0 flex-1 font-display text-[12px]"
      type="url"
      inputmode="url"
      spellcheck="false"
      placeholder="https://…/repo.json"
      aria-label={t('repos.url')}
      aria-invalid={!!error}
      disabled={busy}
      onkeydown={(e) => e.key === 'Escape' && onClose()}
    />
    <button type="submit" class="btn btn-primary" disabled={busy || !url.trim()}>
      {busy ? t('repos.adding') : t('repos.add_submit')}
    </button>
    <button type="button" class="btn" onclick={onClose}>{t('common.cancel')}</button>
  </div>
  {#if error}<ErrorBox {error} />{/if}
</form>
