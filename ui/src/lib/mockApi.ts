





import type { JobEvent, WispErr } from './api'
import { certWarnings } from './certRules'

const STEP_MS = 250
const NOW = '2026-10-24T12:00:00+00:00'
const DAY_MS = 86_400_000

type Ok<T> = { ok: true; data: T }
type Fail = { ok: false; error: WispErr }
type Emit = (event: JobEvent) => void

const ok = <T>(data: T): Ok<T> => ({ ok: true, data })
const failure = (code: string, params: Record<string, unknown> = {}): Fail => ({
  ok: false,
  error: { code, params, detail: 'mock' },
})


const inDays = (days: number) => new Date(Date.now() + days * DAY_MS + DAY_MS / 2).toISOString()

const REPO_URL = 'https://example.com/repo.json'
const makeRepo = (url = REPO_URL, htmlDescription = false) => ({
  url,
  name: 'Demo Repo',
  icon_url: null,
  skipped: 0,
  apps: [
    {
      repo_url: url,
      name: 'Demo App',
      bundle_id: 'com.example.demo',
      version: '452.0.1',
      download_url: 'https://example.com/demo.ipa',
      icon_url: null,
      size: 96_000_000,
      description: htmlDescription ? '<b>x</b>' : 'A demo app for screenshots',
      developer: 'demo',
    },
    {
      repo_url: url,
      name: 'Sample Tool',
      bundle_id: 'com.example.sample',
      version: '9.1.0',
      download_url: 'https://example.com/sample.ipa',
      icon_url: null,
      size: 64_000_000,
      description: 'A second demo app',
      developer: null,
    },
  ],
})

const makeCerts = () => [
  {
    id: 'a1b2c3d4e5f6',
    nickname: 'Ana sertifika',
    team_id: 'DEMO-TEAM-A',
    common_name: 'Apple Development: Demo (DEMO-TEAM-A)',
    app_id: 'com.example.demo',
    is_wildcard: false,
    has_push: true,
    devices: ['DEMO-DEVICE'],
    all_devices: false,
    expires: inDays(200),
    added_at: NOW,
    broken: false,
  },
  {
    id: '0f9e8d7c6b5a',
    nickname: 'Yedek (pushsuz)',
    team_id: 'DEMO-TEAM-B',
    common_name: 'Apple Development: Demo Backup (DEMO-TEAM-B)',
    app_id: 'com.example.demo',
    is_wildcard: false,
    has_push: false,
    devices: ['DEMO-OTHER-DEVICE'],
    all_devices: false,
    expires: inDays(3),
    added_at: NOW,
    broken: false,
  },
  {
    id: '5a6b7c8d9e0f',
    nickname: 'Kurumsal',
    team_id: 'DEMO-TEAM-C',
    common_name: 'iPhone Distribution: Demo Corp (DEMO-TEAM-C)',
    app_id: 'com.example.demo',
    is_wildcard: false,
    has_push: true,
    devices: [],
    all_devices: true,
    expires: inDays(90),
    added_at: NOW,
    broken: false,
  },
]


const BROKEN_CERT = {
  id: '9f8e7d6c5b4a',
  nickname: '9f8e7d6c5b4a',
  team_id: '',
  common_name: '',
  app_id: '',
  is_wildcard: false,
  has_push: false,
  devices: [] as string[],
  all_devices: false,
  expires: NOW,
  added_at: NOW,
  broken: true,
}

const makeEntry = (n = 1) => ({
  id: `lib${String(n).padStart(9, '0')}`,
  name: 'Demo App',
  bundle_id: 'com.example.demo',
  version: '452.0.1',
  path: 'demo.ipa',
  source: REPO_URL,
  added_at: NOW,
  owned: true,
})

const DEVICE = {
  udid: 'DEMO-DEVICE',
  name: 'Demo iPhone',
  ios: '18.1',
  model: 'DemoPhone1,1',
}
const DEVICE_APPS = [
  {
    bundle_id: 'com.example.demo',
    name: 'Demo App',
    version: '452.0.1',
    signer: 'Apple Development: Demo',
    has_push: true,
    app_id: 'com.example.demo',
  },
]

type JobStep = { step: string; percent?: number }
type Outcome = { result: unknown } | { error: WispErr }

