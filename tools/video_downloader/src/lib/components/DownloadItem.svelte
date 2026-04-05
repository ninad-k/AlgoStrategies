<script lang="ts">
  import { pauseDownload, resumeDownload, cancelDownload, removeDownload, openFileLocation, formatSize } from '$lib/api';
  import type { DownloadItem } from '$lib/api';

  let { item }: { item: DownloadItem } = $props();

  function stateColor(state: string): string {
    switch (state) {
      case 'downloading': return '#3b82f6';
      case 'completed': return '#10b981';
      case 'failed': return '#ef4444';
      case 'paused': return '#f59e0b';
      case 'extracting': return '#8b5cf6';
      case 'queued': return '#6b7280';
      case 'cancelled': return '#6b7280';
      default: return '#6b7280';
    }
  }

  function stateLabel(state: string): string {
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  async function handlePause() { await pauseDownload(item.id); }
  async function handleResume() { await resumeDownload(item.id); }
  async function handleCancel() { await cancelDownload(item.id); }
  async function handleRemove() { await removeDownload(item.id); }
  async function handleOpenFile() {
    if (item.output_path) await openFileLocation(item.output_path);
  }
</script>

<div class="download-item">
  <div class="item-header">
    <span class="title" title={item.title}>{item.title || 'Untitled'}</span>
    <span class="state" style="color: {stateColor(item.state)}">{stateLabel(item.state)}</span>
  </div>

  {#if item.state === 'downloading' || item.state === 'paused'}
    <div class="progress-row">
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width: {item.progress}%; background: {stateColor(item.state)}"></div>
      </div>
      <span class="progress-text">{item.progress.toFixed(1)}%</span>
    </div>
    <div class="info-row">
      <span>{item.speed || '--'}</span>
      <span>ETA: {item.eta || '--:--'}</span>
      <span>{formatSize(item.downloaded_size)} / {item.total_size > 0 ? formatSize(item.total_size) : '?'}</span>
    </div>
  {/if}

  {#if item.state === 'extracting'}
    <div class="info-row">
      <span class="extracting-text">Extracting video info...</span>
    </div>
  {/if}

  {#if item.error}
    <div class="error-text">{item.error}</div>
  {/if}

  <div class="actions">
    {#if item.state === 'downloading'}
      <button class="btn btn-warning" onclick={handlePause}>Pause</button>
      <button class="btn btn-danger" onclick={handleCancel}>Cancel</button>
    {:else if item.state === 'paused'}
      <button class="btn btn-primary" onclick={handleResume}>Resume</button>
      <button class="btn btn-danger" onclick={handleCancel}>Cancel</button>
    {:else if item.state === 'completed'}
      <button class="btn btn-success" onclick={handleOpenFile}>Show in Finder</button>
      <button class="btn btn-ghost" onclick={handleRemove}>Remove</button>
    {:else if item.state === 'failed' || item.state === 'cancelled'}
      <button class="btn btn-primary" onclick={handleResume}>Retry</button>
      <button class="btn btn-ghost" onclick={handleRemove}>Remove</button>
    {:else if item.state === 'queued'}
      <button class="btn btn-danger" onclick={handleCancel}>Cancel</button>
    {/if}
  </div>
</div>

<style>
  .download-item {
    background: var(--bg-card);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: background 0.15s;
  }
  .download-item:hover {
    background: var(--bg-hover);
  }
  .item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .title {
    font-size: 14px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    margin-right: 12px;
  }
  .state {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .progress-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }
  .progress-bar-bg {
    flex: 1;
    height: 6px;
    background: rgba(255,255,255,0.1);
    border-radius: 3px;
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
  }
  .progress-text {
    font-size: 12px;
    color: var(--text-secondary);
    min-width: 45px;
    text-align: right;
  }
  .info-row {
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
  .extracting-text {
    color: #8b5cf6;
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .error-text {
    font-size: 12px;
    color: var(--danger);
    margin-bottom: 8px;
    word-break: break-all;
  }
  .actions {
    display: flex;
    gap: 8px;
  }
  .btn {
    padding: 4px 12px;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 500;
    transition: opacity 0.15s;
  }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: var(--accent); color: white; }
  .btn-success { background: var(--success); color: white; }
  .btn-warning { background: var(--warning); color: black; }
  .btn-danger { background: var(--danger); color: white; }
  .btn-ghost { background: rgba(255,255,255,0.1); color: var(--text-secondary); }
</style>
