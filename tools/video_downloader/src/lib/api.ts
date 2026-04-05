import { invoke } from '@tauri-apps/api/core';

export interface DownloadItem {
  id: string;
  url: string;
  title: string;
  page_url: string;
  format_id: string | null;
  state: string;
  progress: number;
  speed: string;
  eta: string;
  total_size: number;
  downloaded_size: number;
  output_path: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface VideoFormat {
  format_id: string;
  ext: string;
  resolution: string;
  filesize: number | null;
  note: string;
  vcodec: string | null;
  acodec: string | null;
}

export interface VideoInfo {
  title: string;
  url: string;
  thumbnail: string | null;
  duration: number | null;
  formats: VideoFormat[];
}

export interface AppSettings {
  download_dir: string;
  max_concurrent: number;
  default_quality: string;
  connections_per_download: number;
  auto_start: boolean;
  show_format_dialog: boolean;
}

export async function addDownload(url: string, title?: string, formatId?: string): Promise<string> {
  return invoke('add_download', { url, title: title ?? null, formatId: formatId ?? null });
}

export async function getDownloads(): Promise<DownloadItem[]> {
  return invoke('get_downloads');
}

export async function pauseDownload(id: string): Promise<void> {
  return invoke('pause_download', { id });
}

export async function resumeDownload(id: string): Promise<void> {
  return invoke('resume_download', { id });
}

export async function cancelDownload(id: string): Promise<void> {
  return invoke('cancel_download', { id });
}

export async function removeDownload(id: string): Promise<void> {
  return invoke('remove_download', { id });
}

export async function getFormats(url: string): Promise<VideoInfo> {
  return invoke('get_formats', { url });
}

export async function getHistory(): Promise<DownloadItem[]> {
  return invoke('get_history');
}

export async function clearHistory(): Promise<void> {
  return invoke('clear_history');
}

export async function getSettings(): Promise<AppSettings> {
  return invoke('get_settings');
}

export async function updateSettings(settings: AppSettings): Promise<void> {
  return invoke('update_settings', { settings });
}

export async function openFileLocation(path: string): Promise<void> {
  return invoke('open_file_location', { path });
}

export function formatSize(bytes: number): string {
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return bytes + ' B';
}
