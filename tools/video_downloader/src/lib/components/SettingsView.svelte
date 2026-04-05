<script lang="ts">
  import { settings, saveSettings } from '$lib/stores/settings';
  import type { AppSettings } from '$lib/api';

  let local = $state<AppSettings>({ ...$settings });
  let saved = $state(false);

  $effect(() => {
    local = { ...$settings };
  });

  async function handleSave() {
    await saveSettings(local);
    saved = true;
    setTimeout(() => saved = false, 2000);
  }
</script>

<div class="settings-view">
  <h3>Settings</h3>

  <div class="setting-group">
    <label>Download Directory</label>
    <input type="text" bind:value={local.download_dir} />
  </div>

  <div class="setting-group">
    <label>Max Concurrent Downloads</label>
    <input type="number" min="1" max="10" bind:value={local.max_concurrent} />
  </div>

  <div class="setting-group">
    <label>Connections Per Download</label>
    <input type="number" min="1" max="32" bind:value={local.connections_per_download} />
    <span class="hint">More connections = faster download (if server supports it)</span>
  </div>

  <div class="setting-group">
    <label>Default Quality</label>
    <select bind:value={local.default_quality}>
      <option value="best">Best Available</option>
      <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
      <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
      <option value="bestvideo[height<=480]+bestaudio/best">480p</option>
      <option value="bestaudio/best">Audio Only</option>
    </select>
  </div>

  <div class="setting-group checkbox">
    <label>
      <input type="checkbox" bind:checked={local.auto_start} />
      Auto-start downloads when added
    </label>
  </div>

  <div class="setting-group checkbox">
    <label>
      <input type="checkbox" bind:checked={local.show_format_dialog} />
      Show format picker before each download
    </label>
  </div>

  <div class="save-row">
    <button class="save-btn" onclick={handleSave}>
      {saved ? 'Saved!' : 'Save Settings'}
    </button>
  </div>
</div>

<style>
  .settings-view { max-width: 500px; }
  h3 { margin: 0 0 20px 0; font-size: 16px; }
  .setting-group {
    margin-bottom: 16px;
  }
  .setting-group label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 6px;
  }
  .setting-group.checkbox label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: var(--text-primary);
  }
  input[type="text"], input[type="number"], select {
    width: 100%;
    padding: 8px 12px;
    background: var(--bg-card);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 14px;
    box-sizing: border-box;
  }
  input[type="text"]:focus, input[type="number"]:focus, select:focus {
    outline: none;
    border-color: var(--accent);
  }
  input[type="number"] { width: 120px; }
  select { width: auto; min-width: 200px; }
  .hint {
    display: block;
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 4px;
  }
  input[type="checkbox"] {
    accent-color: var(--accent);
  }
  .save-row { margin-top: 24px; }
  .save-btn {
    padding: 8px 24px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .save-btn:hover { background: var(--accent-hover); }
</style>
