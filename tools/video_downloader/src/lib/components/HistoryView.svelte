<script lang="ts">
  import { onMount } from 'svelte';
  import { getHistory, clearHistory, openFileLocation, formatSize } from '$lib/api';
  import type { DownloadItem } from '$lib/api';

  let history = $state<DownloadItem[]>([]);

  onMount(async () => {
    await loadHistory();
  });

  async function loadHistory() {
    try {
      history = await getHistory();
    } catch (e) {
      console.error('Failed to load history:', e);
    }
  }

  async function handleClear() {
    await clearHistory();
    history = [];
  }

  async function handleOpen(path: string | null) {
    if (path) await openFileLocation(path);
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }
</script>

<div class="history-view">
  <div class="history-header">
    <h3>Download History</h3>
    {#if history.length > 0}
      <button class="clear-btn" onclick={handleClear}>Clear All</button>
    {/if}
  </div>

  {#if history.length === 0}
    <div class="empty-state">
      <p>No download history</p>
    </div>
  {:else}
    <div class="history-list">
      {#each history as item (item.id)}
        <div class="history-item" ondblclick={() => handleOpen(item.output_path)}>
          <div class="history-title">{item.title}</div>
          <div class="history-meta">
            <span>{formatSize(item.total_size)}</span>
            <span>{formatDate(item.created_at)}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .history-view { height: 100%; display: flex; flex-direction: column; }
  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  h3 { margin: 0; font-size: 16px; }
  .clear-btn {
    padding: 4px 12px;
    border: 1px solid var(--danger);
    border-radius: 4px;
    background: transparent;
    color: var(--danger);
    font-size: 12px;
    cursor: pointer;
  }
  .clear-btn:hover { background: var(--danger); color: white; }
  .history-list { flex: 1; overflow-y: auto; }
  .history-item {
    padding: 10px 14px;
    background: var(--bg-card);
    border-radius: 6px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .history-item:hover { background: var(--bg-hover); }
  .history-title {
    font-size: 14px;
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .history-meta {
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-secondary);
  }
</style>
