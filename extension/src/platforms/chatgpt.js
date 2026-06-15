/**
 * ChatGPT platform adapter.
 * Interacts with ChatGPT's web UI via DOM.
 */

(function() {
  'use strict';

  const PLATFORM = 'chatgpt';

  // Selectors — update these when ChatGPT changes its UI
  const SELECTORS = {
    input: '#prompt-textarea, [contenteditable="true"]',
    sendButton: '[data-testid="send-button"]',
    stopButton: '[data-testid="stop-button"]',
    response: '[data-message-author-role="assistant"]',
    lastResponse: '[data-message-author-role="assistant"]:last-of-type',
  };

  let lastResponseText = '';

  function getInput() {
    return document.querySelector(SELECTORS.input);
  }

  function getResponse() {
    const els = document.querySelectorAll(SELECTORS.response);
    if (els.length === 0) return '';
    return els[els.length - 1].textContent?.trim() || '';
  }

  function isStreaming() {
    return !!document.querySelector(SELECTORS.stopButton);
  }

  async function sendPrompt(prompt) {
    const input = getInput();
    if (!input) throw new Error('ChatGPT input not found');

    input.focus();
    // For contenteditable
    if (input.getAttribute('contenteditable') === 'true') {
      input.textContent = prompt;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      input.value = prompt;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    await new Promise(r => setTimeout(r, 300));

    // Click send button or press Enter
    const sendBtn = document.querySelector(SELECTORS.sendButton);
    if (sendBtn) {
      sendBtn.click();
    } else {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
    }
  }

  function waitForResponse(oldResponse, timeoutMs = 60000) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      let lastText = oldResponse;
      let stableCount = 0;
      const stableThreshold = 4;
      let newDetected = false;

      const check = () => {
        if (Date.now() - start > timeoutMs) {
          resolve(lastText);
          return;
        }

        const current = getResponse();

        if (!newDetected) {
          if (current && current !== oldResponse) {
            newDetected = true;
            lastText = current;
            stableCount = 0;
          } else {
            setTimeout(check, 500);
            return;
          }
        }

        if (current && current !== lastText) {
          lastText = current;
          stableCount = 0;
        } else if (current) {
          stableCount++;
        }

        if (stableCount >= stableThreshold) {
          resolve(lastText);
          return;
        }

        if (!isStreaming() && stableCount >= 2) {
          resolve(lastText);
          return;
        }

        setTimeout(check, 500);
      };

      setTimeout(check, 1000);
    });
  }

  // Expose to Egregore bridge
  window.egregore = {
    platform: PLATFORM,
    getInput,
    getResponse,
    isStreaming,
    sendPrompt,
    waitForResponse,
    getUrl: () => window.location.href,
    getConversationUrl: () => window.location.href,
    isReady: () => !!getInput(),
  };

  console.log('[Egregore] ChatGPT adapter loaded');
})();
