<script lang="ts">
  import { formatSize } from '../lib/format'
  import { t } from '../lib/i18n'
  import { jobs } from '../lib/jobs'
  import type { RepoApp } from '../lib/repoState'
  import { downloadApp, downloadKey, library } from '../lib/stores'
  import AppIcon from './AppIcon.svelte'
  import ErrorBox from './ErrorBox.svelte'
  import ProgressSteps from './ProgressSteps.svelte'

  type Props = { app: RepoApp; repoName: string }
  let { app, repoName }: Props = $props()

  const job = $derived($jobs[downloadKey(app)])
  // From the library itself, so removing the IPA brings the button back.
  const inLibrary = $derived(
    $library.some((e) => e.source === app.repo_url && e.bundle_id === app.bundle_id),
  )
  const size = $derived(formatSize(app.size))
</script>

<article class="rise flex flex-col gap-5">
  <header class="flex flex-col items-start gap-4">
    <AppIcon name={app.name} src={app.icon_url} size={84} glow />
    <div class="min-w-0">
      <h3 class="m-0 font-display text-[22px] leading-tight font-bold tracking-tight break-words">
        {app.name}
      </h3>
      <p class="mt-1 mb-0 text-[13px] text-muted">
        {app.developer ?? t('repos.unknown_developer')} · {repoName}
      </p>
    </div>
  </header>

  <dl class="facts m-0 grid grid-cols-2 gap-2">
    <div>
      <dt class="label">{t('app.version')}</dt>
      <dd class="font-display">{app.version || '—'}</dd>
    </div>
    <div>
      <dt class="label">{t('app.size')}</dt>
      <dd class="font-display">{size ?? '—'}</dd>
    </div>
    <div class="col-span-2">
      <dt class="label">{t('app.bundle_id')}</dt>
      <dd class="font-display text-[12px] break-all">{app.bundle_id}</dd>
    </div>
  </dl>

  {#if app.description}
    <section>
      <h4 class="label m-0 mb-2">{t('app.description')}</h4>
      <p class="m-0 text-[13px] leading-relaxed whitespace-pre-line text-ink/80">{app.description}</p>
    </section>
  {/if}

  <div class="sticky bottom-0 -mx-5 -mb-5 mt-auto border-t border-line bg-panel/95 p-5 backdrop-blur">
    {#if job?.status === 'running'}
      <ProgressSteps steps={['download']} current="download" percent={job.percent ?? 0} />
    {:else if inLibrary || job?.status === 'done'}
      <p class="done m-0 flex items-center gap-2 font-display text-[13px] text-accent">
        <span aria-hidden="true">✓</span>{t('repos.in_library')}
      </p>
    {:else}
      {#if job?.status === 'error'}
        <div class="mb-3"><ErrorBox error={job.error} /></div>
      {/if}
      <button type="button" class="btn btn-primary cta w-full" onclick={() => downloadApp(app)}>
        {t('repos.download')}
      </button>
    {/if}
  </div>
</article>

<style>
  .facts > div {
    background: var(--color-raised);
    border: 1px solid var(--color-line);
    border-radius: 10px;
    padding: 10px 12px;
  }
  dd {
    margin: 4px 0 0;
    font-size: 13px;
  }
  .cta {
    padding: 11px 14px;
    font-size: 13px;
    box-shadow: 0 10px 30px -12px rgb(198 255 61 / 0.55);
  }
</style>
