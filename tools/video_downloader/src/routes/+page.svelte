<script lang="ts">
  import { onMount } from 'svelte';
  import '../app.css';
  import { initDownloadsStore } from '$lib/stores/downloads';
  import { initSettingsStore } from '$lib/stores/settings';
  import QueueView from '$lib/components/QueueView.svelte';
  import HistoryView from '$lib/components/HistoryView.svelte';
  import SettingsView from '$lib/components/SettingsView.svelte';
  import AddUrlModal from '$lib/components/AddUrlModal.svelte';

  let activeTab = $state<'queue' | 'history' | 'settings'>('queue');
  let showAddModal = $state(false);

  onMount(() => {
    initDownloadsStore();
    initSettingsStore();
  });
</script>

<div class="app">
  <header class="toolbar">
    <div class="toolbar-left">
      <span class="app-title">Video Downloader</span>
    </div>
    <div class="toolbar-center">
      <button
        class="tab-btn"
        class:active={activeTab === 'queue'}
        onclick={() => activeTab = 'queue'}
      >
        Downloads
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === 'history'}
        onclick={() => activeTab = 'history'}
      >
        History
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === 'settings'}
        onclick={() => activeTab = 'settings'}
      >
        Settings
      </button>
    </div>
    <div class="toolbar-right">
      <button class="add-btn" onclick={() => showAddModal = true}>
        + Add URL
      </button>
    </div>
  </header>

  <main class="content">
    {#if activeTab === 'queue'}
      <QueueView />
    {:else if activeTab === 'history'}
      <HistoryView />
    {:else if activeTab === 'settings'}
      <SettingsView />
    {/if}
  </main>

  <footer class="statusbar">
    <span>API Server: 127.0.0.1:9160</span>
    <span>Ready</span>
  </footer>
</div>

{#if showAddModal}
  <AddUrlModal onclose={() => showAddModal = false} />
{/if}

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }

  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid rgba(255,255,255,0.06);
    -webkit-app-region: drag;
  }

  .toolbar-left, .toolbar-center, .toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
    -webkit-app-region: no-drag;
  }

  .app-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-right: 8px;
  }

  .tab-btn {
    padding: 6px 16px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .tab-btn:hover { background: rgba(255,255,255,0.05); }
  .tab-btn.active {
    background: var(--bg-card);
    color: var(--text-primary);
  }

  .add-btn {
    padding: 6px 16px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
  }
  .add-btn:hover { background: var(--accent-hover); }

  .content {
    flex: 1;
    padding: 16px;
    overflow: hidden;
  }

  .statusbar {
    display: flex;
    justify-content: space-between;
    padding: 6px 16px;
    background: var(--bg-secondary);
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 11px;
    color: var(--text-secondary);
  }
</style>
