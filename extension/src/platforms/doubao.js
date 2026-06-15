/**
 * Doubao platform adapter.
 */

(function() {
  'use strict';

  function getInput() {
    return document.querySelector('textarea[class*="semi-input"]') ||
           document.querySelector('textarea') ||
           document.querySelector('[role="textbox"]');
  }

  function getResponse() {
    // Doubao responses are in the message list
    const els = document.querySelectorAll('[class*="message-list"] > div, [class*="receive"]');
    if (els.length === 0) return '';
    const text = els[els.length - 1].textContent?.trim() || '';
    if (text.startsWith('{') || text.includes('{"data":')) return '';
    return text;
  }

  function isStreaming() {
    return !!document.querySelector('[class*="stop"]');
  }

  async function sendPrompt(prompt) {
    const input = getInput();
    if (!input) throw new Error('Doubao input not found');
    input.focus();
    input.value = prompt;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 300));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
  }

  function waitForResponse(oldResponse, timeoutMs = 60000) {
    return new Promise((resolve) => {
      const start = Date.now();
      let lastText = oldResponse, stableCount = 0, newDetected = false;
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
    platform: 'doubao', getInput, getResponse, isStreaming, sendPrompt, waitForResponse,
    getUrl: () => window.location.href, getConversationUrl: () => window.location.href,
    isReady: () => !!getInput(),
  };
  console.log('[Egregore] Doubao adapter loaded');
})();
