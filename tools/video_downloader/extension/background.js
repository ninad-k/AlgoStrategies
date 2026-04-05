// Background service worker - manages badge and relays messages

const tabVideos = new Map(); // tabId -> videos[]

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'VIDEOS_DETECTED' && sender.tab) {
    const tabId = sender.tab.id;
    tabVideos.set(tabId, msg.videos);

    const count = msg.count;
    chrome.action.setBadgeText({
      text: count > 0 ? count.toString() : '',
      tabId
    });
    chrome.action.setBadgeBackgroundColor({
      color: '#3b82f6',
      tabId
    });
  }
});

// Clean up when tabs are closed
chrome.tabs.onRemoved.addListener((tabId) => {
  tabVideos.delete(tabId);
});

// Reset badge on navigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'loading') {
    tabVideos.delete(tabId);
    chrome.action.setBadgeText({ text: '', tabId });
  }
});
