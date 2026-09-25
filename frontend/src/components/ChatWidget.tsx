import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import VoiceModal from "./VoiceModal";
import { useChatSession, type ChatMessage } from "../lib/useChatSession";

const QUICK_REPLIES = ["Check recalls", "Book service", "Service pricing", "Talk to a person"];
const SLOT_LIST_RE = /^\s*[123]\.\s+.+$/m;
const CONFIRMATION_RE = /\bMRD-[A-Z0-9]{6}\b/;

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  const [draft, setDraft] = useState("");
  const { messages, send, sending, escalated, rate } = useChatSession();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const toggleOpen = () => {
    setOpen((v) => !v);
    setEverOpened(true);
  };

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const handleSend = (text: string) => {
    setDraft("");
    void send(text);
  };

  const downloadTranscript = () => {
    const lines = messages.map((m) => `${m.role === "user" ? "You" : "Meridian Assist"}: ${m.text}`);
    const blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "meridian-assist-transcript.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-3">
        {open && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Chat with Meridian Assist"
            className="flex h-[640px] max-h-[calc(100vh-2rem)] w-[400px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-[var(--radius-card)] border border-slate-200 bg-white shadow-2xl sm:h-[640px]"
          >
            <header className="flex items-center justify-between gap-2 bg-navy px-4 py-3 text-white">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-bold">MA</div>
                <div>
                  <div className="text-sm font-semibold">Meridian Assist</div>
                  <div className="flex items-center gap-1 text-xs text-green-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-400" aria-hidden="true" />
                    Online now
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  className="rounded p-2 text-slate-200 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                  aria-label="Talk to Meridian Assist by voice"
                  onClick={() => setVoiceOpen(true)}
                >
                  <MicIcon />
                </button>
                <button
                  className="rounded p-2 text-slate-200 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                  aria-label="Close chat"
                  onClick={() => setOpen(false)}
                >
                  <CloseIcon />
                </button>
              </div>
            </header>

            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-slate-50 px-4 py-4">
              {messages.map((m, i) => (
                <MessageBubble key={m.id} message={m} isLast={i === messages.length - 1} onRate={rate} onQuickPick={handleSend} />
              ))}
              {sending && (
                <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-white px-3.5 py-2.5 w-fit shadow-sm" aria-live="polite" aria-label="Assistant is typing">
                  {[0, 1, 2].map((d) => (
                    <span
                      key={d}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
                      style={{ animationDelay: `${d * 120}ms` }}
                    />
                  ))}
                </div>
              )}
            </div>

            {messages.length <= 1 && (
              <div className="flex flex-wrap gap-2 border-t border-slate-200 bg-white px-4 py-3">
                {QUICK_REPLIES.map((chip) => (
                  <button
                    key={chip}
                    onClick={() => handleSend(chip)}
                    className="rounded-full border border-accent px-3 py-1.5 text-xs font-semibold text-accent hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            )}

            {escalated && (
              <div className="border-t border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
                You've been connected with a service advisor. They'll follow up shortly.
              </div>
            )}

            <form
              className="flex items-center gap-2 border-t border-slate-200 bg-white p-3"
              onSubmit={(e) => {
                e.preventDefault();
                handleSend(draft);
              }}
            >
              <label htmlFor="chat-input" className="sr-only">
                Type a message
              </label>
              <input
                id="chat-input"
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type your message..."
                className="flex-1 rounded-full border border-slate-300 px-4 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                maxLength={1000}
              />
              <button
                type="submit"
                disabled={!draft.trim() || sending}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                aria-label="Send message"
              >
                <SendIcon />
              </button>
            </form>
            <button
              onClick={downloadTranscript}
              className="border-t border-slate-100 py-2 text-center text-xs font-medium text-slate-500 hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              End chat &amp; download transcript
            </button>
          </div>
        )}

        <button
          className="relative flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg shadow-accent/40 transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-accent"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close chat" : "Open chat with Meridian Assist"}
          aria-expanded={open}
        >
          {open ? <CloseIcon /> : <ChatIcon />}
          {!open && !everOpened && (
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-danger text-[10px] font-bold text-white" aria-hidden="true">
              1
            </span>
          )}
        </button>
      </div>
      {voiceOpen && <VoiceModal onClose={() => setVoiceOpen(false)} />}
    </>
  );
}

function MessageBubble({
  message,
  isLast,
  onRate,
  onQuickPick,
}: {
  message: ChatMessage;
  isLast: boolean;
  onRate: (id: string, helpful: boolean) => void;
  onQuickPick: (text: string) => void;
}) {
  const isUser = message.role === "user";
  const hasSlotList = !isUser && SLOT_LIST_RE.test(message.text);
  const confirmationMatch = !isUser ? message.text.match(CONFIRMATION_RE) : null;

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
          isUser
            ? "rounded-br-sm bg-accent text-white"
            : message.escalated
              ? "rounded-bl-sm border border-amber-300 bg-amber-50 text-amber-900"
              : confirmationMatch
                ? "rounded-bl-sm border border-green-300 bg-green-50 text-green-900"
                : "rounded-bl-sm bg-white text-slate-800"
        }`}
      >
        {isUser ? (
          message.text
        ) : (
          <div className="prose-chat">
            <ReactMarkdown>{message.text}</ReactMarkdown>
          </div>
        )}
      </div>

      {hasSlotList && isLast && (
        <div className="mt-2 flex gap-2">
          {["1", "2", "3"].map((n) => (
            <button
              key={n}
              onClick={() => onQuickPick(n)}
              className="rounded-full border border-accent px-3 py-1 text-xs font-semibold text-accent hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Option {n}
            </button>
          ))}
        </div>
      )}

      {!isUser && message.id !== "welcome" && (
        <div className="mt-1 flex items-center gap-1.5">
          <button
            aria-label="Helpful"
            aria-pressed={message.feedback === true}
            onClick={() => onRate(message.id, true)}
            className={`rounded p-1 text-xs ${message.feedback === true ? "text-green-600" : "text-slate-300 hover:text-slate-500"}`}
          >
            &#128077;
          </button>
          <button
            aria-label="Not helpful"
            aria-pressed={message.feedback === false}
            onClick={() => onRate(message.id, false)}
            className={`rounded p-1 text-xs ${message.feedback === false ? "text-red-600" : "text-slate-300 hover:text-slate-500"}`}
          >
            &#128078;
          </button>
        </div>
      )}
    </div>
  );
}

function ChatIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 4h16v12H8l-4 4V4z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 12l16-8-6 8 6 8-16-8z" fill="currentColor" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="M19 11a7 7 0 0 1-14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
