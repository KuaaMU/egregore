"""Test ChatGPT provider with CDP transport.

Usage:
    1. Start Chrome: chrome.exe --remote-debugging-port=9222
    2. Login to ChatGPT
    3. Run: uv run python -m egregore.labs.transport.test_chatgpt
"""

import asyncio

from egregore.providers.cdp_transport import CdpTransport
from egregore.providers.chatgpt.connector import ChatGPTProvider
from egregore.providers.metrics import ProviderMetrics


async def main():
    transport = CdpTransport()
    provider = ChatGPTProvider(transport)
    metrics = ProviderMetrics(provider_name="chatgpt")

    try:
        await provider.connect()
        print(f"[OK] Connected. Status: {provider.status.value}")

        prompts = ["What is 2+2?", "Name three programming languages."]
        for i, prompt in enumerate(prompts):
            r = await provider.send(prompt, timeout_ms=30000)
            if r.success:
                metrics.record_success(r.latency_ms)
                print(f"[{i+1}] OK ({r.latency_ms:.0f}ms): {r.content[:150]}")
            else:
                metrics.record_failure("error", r.error or "")
                print(f"[{i+1}] FAIL: {r.error}")

        print(f"\n{metrics.summary()}")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        await provider.close()
        print("[OK] Done")


if __name__ == "__main__":
    asyncio.run(main())
