import { useEffect, useRef } from "react";
import { useVoiceSession } from "../voice/useVoiceSession";
import Waveform from "./Waveform";

interface VoiceModalProps {
  onClose: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  idle: "Ready",
  connecting: "Connecting...",
  listening: "Listening...",
  thinking: "Thinking...",
  speaking: "Speaking...",
  error: "Connection error",
  ended: "Call ended",
};

export default function VoiceModal({ onClose }: VoiceModalProps) {
  const { status, captions, micLevel, escalated, start, end } = useVoiceSession();
  const startedRef = useRef(false);
  const captionsEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!startedRef.current) {
      startedRef.current = true;
      start().catch(() => {
        /* status is already reflected as "error" by the hook */
      });
    }
  }, [start]);

  useEffect(() => {
    captionsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [captions]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleEndCall();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEndCall = () => {
    end();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-navy/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Talk to Meridian Assist"
    >
      <div className="flex max-h-[640px] w-[420px] max-w-full flex-col gap-4 rounded-[var(--radius-card)] bg-navy p-6 text-white shadow-2xl">
        <header className="flex items-center justify-between">
          <span className="font-display text-lg font-bold">Talk to Meridian Assist</span>
          <button
            className="rounded p-1 text-2xl leading-none text-slate-300 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            onClick={handleEndCall}
            aria-label="Close"
          >
            &times;
          </button>
        </header>

        <div className="text-center text-sm tracking-wide text-blue-300">{STATUS_LABEL[status] ?? status}</div>

        <Waveform level={micLevel} active={status === "listening"} />

        {escalated && (
          <div className="rounded-lg border border-amber-500 bg-amber-500/10 px-3 py-2 text-center text-sm text-amber-300">
            You're being connected with a service advisor.
          </div>
        )}

        <div className="flex min-h-40 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {captions.length === 0 && <p className="mt-8 text-center text-slate-500">Say something to get started.</p>}
          {captions.map((line, i) => (
            <p key={i} className="text-sm leading-relaxed">
              <span className={`font-semibold ${line.role === "user" ? "text-green-300" : "text-blue-300"}`}>
                {line.role === "user" ? "You" : "Assistant"}:
              </span>{" "}
              {line.text}
            </p>
          ))}
          <div ref={captionsEndRef} />
        </div>

        <button
          className="rounded-[var(--radius-input)] bg-danger py-3 font-semibold text-white hover:bg-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          onClick={handleEndCall}
        >
          End Call
        </button>
      </div>
    </div>
  );
}
