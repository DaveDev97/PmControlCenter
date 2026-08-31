import { useState, useRef, useEffect } from "react";
import { Send, Loader2, RotateCcw } from "lucide-react";
import { chatApi } from "../lib/settings";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Ciao! Sono l'assistente AI del Control Center. Posso aiutarti a:\n\n" +
        "• Trovare risorse disponibili per nuovi progetti\n" +
        "• Analizzare margini e KPI sui contratti\n" +
        "• Identificare risorse sovrallocate\n" +
        "• Calcolare chargeability e utilization\n" +
        "• Fornire insights su opportunità e pipeline\n\n" +
        "Cosa vuoi sapere?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    const question = input;
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const { reply } = await chatApi.send(question);
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: "assistant", content: reply, timestamp: new Date() },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "⚠️ Errore nel contattare Claude Code: " + (e instanceof Error ? e.message : String(e)),
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content:
          "Chat resettata! Cosa vuoi sapere sul Control Center?",
        timestamp: new Date(),
      },
    ]);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
              Claude AI Chat
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Assistente intelligente per il Control Center
            </p>
          </div>
          <button
            onClick={handleReset}
            className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white bg-white px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
          >
            <RotateCcw size={16} />
            Reset Chat
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-brand-500 text-white"
                    : "bg-white text-slate-800 shadow-sm dark:bg-slate-800 dark:text-slate-100"
                }`}
              >
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {msg.content}
                </div>
                <div
                  className={`mt-1 text-xs ${
                    msg.role === "user" ? "text-brand-100" : "text-slate-400"
                  }`}
                >
                  {msg.timestamp.toLocaleTimeString("it-IT", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-2xl bg-white px-4 py-3 shadow-sm dark:bg-slate-800">
                <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                  <Loader2 className="animate-spin" size={16} />
                  <span className="text-sm">Claude sta pensando...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 bg-white px-6 py-4 dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto max-w-3xl">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Scrivi la tua domanda... (Invio per inviare, Shift+Invio per nuova riga)"
              rows={1}
              className="flex-1 resize-none rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white bg-white px-4 py-3 text-sm text-slate-800 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white dark:placeholder-slate-500"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="flex h-12 w-12 items-center justify-center rounded-lg bg-brand-500 text-slate-800 dark:text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={20} />
            </button>
          </div>

          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            💡 Prova: "Chi si libera a breve?" • "Mostrami i contratti con margine basso" •
            "Qual è la chargeability media del team?"
          </p>
        </div>
      </div>
    </div>
  );
}