export function createMockApi(emit: Emit, flags: URLSearchParams) {

  let settings: { language: string | null; download_dir: string } = { language: null, download_dir:'C:\\Users\\demo\\WispSign\\ipas' }
  let repos = [REPO_URL]

  let library: ReturnType<typeof makeEntry>[] = flags.has('seedlib') ? [makeEntry()] : []
  let certs = flags.has('brokencert') ? [...makeCerts(), BROKEN_CERT] : makeCerts()
  let jobCounter = 0
  const htmlDesc = flags.has('htmldesc')


  function startJob(steps: JobStep[], outcome: Outcome): Ok<string> {
    const job = `mockjob${String(++jobCounter).padStart(4, '0')}`
    steps.forEach((s, i) =>
      setTimeout(() => emit({ job, type: 'progress', ...s }), STEP_MS * (i + 1)),
    )
    setTimeout(
      () =>
        emit(
          'error' in outcome
            ? { job, type: 'error', error: outcome.error }
            : { job, type: 'done', result: outcome.result },
        ),
      STEP_MS * (steps.length + 1),
    )
    return ok(job)
  }

  const addEntry = (patch: Partial<ReturnType<typeof makeEntry>>) => {
    const entry = { ...makeEntry(library.length + 1), ...patch }
    library = [...library, entry]
    return entry
  }

  return {
    get_state: async () =>
      ok({ version: '0.1.0', settings, repos, library, certs, updates: !flags.has('noupdates') }),
    settings_get: async () => ok(settings),
    settings_set: async (patch: Partial<typeof settings>) => {
      if (patch.download_dir !== undefined && !/^[A-Za-z]:\\/.test(patch.download_dir)) {
        return failure('error.settings_invalid')
      }
      settings = { ...settings, ...patch }
      return ok(settings)
    },
    check_update: async () =>
      ok(
        flags.has('updatefail')
          ? { current: '0.1.0', status: 'failed', latest: null }
          : { current: '0.1.0', status: 'current', latest: null },
      ),
    cache_clear: async () => ok(48_234_496),

    repos_list: async () => ok(repos),
    repos_add: async (url: string) => {
      if (!url.startsWith('https://')) return failure('error.url_not_https')
      if (!repos.includes(url)) repos = [...repos, url]
      return ok(makeRepo(url, htmlDesc))
    },
    repos_remove: async (url: string) => {
      repos = repos.filter((u) => u !== url)
      return ok(null)
    },
    repos_refresh: async () =>
      startJob([{ step: 'download', percent: 50 }], {
        result: repos.map((url) => makeRepo(url, htmlDesc)),
      }),
    repo_download: async (repoUrl: string, bundleId: string) => {

      const app = makeRepo(repoUrl, htmlDesc).apps.find((a) => a.bundle_id === bundleId)
      if (!app) return failure('error.repo_invalid')
      const path = `${bundleId}-${app.version}-${library.length + 1}.ipa`
      const entry = addEntry({ name: app.name, bundle_id: bundleId, version: app.version, path, source: repoUrl })
      return startJob(
        [
          { step: 'download', percent: 30 },
          { step: 'download', percent: 100 },
        ],
        { result: entry },
      )
    },
    job_result: async () => ok(null),

    library_list: async () => ok(library),
    library_add_files: async () => ok([]),
    library_add_path: async (path: string) =>
      ok(addEntry({ name: path.split(/[\\/]/).pop() ?? path, source: 'file' })),
    library_remove: async (id: string) => {
      library = library.filter((e) => e.id !== id)
      return ok(null)
    },
    library_icon: async () => ok(null),
    pick_icon: async () => ok(null),
    pick_folder: async () => ok('D:\\IPA'),

    certs_list: async () => ok(certs),
    certs_import: async (nickname: string) => {
      const added = {
        ...makeCerts()[0],
        id: `cert${String(certs.length + 1).padStart(8, '0')}`,
        nickname,
      }
      certs = [...certs, added]
      return ok(added)
    },
    certs_remove: async (id: string) => {
      certs = certs.filter((c) => c.id !== id)
      return ok(null)
    },
    certs_validate: async (id: string, udid: string | null, bundleId: string | null = null) => {
      if (flags.has('failvalidate')) return failure('error.cert_meta_corrupt')
      const cert = certs.find((c) => c.id === id)
      if (!cert) return failure('error.cert_not_found')
      if (cert.broken) return failure('error.cert_meta_corrupt')
      return ok(certWarnings(cert, udid, bundleId))
    },

    device_list: async () => ok(flags.has('nodevice') ? [] : [DEVICE]),
    device_apps: async () => ok(DEVICE_APPS),
    device_uninstall: async () => ok(null),

    sign_and_install: async () => {
      const steps: JobStep[] = [
        { step: 'extract' },
        { step: 'sign' },
        { step: 'verify' },
        { step: 'pack' },
        { step: 'install', percent: 100 },
      ]
      if (flags.has('failsign')) {
        return startJob(steps.slice(0, 2), { error: failure('error.identifier_mismatch').error })
      }
      return startJob(steps, { result: null })
    },
  }
}
