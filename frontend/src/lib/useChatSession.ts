import { useCallback, useRef, useState } from "react";
import { createChatSession, sendChatFeedback, sendChatMessage } from "./api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  escalated?: boolean;
  feedback?: boolean | null;
}

const WELCOME_TEXT =
  "Hi, I'm Meridian Assist. I can check recalls, book service, or answer questions -- what can I help with today?";

export function useChatSession() {
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: "welcome", role: "assistant", text: WELCOME_TEXT }]);
  const [sending, setSending] = useState(false);
  const [escalated, setEscalated] = useState(false);
  const sessionRef = useRef<{ token: string; conversationId: string } | null>(null);
  const [ready, setReady] = useState(false);

  const ensureSession = useCallback(async () => {
    if (sessionRef.current) return sessionRef.current;
    const session = await createChatSession();
    sessionRef.current = { token: session.session_token, conversationId: session.conversation_id };
    setReady(true);
    return sessionRef.current;
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;
      const userMessage: ChatMessage = { id: `local-${Date.now()}`, role: "user", text: trimmed };
      setMessages((prev) => [...prev, userMessage]);
      setSending(true);
      try {
        const session = await ensureSession();
        const result = await sendChatMessage(session.token, session.conversationId, trimmed);
        setMessages((prev) => [
          ...prev,
          { id: result.message_id ?? `reply-${Date.now()}`, role: "assistant", text: result.text, escalated: result.escalated },
        ]);
        if (result.escalated) setEscalated(true);
      } catch {
        setMessages((prev) => [
          ...prev,
          { id: `error-${Date.now()}`, role: "assistant", text: "Sorry, something went wrong reaching the assistant. Please try again." },
        ]);
      } finally {
        setSending(false);
      }
    },
    [ensureSession, sending],
  );

  const rate = useCallback(async (messageId: string, helpful: boolean) => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: helpful } : m)));
    const session = sessionRef.current;
    if (!session || messageId.startsWith("local-") || messageId.startsWith("reply-") || messageId === "welcome") return;
    try {
      await sendChatFeedback(session.token, session.conversationId, messageId, helpful);
    } catch {
      // best-effort -- the UI already reflects the click either way
    }
  }, []);

  return { messages, send, sending, escalated, rate, ready };
}
