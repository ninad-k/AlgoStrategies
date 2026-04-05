import { writable } from 'svelte/store';
import type { DownloadItem } from '$lib/api';
import { listen } from '@tauri-apps/api/event';
import { getDownloads } from '$lib/api';

export const downloads = writable<DownloadItem[]>([]);

let initialized = false;

export async function initDownloadsStore() {
  if (initialized) return;
  initialized = true;

  // Load initial state
  try {
    const items = await getDownloads();
    downloads.set(items);
  } catch (e) {
    console.error('Failed to load downloads:', e);
  }

  // Listen for updates from Rust backend
  listen<DownloadItem[]>('downloads-updated', (event) => {
    downloads.set(event.payload);
  });
}
