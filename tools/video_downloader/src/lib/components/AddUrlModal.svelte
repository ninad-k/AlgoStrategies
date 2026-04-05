<script lang="ts">
  import { addDownload } from '$lib/api';

  let { onclose }: { onclose: () => void } = $props();

  let url = $state('');
  let loading = $state(false);
  let error = $state('');

  async function handleSubmit() {
    const trimmed = url.trim();
    if (!trimmed) return;

    loading = true;
    error = '';
    try {
      await addDownload(trimmed);
      onclose();
    } catch (e: any) {
      error = e?.toString() || 'Failed to add download';
    } finally {
      loading = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') handleSubmit();
    if (e.key === 'Escape') onclose();
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="overlay" onclick={onclose} onkeydown={handleKeydown}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal" onclick={(e) => e.stopPropagation()}>
    <h3>Add Download</h3>
    <p class="subtitle">Paste a video URL from any supported site</p>

    <input
      type="text"
      placeholder="https://www.youtube.com/watch?v=..."
      bind:value={url}
      onkeydown={handleKeydown}
      autofocus
    />

    {#if error}
      <div class="error">{error}</div>
    {/if}

    <div class="modal-actions">
      <button class="btn-cancel" onclick={onclose}>Cancel</button>
      <button class="btn-add" onclick={handleSubmit} disabled={loading || !url.trim()}>
        {loading ? 'Adding...' : 'Download'}
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .modal {
    background: var(--bg-secondary);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 24px;
    width: 480px;
    max-width: 90vw;
  }
  h3 { margin: 0 0 4px 0; font-size: 18px; }
  .subtitle { font-size: 13px; color: var(--text-secondary); margin: 0 0 16px 0; }
  input {
    width: 100%;
    padding: 10px 14px;
    background: var(--bg-card);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 14px;
    box-sizing: border-box;
  }
  input:focus { outline: none; border-color: var(--accent); }
  .error { color: var(--danger); font-size: 13px; margin-top: 8px; }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 20px;
  }
  .btn-cancel, .btn-add {
    padding: 8px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
  }
  .btn-cancel { background: rgba(255,255,255,0.1); color: var(--text-secondary); }
  .btn-add { background: var(--accent); color: white; }
  .btn-add:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-add:hover:not(:disabled) { background: var(--accent-hover); }
</style>
