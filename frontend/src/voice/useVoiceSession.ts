import { useCallback, useEffect, useRef, useState } from "react";
import { createVoiceSession, WS_BASE } from "../lib/api";
import { float32ToPcm16 } from "./pcm";

export type CallStatus = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error" | "ended";

export interface CaptionLine {
  role: "user" | "assistant";
  text: string;
}

interface ServerMessage {
  type: "transcript" | "reply_text" | "audio_start" | "interrupted" | "turn_complete";
  text?: string;
  escalated?: boolean;
  has_audio?: boolean;
}

export function useVoiceSession() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [captions, setCaptions] = useState<CaptionLine[]>([]);
  const [micLevel, setMicLevel] = useState(0);
  const [escalated, setEscalated] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const vadRef = useRef<import("@ricky0123/vad-web").MicVAD | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playbackSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const pendingAudioTextRef = useRef<string | null>(null);

  const stopPlayback = useCallback(() => {
    if (playbackSourceRef.current) {
      try {
        playbackSourceRef.current.stop();
      } catch {
        // already stopped
      }
      playbackSourceRef.current = null;
    }
  }, []);

  const playAudioChunk = useCallback(async (bytes: ArrayBuffer) => {
    const ctx = audioCtxRef.current;
    if (!ctx) return;
    const buffer = await ctx.decodeAudioData(bytes.slice(0));
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    playbackSourceRef.current = source;
    setStatus("speaking");
    await new Promise<void>((resolve) => {
      source.onended = () => resolve();
      source.start();
    });
    if (playbackSourceRef.current === source) {
      playbackSourceRef.current = null;
    }
  }, []);

  const levelLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    setMicLevel(Math.sqrt(sum / data.length));
    rafRef.current = requestAnimationFrame(levelLoop);
  }, []);

  const end = useCallback(() => {
    stopPlayback();
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: "end" }));
      } catch {
        // socket may already be closed
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    if (vadRef.current) {
      vadRef.current.destroy();
      vadRef.current = null;
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    setStatus("ended");
  }, [stopPlayback]);

  const start = useCallback(async () => {
    setStatus("connecting");
    setCaptions([]);
    setEscalated(false);

    const { session_token } = await createVoiceSession();
    const ws = new WebSocket(`${WS_BASE}/api/v1/voice/session?token=${encodeURIComponent(session_token)}`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
        const msg: ServerMessage = JSON.parse(event.data);
        if (msg.type === "transcript" && msg.text) {
          setCaptions((prev) => [...prev, { role: "user", text: msg.text! }]);
        } else if (msg.type === "reply_text" && msg.text) {
          setStatus("thinking");
          setCaptions((prev) => [...prev, { role: "assistant", text: msg.text! }]);
          if (msg.escalated) setEscalated(true);
        } else if (msg.type === "audio_start") {
          pendingAudioTextRef.current = msg.text ?? null;
          if (!msg.has_audio && "speechSynthesis" in window && msg.text) {
            // Server TTS unavailable for this sentence -- browser speechSynthesis last resort.
            const utterance = new SpeechSynthesisUtterance(msg.text);
            setStatus("speaking");
            window.speechSynthesis.speak(utterance);
          }
        } else if (msg.type === "interrupted") {
          stopPlayback();
          setStatus("listening");
        } else if (msg.type === "turn_complete") {
          setStatus("listening");
        }
      } else {
        await playAudioChunk(event.data as ArrayBuffer);
      }
    };

    ws.onerror = () => setStatus("error");
    ws.onclose = () => setStatus((s) => (s === "error" ? s : "ended"));

    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.addEventListener("error", () => reject(new Error("voice socket failed to open")), { once: true });
    });

    const audioCtx = new AudioContext();
    audioCtxRef.current = audioCtx;

    const { MicVAD } = await import("@ricky0123/vad-web");
    const vad = await MicVAD.new({
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      onSpeechStart: () => {
        // Barge-in (item 6): the user started talking while the assistant's audio is still
        // playing -- stop local playback immediately and tell the server to abandon the rest
        // of the in-flight reply.
        if (playbackSourceRef.current) {
          stopPlayback();
          ws.send(JSON.stringify({ type: "interrupt" }));
        }
        setStatus("listening");
      },
      onSpeechEnd: (audio: Float32Array) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(float32ToPcm16(audio));
          setStatus("thinking");
        }
      },
      onVADMisfire: () => {
        // Too short to be real speech; nothing was sent, stay in whatever state we were in.
      },
    });
    vadRef.current = vad;
    vad.start();

    const source = audioCtx.createMediaStreamSource(await navigator.mediaDevices.getUserMedia({ audio: true }));
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    analyserRef.current = analyser;
    rafRef.current = requestAnimationFrame(levelLoop);

    setStatus("listening");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [levelLoop, playAudioChunk, stopPlayback]);

  useEffect(() => () => end(), [end]);

  return { status, captions, micLevel, escalated, start, end };
}
