/**
 * Egregore Bridge — Background Service Worker
 *
 * Communicates with:
 * 1. Content scripts (via chrome.runtime messages)
 * 2. Local daemon (via WebSocket)
 *
 * Architecture:
 *   Content Script ↔ Background Script ↔ Local Daemon
 *
 * The daemon runs on localhost:8765 and provides:
 *   POST /send    — send a prompt to a platform
 *   GET  /status  — check platform status
 *   WebSocket     — streaming updates
 */

const DAEMON_URL = "ws://localhost:8765";
let ws = null;
let reconnectTimer = null;

// === WebSocket to Daemon ===

function connectDaemon() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  try {
    ws = new WebSocket(DAEMON_URL);

    ws.onopen = () => {
      console.log("[Egregore] Connected to daemon");
      if (reconnectTimer) {
        clearInterval(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onclose = () => {
      console.log("[Egregore] Disconnected from daemon");
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.log("[Egregore] Daemon connection error");
    };

    ws.onmessage = (event) => {
      handleDaemonMessage(event.data);
    };
  } catch (e) {
    console.log("[Egregore] Cannot connect to daemon");
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setInterval(() => {
    connectDaemon();
  }, 5000);
}

function handleDaemonMessage(data) {
  try {
    const msg = JSON.parse(data);
    // Forward to content script if needed
    if (msg.tabId) {
      chrome.tabs.sendMessage(msg.tabId, msg).catch(() => {});
    }
  } catch (e) {
    // ignore
  }
}

// === Message handling from content scripts ===

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "egregore:send") {
    // Forward to daemon
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "send",
        platform: msg.platform,
        prompt: msg.prompt,
        tabId: sender.tab?.id,
      }));
    }
    sendResponse({ ok: true });
  }

  if (msg.type === "egregore:response") {
    // Forward response to daemon
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "response",
        platform: msg.platform,
        content: msg.content,
        tabId: sender.tab?.id,
      }));
    }
  }

  if (msg.type === "egregore:status") {
    sendResponse({
      daemonConnected: ws && ws.readyState === WebSocket.OPEN,
    });
  }

  return true; // Keep message channel open for async response
});

// === Init ===
connectDaemon();
