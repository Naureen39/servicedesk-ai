"""WebChatAdapter (Section 4.7): the text channel, real and complete in this phase."""

from __future__ import annotations

from app.services.channel.base import ChannelAdapter, Response, Turn


class WebChatAdapter(ChannelAdapter):
    channel_name = "chat"

    async def receive(self, raw: bytes | str, conversation_id: str) -> Turn:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return Turn(conversation_id=conversation_id, text=text, channel=self.channel_name)

    async def send(self, response: Response) -> str:
        return response.text
