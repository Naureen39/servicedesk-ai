"""VoiceAdapter (Section 4.7): defines the same interface as WebChatAdapter so the dialog
manager is channel-agnostic. Real as of Phase 6: `receive` runs faster-whisper STT on raw PCM16
bytes (Section 5/6 item 3) and `send` is a thin passthrough, since real TTS streaming needs
sentence-level granularity and barge-in cancellation that a single `send()` call can't express
-- that streaming lives in `app.services.voice.session.VoiceSession`, which uses
`app.services.voice.tts` directly. This adapter still gives voice the same
`receive(raw) -> Turn` shape chat uses, which is what keeps `handle_turn` itself
channel-agnostic.
"""

from __future__ import annotations

from app.services.channel.base import ChannelAdapter, Response, Turn
from app.services.voice.stt import transcribe_pcm16


class VoiceAdapter(ChannelAdapter):
    channel_name = "voice"

    async def receive(self, raw: bytes | str, conversation_id: str) -> Turn:
        if isinstance(raw, bytes):
            import asyncio

            text = await asyncio.to_thread(transcribe_pcm16, raw)
            return Turn(conversation_id=conversation_id, text=text, channel=self.channel_name)
        return Turn(conversation_id=conversation_id, text=raw, channel=self.channel_name)

    async def send(self, response: Response) -> str:
        # Sentence-split TTS streaming and barge-in live in VoiceSession (Section 5.1 items
        # 5-6), which needs per-sentence control this single-call interface can't express.
        return response.text
