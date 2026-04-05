import { writable } from 'svelte/store';
import type { AppSettings } from '$lib/api';
import { getSettings, updateSettings } from '$lib/api';

export const settings = writable<AppSettings>({
  download_dir: '',
  max_concurrent: 3,
  default_quality: 'best',
  connections_per_download: 8,
  auto_start: true,
  show_format_dialog: false,
});

export async function initSettingsStore() {
  try {
    const s = await getSettings();
    settings.set(s);
  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

export async function saveSettings(s: AppSettings) {
  await updateSettings(s);
  settings.set(s);
}
