"""Orchestrates one `WS /voice/session` connection (Phase 6): a background reader task
consumes incoming WebSocket frames (binary = one VAD-segmented speech utterance from the
client, JSON text = control messages) into a queue, while the main loop processes utterances
one at a time through the same dialog manager chat uses (Section 4.2), streaming TTS audio
back sentence by sentence so playback can start on the first sentence without waiting for the
whole reply to synthesize.

Barge-in (item 6): the reader task sets `interrupt_event` the instant an `{"type":
"interrupt"}` control message arrives -- independent of whatever the main loop is doing --
and the streaming loop checks it between sentences, so a user interrupting mid-reply gets the
rest of that reply's audio cut off at the next sentence boundary.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assistant import Conversation
from app.services.channel.voice import VoiceAdapter
from app.services.dialog.manager import handle_turn
from app.services.llm.factory import get_router
from app.services.voice import tts
from app.services.voice.spokenize import spokenize


class VoiceSession:
    def __init__(self, websocket: WebSocket, db: AsyncSession, conversation: Conversation):
        self.websocket = websocket
        self.db = db
        self.conversation = conversation
        self.interrupt_event = asyncio.Event()
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._adapter = VoiceAdapter()

    async def run(self) -> None:
        reader_task = asyncio.create_task(self._reader_loop())
        try:
            while True:
                message = await self._inbox.get()
                if message is None:
                    break
                await self._handle_utterance(message)
        finally:
            reader_task.cancel()

    async def _reader_loop(self) -> None:
        try:
            while True:
                msg = await self.websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    await self._inbox.put(None)
                    return
                audio = msg.get("bytes")
                if audio is not None:
                    await self._inbox.put(audio)
                    continue
                raw_text = msg.get("text")
                if raw_text is None:
                    continue
                try:
                    payload = json.loads(raw_text)
                except ValueError:
                    continue
                if payload.get("type") == "interrupt":
                    self.interrupt_event.set()
                elif payload.get("type") == "end":
                    await self._inbox.put(None)
                    return
        except WebSocketDisconnect:
            await self._inbox.put(None)

    async def _handle_utterance(self, audio_bytes: bytes) -> None:
        self.interrupt_event.clear()

        turn = await self._adapter.receive(audio_bytes, self.conversation.conversation_id)
        # Item 8: the only reference to the raw audio was this local parameter; dropping it
        # here (nothing else holds it, it was never written to disk or the DB) is the actual
        # deletion -- only the transcript below gets persisted, via handle_turn's message log.
        del audio_bytes
        text = turn.text
        if not text:
            return

        await self.websocket.send_json({"type": "transcript", "text": text})

        turn_result = await handle_turn(self.db, self.conversation, text, get_router(), channel="voice")
        await self.websocket.send_json(
            {"type": "reply_text", "text": turn_result.text, "escalated": not turn_result.contained}
        )

        spoken_text = spokenize(turn_result.text)
        for sentence in tts.split_sentences(spoken_text):
            if self.interrupt_event.is_set():
                await self.websocket.send_json({"type": "interrupted"})
                return
            audio = await asyncio.to_thread(tts.synthesize_sentence, sentence)
            if self.interrupt_event.is_set():
                await self.websocket.send_json({"type": "interrupted"})
                return
            await self.websocket.send_json({"type": "audio_start", "text": sentence, "has_audio": audio is not None})
            if audio is not None:
                await self.websocket.send_bytes(audio)

        await self.websocket.send_json({"type": "turn_complete"})
