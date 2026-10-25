/** Transient notifications shown by Toast.svelte. */
import { writable } from 'svelte/store'
import type { WispErr } from './api'

export type ToastItem = { id: number; kind: 'info' | 'error'; text: string; error?: WispErr }

export const toasts = writable<ToastItem[]>([])
let nextId = 1

export function dismissToast(id: number): void {
  toasts.update((list) => list.filter((item) => item.id !== id))
}

export function pushToast(item: Omit<ToastItem, 'id'>, ttlMs = 6000): number {
  const id = nextId++
  toasts.update((list) => [...list, { ...item, id }])
  if (ttlMs > 0) setTimeout(() => dismissToast(id), ttlMs)
  return id
}
