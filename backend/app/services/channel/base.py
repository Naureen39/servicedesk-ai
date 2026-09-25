"""Common channel adapter interface (Section 4.7): `receive(text|audio) -> Turn`,
`send(Response)`. Implementations: WebChatAdapter (this phase), VoiceAdapter (audio I/O real
in Phase 6). A future telephony adapter plugs in here without touching the dialog manager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Turn:
    conversation_id: str
    text: str
    channel: str


@dataclass
class Response:
    text: str
    escalated: bool = False


class ChannelAdapter(ABC):
    @abstractmethod
    async def receive(self, raw: bytes | str, conversation_id: str) -> Turn: ...

    @abstractmethod
    async def send(self, response: Response) -> bytes | str: ...
