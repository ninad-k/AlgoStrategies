<script lang="ts">
  import { downloads } from '$lib/stores/downloads';
  import DownloadItem from './DownloadItem.svelte';

  let filterState = $state('all');

  let filtered = $derived(
    filterState === 'all'
      ? $downloads
      : $downloads.filter(d => {
          if (filterState === 'active') return ['downloading', 'extracting', 'queued', 'paused'].includes(d.state);
          if (filterState === 'completed') return d.state === 'completed';
          if (filterState === 'failed') return d.state === 'failed' || d.state === 'cancelled';
          return true;
        })
  );

  let activeCount = $derived($downloads.filter(d => ['downloading', 'extracting', 'queued'].includes(d.state)).length);
</script>

<div class="queue-view">
  <div class="filters">
    <button class="filter-btn" class:active={filterState === 'all'} onclick={() => filterState = 'all'}>
      All ({$downloads.length})
    </button>
    <button class="filter-btn" class:active={filterState === 'active'} onclick={() => filterState = 'active'}>
      Active ({activeCount})
    </button>
    <button class="filter-btn" class:active={filterState === 'completed'} onclick={() => filterState = 'completed'}>
      Completed
    </button>
    <button class="filter-btn" class:active={filterState === 'failed'} onclick={() => filterState = 'failed'}>
      Failed
    </button>
  </div>

  <div class="downloads-list">
    {#if filtered.length === 0}
      <div class="empty-state">
        <div class="empty-icon">&#8615;</div>
        <p>No downloads yet</p>
        <p class="empty-hint">Paste a URL above or use the browser extension</p>
      </div>
    {:else}
      {#each filtered as item (item.id)}
        <DownloadItem {item} />
      {/each}
    {/if}
  </div>
</div>

<style>
  .queue-view {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  .filters {
    display: flex;
    gap: 4px;
    padding: 0 0 12px 0;
  }
  .filter-btn {
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .filter-btn:hover { background: var(--bg-card); }
  .filter-btn.active {
    background: var(--accent);
    color: white;
  }
  .downloads-list {
    flex: 1;
    overflow-y: auto;
    padding-right: 4px;
  }
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 300px;
    color: var(--text-secondary);
  }
  .empty-icon {
    font-size: 48px;
    margin-bottom: 12px;
    opacity: 0.3;
  }
  .empty-hint {
    font-size: 13px;
    opacity: 0.6;
  }
</style>
