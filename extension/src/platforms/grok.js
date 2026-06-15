/**
 * Grok platform adapter.
 */

(function() {
  'use strict';

  const PLATFORM = 'grok';

  function getInput() {
    return document.querySelector('[role="textbox"]') ||
           document.querySelector('[contenteditable="true"]') ||
           document.querySelector('textarea');
  }

  function getResponse() {
    const els = document.querySelectorAll('[data-testid*="assistant"], .message-bubble, [class*="message"]');
    if (els.length === 0) return '';
    return els[els.length - 1].textContent?.trim() || '';
  }

  function isStreaming() {
    // Grok shows a stop button during streaming
    const stopBtn = document.querySelector('[data-testid="stop-button"], button[aria-label*="stop"]');
    return !!stopBtn;
  }

  async function sendPrompt(prompt) {
    const input = getInput();
    if (!input) throw new Error('Grok input not found');

    input.focus();
    if (input.getAttribute('contenteditable') === 'true') {
      input.textContent = prompt;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      input.value = prompt;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    await new Promise(r => setTimeout(r, 300));

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
  }

  function waitForResponse(oldResponse, timeoutMs = 60000) {
    return new Promise((resolve) => {
      const start = Date.now();
      let lastText = oldResponse;
      let stableCount = 0;
      let newDetected = false;

      const check = () => {
        if (Date.now() - start > timeoutMs) { resolve(lastText); return; }
        const current = getResponse();
        if (!newDetected) {
          if (current && current !== oldResponse) { newDetected = true; lastText = current; stableCount = 0; }
          else { setTimeout(check, 500); return; }
        }
        if (current && current !== lastText) { lastText = current; stableCount = 0; }
        else if (current) { stableCount++; }
        if (stableCount >= 4 || (!isStreaming() && stableCount >= 2)) { resolve(lastText); return; }
        setTimeout(check, 500);
      };
      setTimeout(check, 1000);
    });
  }

  window.egregore = {
    platform: PLATFORM, getInput, getResponse, isStreaming, sendPrompt, waitForResponse,
    getUrl: () => window.location.href,
    getConversationUrl: () => window.location.href,
    isReady: () => !!getInput(),
  };

  console.log('[Egregore] Grok adapter loaded');
})();
