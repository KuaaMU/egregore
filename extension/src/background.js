/**
 * Egregore Background Service Worker.
 *
 * Communicates with:
 * 1. Content scripts (via chrome.runtime messages)
 * 2. Local daemon (via WebSocket on localhost:9225)
 *
 * Flow:
 *   Daemon → WebSocket → Background → Content Script → Platform DOM
 *   Platform DOM → Content Script → Background → WebSocket → Daemon
 */

const DAEMON_URL = 'ws://localhost:9225';
let ws = null;
let reconnectTimer = null;

// === WebSocket to Daemon ===

function connectDaemon() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  try {
    ws = new WebSocket(DAEMON_URL);

    ws.onopen = () => {
      console.log('[Egregore] Connected to daemon');
      if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null; }
    };

    ws.onclose = () => {
      console.log('[Egregore] Disconnected from daemon');
      scheduleReconnect();
    };

    ws.onerror = () => {
      // Silent — daemon might not be running
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleDaemonMessage(msg);
      } catch (e) { /* ignore */ }
    };
  } catch (e) {
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setInterval(connectDaemon, 5000);
}

function handleDaemonMessage(msg) {
  // Forward commands from daemon to content scripts
  if (msg.type === 'send_prompt') {
    chrome.tabs.query({ url: getPlatformUrl(msg.platform) }, (tabs) => {
      if (tabs.length > 0) {
        chrome.tabs.sendMessage(tabs[0].id, {
          type: 'send_prompt',
          prompt: msg.prompt,
        });
      }
    });
  }
}

function getPlatformUrl(platform) {
  const urls = {
    chatgpt: 'https://chatgpt.com/*',
    grok: 'https://grok.com/*',
    kimi: 'https://kimi.moonshot.cn/*',
    qwen: 'https://tongyi.aliyun.com/*',
    doubao: 'https://www.doubao.com/*',
  };
  return urls[platform] || '*';
}

// === Message handling from content scripts ===

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'platform_ready') {
    // Content script reports platform is ready
    console.log(`[Egregore] ${msg.platform} ready at ${sender.tab?.url}`);
    sendResponse({ ok: true });
  }

  if (msg.type === 'response_complete') {
    // Content script reports response is complete
    // Forward to daemon
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'response',
        platform: msg.platform,
        content: msg.content,
        url: msg.url,
        conversationUrl: msg.conversationUrl,
      }));
    }
    sendResponse({ ok: true });
  }

  return true;
});

// === Init ===
connectDaemon();
