/**
 * Egregore Bridge — ChatGPT Content Script
 *
 * Injects into ChatGPT pages. Exposes a simple API for:
 * - Sending prompts
 * - Reading responses
 * - Detecting streaming state
 *
 * Usage from console or other extensions:
 *   await window.egregore.send("What is 2+2?")
 *   // => "2 + 2 = 4"
 *
 *   window.egregore.isStreaming()
 *   // => true/false
 *
 * Architecture:
 *   Content Script (this) → Background Script → Local Daemon → Egregore
 */

(() => {
  "use strict";

  // === DOM Selectors ===
  // These may need updating as ChatGPT changes its UI.
  const SELECTORS = {
    input: () => document.querySelector("#prompt-textarea") || document.querySelector('[contenteditable="true"]'),
    sendButton: () => document.querySelector('[data-testid="send-button"]'),
    stopButton: () => document.querySelector('[data-testid="stop-button"]'),
    responses: () => document.querySelectorAll('[data-message-author-role="assistant"]'),
    lastResponse: () => {
      const els = document.querySelectorAll('[data-message-author-role="assistant"]');
      return els.length > 0 ? els[els.length - 1] : null;
    },
  };

  // === State ===
  let lastResponseText = "";
  let streamingObserver = null;
  let streamingCallbacks = [];

  // === Core API ===

  /**
   * Send a prompt to ChatGPT and wait for the response.
   * @param {string} prompt - The prompt to send
   * @param {number} timeoutMs - Timeout in milliseconds
   * @returns {Promise<string>} The response text
   */
  async function send(prompt, timeoutMs = 60000) {
    const input = SELECTORS.input();
    if (!input) throw new Error("Cannot find ChatGPT input");

    // Record current response before sending
    const oldResponse = getLatestResponse();

    // Type prompt
    input.focus();
    input.textContent = prompt;
    input.dispatchEvent(new Event("input", { bubbles: true }));

    // Wait a bit for UI to update
    await sleep(300);

    // Send (press Enter)
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));

    // Wait for NEW response
    return waitForNewResponse(oldResponse, timeoutMs);
  }

  /**
   * Get the latest response text.
   * @returns {string} The response text
   */
  function getLatestResponse() {
    const el = SELECTORS.lastResponse();
    return el ? el.textContent.trim() : "";
  }

  /**
   * Check if ChatGPT is currently streaming.
   * @returns {boolean}
   */
  function isStreaming() {
    return !!SELECTORS.stopButton();
  }

  /**
   * Check if the page is ready (input is visible).
   * @returns {boolean}
   */
  function isReady() {
    return !!SELECTORS.input();
  }

  /**
   * Subscribe to streaming updates.
   * @param {function} callback - Called with each new token
   * @returns {function} Unsubscribe function
   */
  function onStream(callback) {
    streamingCallbacks.push(callback);
    startStreamingObserver();
    return () => {
      streamingCallbacks = streamingCallbacks.filter((cb) => cb !== callback);
      if (streamingCallbacks.length === 0) stopStreamingObserver();
    };
  }

  // === Streaming Observer ===

  function startStreamingObserver() {
    if (streamingObserver) return;

    const target = document.body;
    streamingObserver = new MutationObserver(() => {
      const current = getLatestResponse();
      if (current !== lastResponseText) {
        const newPart = current.slice(lastResponseText.length);
        if (newPart) {
          streamingCallbacks.forEach((cb) => cb(newPart, current));
        }
        lastResponseText = current;
      }
    });

    streamingObserver.observe(target, { childList: true, subtree: true, characterData: true });
  }

  function stopStreamingObserver() {
    if (streamingObserver) {
      streamingObserver.disconnect();
      streamingObserver = null;
    }
  }

  // === Helpers ===

  async function waitForNewResponse(oldResponse, timeoutMs) {
    const start = Date.now();
    let lastText = oldResponse;
    let stableCount = 0;
    const stableThreshold = 4;
    let newDetected = false;

    await sleep(1000);

    while (Date.now() - start < timeoutMs) {
      const current = getLatestResponse();

      if (!newDetected) {
        if (current && current !== oldResponse) {
          newDetected = true;
          lastText = current;
          stableCount = 0;
        } else {
          await sleep(500);
          continue;
        }
      }

      if (current && current !== lastText) {
        lastText = current;
        stableCount = 0;
      } else if (current) {
        stableCount++;
      }

      if (stableCount >= stableThreshold) break;
      if (!isStreaming() && stableCount >= 2) break;

      await sleep(500);
    }

    return lastText;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // === Expose API ===

  window.egregore = {
    send,
    getLatestResponse,
    isStreaming,
    isReady,
    onStream,
    platform: "chatgpt",
    version: "0.1.0",
  };

  console.log("[Egregore] Bridge loaded for ChatGPT");
})();
