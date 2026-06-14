"""Test Grok provider.

Usage:
    1. Start Chrome: chrome.exe --remote-debugging-port=9222 --user-data-dir=...
    2. Login to Grok (https://grok.com/)
    3. Run: uv run python -m egregore.labs.transport.test_grok
"""

import asyncio

from egregore.providers.grok.connector import GrokProvider
from egregore.providers.metrics import ProviderMetrics


async def main():
    print("Connecting to Grok...")
    provider = GrokProvider()
    metrics = ProviderMetrics(provider_name="grok")

    try:
        await provider.connect()
        print(f"[OK] Connected. Status: {provider.status.value}")

        # Test prompts
        prompts = [
            "What is 2+2?",
            "Name three programming languages.",
            "What is the capital of France?",
        ]

        for i, prompt in enumerate(prompts):
            print(f"\n[{i+1}] Sending: {prompt}")
            response = await provider.send(prompt, timeout_ms=30000)

            if response.success:
                metrics.record_success(response.latency_ms)
                print(f"[OK] Response ({response.latency_ms:.0f}ms):")
                print(f"  {response.content[:200]}")
            else:
                metrics.record_failure("error", response.error or "")
                print(f"[FAIL] {response.error}")

        print(f"\n{metrics.summary()}")

    except Exception as e:
        print(f"\n[ERROR] {e}")

    finally:
        await provider.close()
        print("[OK] Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
