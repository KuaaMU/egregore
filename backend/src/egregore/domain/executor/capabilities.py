"""Capabilities — what a provider can do, not who it is.

This is the most important design correction.

Instead of:
    class ChatGPTExecutor: ...
    class ClaudeExecutor: ...
    class GeminiExecutor: ...

We model:
    class Capabilities:
        streaming: bool
        thinking: bool
        vision: bool
        artifacts: bool
        tool_use: bool

A provider is just a bundle of capabilities + a transport.
Claude and GPT are not special objects — they're configurations.

Why?
1. New capabilities compose, not multiply
2. UI can adapt based on capabilities, not provider identity
3. Testing is capability-scoped, not provider-scoped
4. Future: route questions to providers based on required capabilities

Pattern: Capability / Trait / Feature Flag
"""

from __future__ import annotations

from pydantic import BaseModel


class Capabilities(BaseModel):
    """Describes what a provider/transport can do.

    This drives:
    - UI rendering (show thinking panel if thinking=True)
    - Parser selection (use ThinkingParser if thinking=True)
    - Routing (send vision tasks to vision-capable providers)
    - Test selection (skip vision tests if vision=False)
    """

    model_config = {"frozen": True}

    # Core
    streaming: bool = True  # Does it stream tokens?
    thinking: bool = False  # Does it have a thinking/reasoning phase?
    vision: bool = False  # Can it process images?
    artifacts: bool = False  # Does it generate artifacts (code, files)?

    # Agent capabilities
    tool_use: bool = False  # Can it call tools/functions?
    web_search: bool = False  # Can it search the web?
    code_execution: bool = False  # Can it execute code?

    # UI hints
    supports_system_prompt: bool = True  # Does it accept system prompts?
    max_input_tokens: int = 128000  # Context window size
    supports_continuation: bool = False  # Can it continue after stopping?

    @classmethod
    def chatgpt(cls) -> Capabilities:
        """ChatGPT's capabilities."""
        return cls(
            streaming=True,
            thinking=False,  # o1/o3 have it, but GPT-4o doesn't
            vision=True,
            artifacts=True,
            tool_use=True,
            web_search=True,
            code_execution=True,
            supports_system_prompt=True,
            max_input_tokens=128000,
        )

    @classmethod
    def claude(cls) -> Capabilities:
        """Claude's capabilities."""
        return cls(
            streaming=True,
            thinking=True,
            vision=True,
            artifacts=True,
            tool_use=True,
            web_search=False,
            code_execution=False,
            supports_system_prompt=True,
            max_input_tokens=200000,
            supports_continuation=True,
        )

    @classmethod
    def gemini(cls) -> Capabilities:
        """Gemini's capabilities."""
        return cls(
            streaming=True,
            thinking=True,
            vision=True,
            artifacts=False,
            tool_use=True,
            web_search=True,
            code_execution=True,
            supports_system_prompt=True,
            max_input_tokens=1000000,
        )

    @classmethod
    def deepseek(cls) -> Capabilities:
        """DeepSeek's capabilities."""
        return cls(
            streaming=True,
            thinking=True,
            vision=False,
            artifacts=False,
            tool_use=False,
            web_search=False,
            code_execution=False,
            supports_system_prompt=True,
            max_input_tokens=64000,
        )

    @classmethod
    def mock(cls) -> Capabilities:
        """Mock provider — minimal capabilities."""
        return cls(
            streaming=True,
            thinking=False,
            vision=False,
            artifacts=False,
        )

    def supports(self, capability: str) -> bool:
        """Check if a specific capability is supported.

        Usage:
            if caps.supports("thinking"):
                # use thinking parser
        """
        return getattr(self, capability, False)
