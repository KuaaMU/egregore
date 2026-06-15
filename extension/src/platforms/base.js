/**
 * Base platform adapter.
 * Each platform implements: getInput, sendPrompt, getResponse, isStreaming, getUrl
 */

class PlatformAdapter {
  constructor(name) {
    this.name = name;
  }

  /** Find the input element */
  getInput() {
    throw new Error('Not implemented');
  }

  /** Type prompt and send */
  async sendPrompt(prompt) {
    const input = this.getInput();
    if (!input) throw new Error('Input not found');

    input.focus();
    input.textContent = prompt;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await this.sleep(300);

    // Try pressing Enter
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
  }

  /** Get the latest response text */
  getResponse() {
    throw new Error('Not implemented');
  }

  /** Check if currently streaming */
  isStreaming() {
    return false;
  }

  /** Get the current URL */
  getUrl() {
    return window.location.href;
  }

  /** Get conversation URL (with ID) */
  getConversationUrl() {
    return window.location.href;
  }

  sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }
}

// Export for content scripts
if (typeof window !== 'undefined') {
  window.EgregorePlatform = PlatformAdapter;
}
