import * as RadixToast from "@radix-ui/react-toast";
import { createContext, useCallback, useContext, useState } from "react";

interface ToastMessage {
  id: number;
  title: string;
  description?: string;
  tone?: "success" | "danger";
}

const ToastContext = createContext<(toast: Omit<ToastMessage, "id">) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const push = useCallback((toast: Omit<ToastMessage, "id">) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      <RadixToast.Provider swipeDirection="right">
        {children}
        {toasts.map((t) => (
          <RadixToast.Root
            key={t.id}
            duration={4000}
            onOpenChange={(open) => {
              if (!open) setToasts((prev) => prev.filter((x) => x.id !== t.id));
            }}
            className={`rounded-[var(--radius-card)] border p-4 shadow-lg ${
              t.tone === "danger" ? "border-red-200 bg-red-50" : "border-green-200 bg-green-50"
            }`}
          >
            <RadixToast.Title className="text-sm font-semibold text-slate-900">{t.title}</RadixToast.Title>
            {t.description && <RadixToast.Description className="mt-1 text-sm text-slate-600">{t.description}</RadixToast.Description>}
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-4 right-4 z-[100] flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}
