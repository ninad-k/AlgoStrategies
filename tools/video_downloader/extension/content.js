// Video detection content script
// Scans pages for video content and reports to background service worker

(function() {
  'use strict';

  const KNOWN_VIDEO_SITES = {
    'www.youtube.com': { extract: extractYouTube },
    'youtube.com': { extract: extractYouTube },
    'm.youtube.com': { extract: extractYouTube },
    'youtu.be': { extract: extractYouTubeShort },
    'vimeo.com': { extract: extractVimeo },
    'www.vimeo.com': { extract: extractVimeo },
    'www.dailymotion.com': { extract: extractDailymotion },
    'www.twitch.tv': { extract: extractTwitch },
    'twitter.com': { extract: extractTwitter },
    'x.com': { extract: extractTwitter },
    'www.instagram.com': { extract: extractGenericPage },
    'www.facebook.com': { extract: extractGenericPage },
    'www.tiktok.com': { extract: extractGenericPage },
    'www.reddit.com': { extract: extractGenericPage },
  };

  const EMBED_DOMAINS = [
    'player.vimeo.com',
    'www.youtube.com',
    'www.youtube-nocookie.com',
    'www.dailymotion.com',
    'player.twitch.tv',
  ];

  let detectedVideos = new Map(); // url -> {title, source}

  function extractYouTube() {
    const params = new URLSearchParams(window.location.search);
    const videoId = params.get('v');
    if (videoId) {
      const title = document.title.replace(' - YouTube', '').trim();
      return [{ url: window.location.href, title, source: 'YouTube' }];
    }
    // Shorts
    const shortsMatch = window.location.pathname.match(/\/shorts\/([^/?]+)/);
    if (shortsMatch) {
      return [{ url: window.location.href, title: document.title, source: 'YouTube Shorts' }];
    }
    return [];
  }

  function extractYouTubeShort() {
    return [{ url: window.location.href, title: document.title, source: 'YouTube' }];
  }

  function extractVimeo() {
    const match = window.location.pathname.match(/\/(\d+)/);
    if (match) {
      return [{ url: window.location.href, title: document.title, source: 'Vimeo' }];
    }
    return [];
  }

  function extractDailymotion() {
    if (window.location.pathname.includes('/video/')) {
      return [{ url: window.location.href, title: document.title, source: 'Dailymotion' }];
    }
    return [];
  }

  function extractTwitch() {
    if (window.location.pathname.match(/\/videos\/\d+/)) {
      return [{ url: window.location.href, title: document.title, source: 'Twitch' }];
    }
    return [];
  }

  function extractTwitter() {
    if (window.location.pathname.match(/\/status\/\d+/)) {
      return [{ url: window.location.href, title: document.title, source: 'Twitter/X' }];
    }
    return [];
  }

  function extractGenericPage() {
    return [{ url: window.location.href, title: document.title, source: window.location.hostname }];
  }

  function scanDOM() {
    const videos = [];

    // Layer 1: Direct <video> and <source> elements
    document.querySelectorAll('video').forEach(video => {
      const src = video.src || video.currentSrc;
      if (src && !src.startsWith('blob:') && !src.startsWith('data:')) {
        videos.push({
          url: src,
          title: document.title,
          source: 'HTML5 Video'
        });
      }
      video.querySelectorAll('source').forEach(source => {
        if (source.src && !source.src.startsWith('blob:') && !source.src.startsWith('data:')) {
          videos.push({
            url: source.src,
            title: document.title,
            source: 'HTML5 Video'
          });
        }
      });
    });

    // Layer 2: iframe embeds from known video domains
    document.querySelectorAll('iframe').forEach(iframe => {
      if (!iframe.src) return;
      try {
        const iframeUrl = new URL(iframe.src);
        for (const domain of EMBED_DOMAINS) {
          if (iframeUrl.hostname === domain) {
            // Convert embed URL to page URL for yt-dlp
            let videoUrl = iframe.src;
            if (domain.includes('youtube')) {
              const match = iframeUrl.pathname.match(/\/embed\/([^/?]+)/);
              if (match) {
                videoUrl = `https://www.youtube.com/watch?v=${match[1]}`;
              }
            }
            videos.push({
              url: videoUrl,
              title: document.title,
              source: `${domain} embed`
            });
          }
        }
      } catch (e) { /* invalid URL */ }
    });

    // Layer 3: og:video meta tags
    const ogVideo = document.querySelector('meta[property="og:video"]') ||
                     document.querySelector('meta[property="og:video:url"]');
    if (ogVideo) {
      const content = ogVideo.getAttribute('content');
      if (content) {
        videos.push({
          url: content,
          title: document.title,
          source: 'og:video'
        });
      }
    }

    return videos;
  }

  function detectVideos() {
    detectedVideos.clear();

    // Check known sites first
    const hostname = window.location.hostname;
    const siteConfig = KNOWN_VIDEO_SITES[hostname];
    if (siteConfig) {
      const siteVideos = siteConfig.extract();
      siteVideos.forEach(v => detectedVideos.set(v.url, v));
    }

    // Then scan DOM
    const domVideos = scanDOM();
    domVideos.forEach(v => {
      if (!detectedVideos.has(v.url)) {
        detectedVideos.set(v.url, v);
      }
    });

    // Report to background
    const videoList = Array.from(detectedVideos.values());
    chrome.runtime.sendMessage({
      type: 'VIDEOS_DETECTED',
      videos: videoList,
      count: videoList.length
    });
  }

  // Initial scan
  detectVideos();

  // Watch for dynamic content
  const observer = new MutationObserver((mutations) => {
    let hasNewMedia = false;
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          const el = node;
          if (el.tagName === 'VIDEO' || el.tagName === 'IFRAME' ||
              el.querySelector?.('video, iframe')) {
            hasNewMedia = true;
            break;
          }
        }
      }
      if (hasNewMedia) break;
    }
    if (hasNewMedia) {
      setTimeout(detectVideos, 500); // Debounce
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  // Listen for popup requests
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'GET_VIDEOS') {
      detectVideos(); // Rescan
      sendResponse(Array.from(detectedVideos.values()));
    }
    return true;
  });
})();
