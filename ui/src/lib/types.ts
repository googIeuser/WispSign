/** Shapes of the bridge payloads the views read (see src/wispsign/bridge/api.py). */

export type LibraryEntry = {
  id: string
  name: string
  bundle_id: string
  version: string
  path: string
  source: string
  added_at: string
  owned: boolean
}

export type Cert = {
  id: string
  nickname: string
  team_id: string
  common_name: string
  app_id: string
  is_wildcard: boolean
  has_push: boolean
  devices: string[]
  all_devices: boolean
  expires: string
  added_at: string
  /** meta.json unreadable: the record can only be removed. */
  broken: boolean
}

export type Device = { udid: string; name: string; ios: string; model: string }

export type DeviceApp = {
  bundle_id: string
  name: string
  version: string
  signer: string | null
  has_push: boolean
  app_id: string | null
}

export type Warning = { code: string; params: Record<string, unknown> }

export type Settings = { language: 'tr' | 'en' | null; download_dir: string }

export type ViewId = 'repos' | 'library' | 'certs' | 'device' | 'settings'
