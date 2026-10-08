import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Send, Loader2, RotateCcw, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { chatApi } from "../lib/settings";

// ---------------------------------------------------------------------------
// Markdown renderer (tables + bullets — no external dependency)
// ---------------------------------------------------------------------------

function renderMarkdown(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // Blank line
    if (!line.trim()) {
      out.push("<br/>");
      i++;
      continue;
    }

    // Table: starts when line looks like "| col | col |"
    if (line.trimStart().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      // Skip separator rows (e.g. |---|---|)
      const isHeader = (l: string) => /^\|[\s\-:|]+\|/.test(l.replace(/[^|:\-\s]/g, ""));
      const header = tableLines[0];
      const body = tableLines.slice(2); // skip separator
      const cells = (l: string) =>
        l.split("|").slice(1, -1).map((c) => c.trim());
      let html = '<table class="md-table">';
      html += "<thead><tr>" + cells(header).map((c) => `<th>${inlineMarkdown(c)}</th>`).join("") + "</tr></thead>";
      html += "<tbody>" + body.map((l) =>
        "<tr>" + cells(l).map((c) => `<td>${inlineMarkdown(c)}</td>`).join("") + "</tr>"
      ).join("") + "</tbody></table>";
      out.push(html);
      continue;
    }

    // Heading
    const hm = line.match(/^(#{1,3})\s+(.+)/);
    if (hm) {
      const tag = `h${hm[1].length + 2}`; // h3-h5 to stay within card hierarchy
      out.push(`<${tag} class="md-h${hm[1].length}">${inlineMarkdown(hm[2])}</${tag}>`);
      i++;
      continue;
    }

    // Bullet (• or - or *)
    if (/^[•\-\*]\s/.test(line.trim())) {
      const items: string[] = [];
      while (i < lines.length && /^[•\-\*]\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[•\-\*]\s/, ""));
        i++;
      }
      out.push("<ul>" + items.map((it) => `<li>${inlineMarkdown(it)}</li>`).join("") + "</ul>");
      continue;
    }

    // Normal paragraph
    out.push(`<p>${inlineMarkdown(line)}</p>`);
    i++;
  }
  return out.join("\n");
}

function inlineMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

function AssistantBubble({ content }: { content: string }) {
  const html = renderMarkdown(content);
  return (
    <div
      className="prose-chat max-w-none text-sm leading-relaxed text-slate-800 dark:text-slate-100"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBriefingLoading, setIsBriefingLoading] = useState(false);
  const { data: status } = useQuery({
    queryKey: ["chat-status"],
    queryFn: chatApi.status,
    staleTime: 60_000,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialised = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  // Load history on mount; if empty, fetch briefing
  const loadHistoryOrBriefing = useCallback(async () => {
    setIsBriefingLoading(true);
    try {
      const { turns } = await chatApi.history();
      if (turns.length > 0) {
        setMessages(
          turns.map((t, idx) => ({
            id: String(idx),
            role: t.role as "user" | "assistant",
            content: t.content,
            timestamp: new Date(t.timestamp),
          }))
        );
      } else {
        const { briefing } = await chatApi.briefing();
        setMessages([
          {
            id: "briefing",
            role: "assistant",
            content: briefing,
            timestamp: new Date(),
          },
        ]);
      }
    } catch {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content:
            "Ciao! Sono l'assistente finanziario del Control Center.\n\n" +
            "• Analisi CCI e spazio costi per WBS e mese\n" +
            "• Forecast ore risorse con verifica spazio costi\n" +
            "• Piano di recovery CCI verso il target 35%\n" +
            "• Scenari A/B/C (allocato / +booking / +OdA)\n\n" +
            "Cosa vuoi analizzare?",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsBriefingLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!initialised.current) {
      initialised.current = true;
      loadHistoryOrBriefing();
    }
  }, [loadHistoryOrBriefing]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };
    const question = input;
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      // History is now managed server-side; send empty client history
      const { reply } = await chatApi.send(question, []);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: reply,
          timestamp: new Date(),
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content:
            "⚠️ Errore nel contattare Claude Code: " +
            (e instanceof Error ? e.message : String(e)),
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    try {
      await chatApi.clearHistory();
    } catch {
      /* ignore */
    }
    setMessages([]);
    initialised.current = false;
    loadHistoryOrBriefing();
  };

  const handleRefreshBriefing = async () => {
    setIsBriefingLoading(true);
    try {
      await chatApi.clearHistory();
      const { briefing } = await chatApi.briefing();
      setMessages([
        {
          id: "briefing-" + Date.now(),
          role: "assistant",
          content: briefing,
          timestamp: new Date(),
        },
      ]);
    } catch {
      /* ignore */
    } finally {
      setIsBriefingLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
              Analista Finanziario AI
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              CCI · spazio costi · forecast ore · recovery plan — dati in tempo reale dall'Excel
            </p>
            {status && (
              <p
                className={`mt-1 flex items-center gap-1 text-xs ${
                  status.available ? "text-emerald-600" : "text-red-600"
                }`}
                title={status.path || undefined}
              >
                {status.available ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                {status.available
                  ? `Claude Code collegato · modello ${status.model}`
                  : "Claude Code non trovato — installalo o indica il percorso nelle Impostazioni"}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleRefreshBriefing}
              disabled={isBriefingLoading}
              title="Ricarica briefing finanziario aggiornato"
              className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
            >
              <RefreshCw size={16} className={isBriefingLoading ? "animate-spin" : ""} />
              Aggiorna dati
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
            >
              <RotateCcw size={16} />
              Reset Chat
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {isBriefingLoading && messages.length === 0 && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-2xl bg-white px-4 py-3 shadow-sm dark:bg-slate-800">
                <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                  <Loader2 className="animate-spin" size={16} />
                  <span className="text-sm">Caricamento dati finanziari...</span>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-brand-500 text-white"
                    : "bg-white shadow-sm dark:bg-slate-800"
                }`}
              >
                {msg.role === "user" ? (
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                  </div>
                ) : (
                  <AssistantBubble content={msg.content} />
                )}
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
                  <span className="text-sm">Claude sta analizzando i dati finanziari...</span>
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
              onKeyDown={handleKeyDown}
              placeholder="Es: Quanto spazio costi ho ancora in ottobre per WBS Findo? Oppure: prepara un forecast ore per Cesarano e Ruggiero in novembre..."
              rows={2}
              className="flex-1 resize-none rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:placeholder-slate-500"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="flex h-14 w-12 items-center justify-center rounded-lg bg-brand-500 text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={20} />
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            💡 Prova: "Il CCI di ottobre è sotto target — cosa posso fare?" · "Chi può assumere più ore senza sforare il budget?" · "Cosa succede al CCI se chiudo il booking Microseg?"
          </p>
        </div>
      </div>
    </div>
  );
}
