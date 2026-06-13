"""Message entities — the atomic unit of communication in Egregore.

In an event-driven system, everything is a message. A user prompt is a message.
A provider response is a message. A consensus result is a message.

Design decisions:
- Messages are immutable (frozen Pydantic models)
- Every message has a unique ID and timestamp
- Messages carry metadata for observability
- The role enum constrains the message space
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Who sent this message.

    Extensible: future roles might include CRITIC, MODERATOR, MEMORY.
    """

    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    PROVIDER = "provider"  # A specific LLM provider's response
    CONSENSUS = "consensus"  # The synthesized consensus
    CRITIC = "critic"  # V3: Debate engine
    MEMORY = "memory"  # V5: Memory system


class ProviderMeta(BaseModel):
    """Metadata about which provider generated this response.

    This is critical for observability and V4's dynamic weighting.
    """

    provider_id: str
    model: str
    latency_ms: float = 0.0
    token_count: int = 0
    temperature: float = 0.7


class Message(BaseModel):
    """A single message in the Egregore system.

    Messages are the fundamental unit. They flow through the event bus,
    get stored in memory, and form the basis of all reasoning.

    Why frozen? Immutability prevents accidental mutation and makes
    messages safe to share across async tasks without locks.
    """

    model_config = {"frozen": True}

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)
    provider_meta: ProviderMeta | None = None

    @property
    def is_provider_response(self) -> bool:
        return self.role == MessageRole.PROVIDER

    @property
    def is_user_prompt(self) -> bool:
        return self.role == MessageRole.USER


class Conversation(BaseModel):
    """An ordered sequence of messages forming a conversation.

    This is the aggregate root for a conversation session.
    Future: will integrate with the memory system (V5).
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, message: Message) -> None:
        self.messages.append(message)

    @property
    def last_message(self) -> Message | None:
        return self.messages[-1] if self.messages else None

    @property
    def provider_responses(self) -> list[Message]:
        return [m for m in self.messages if m.is_provider_response]
