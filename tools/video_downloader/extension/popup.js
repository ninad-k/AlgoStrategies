const API_BASE = 'http://127.0.0.1:9160';

const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const videoList = document.getElementById('videoList');

let appConnected = false;

// Check if desktop app is running
async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(2000) });
    const data = await resp.json();
    appConnected = true;
    statusDot.className = 'dot connected';
    statusText.textContent = `Connected (${data.queue_size} in queue)`;
  } catch (e) {
    appConnected = false;
    statusDot.className = 'dot disconnected';
    statusText.textContent = 'App not running';
  }
}

// Get videos from content script
async function loadVideos() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    videoList.innerHTML = '<div class="no-videos">No active tab</div>';
    return;
  }

  chrome.tabs.sendMessage(tab.id, { type: 'GET_VIDEOS' }, (videos) => {
    if (chrome.runtime.lastError || !videos || videos.length === 0) {
      videoList.innerHTML = '<div class="no-videos">No videos detected on this page</div>';
      return;
    }
    renderVideos(videos);
  });
}

function renderVideos(videos) {
  videoList.innerHTML = '';

  videos.forEach(video => {
    const item = document.createElement('div');
    item.className = 'video-item';

    const info = document.createElement('div');
    info.className = 'video-info';

    const title = document.createElement('div');
    title.className = 'video-title';
    title.textContent = video.title || 'Untitled';
    title.title = video.title || video.url;

    const source = document.createElement('div');
    source.className = 'video-source';
    source.textContent = video.source;

    info.appendChild(title);
    info.appendChild(source);

    const btn = document.createElement('button');
    btn.className = 'download-btn';
    btn.textContent = 'Download';

    if (!appConnected) {
      btn.disabled = true;
      btn.textContent = 'App offline';
    }

    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Sent!';

      try {
        await fetch(`${API_BASE}/api/download`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: video.url,
            title: video.title,
            page_url: video.url
          })
        });
      } catch (e) {
        btn.textContent = 'Error';
        btn.disabled = false;
        setTimeout(() => { btn.textContent = 'Download'; }, 2000);
      }
    });

    item.appendChild(info);
    item.appendChild(btn);
    videoList.appendChild(item);
  });
}

// Initialize
checkHealth().then(loadVideos);
