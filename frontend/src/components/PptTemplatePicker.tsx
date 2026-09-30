import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Trash2, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "../lib/api";

export interface PptTemplate {
  id: string;
  kind: "builtin" | "uploaded";
  name: string;
  description: string;
  palette: Record<string, string>;
  fonts: { heading?: string; body?: string };
  analysis?: {
    slide_width_in: number;
    slide_height_in: number;
    layouts: { index: number; name: string; placeholders: string[] }[];
    slides: { n: number; layout: string; title: string; content: Record<string, number> }[];
    content_totals: Record<string, number>;
  };
}

const SWATCH_KEYS = ["primary", "dark", "background", "accent1", "accent2", "accent3", "accent4", "dk2", "lt1"];

function Swatches({ palette }: { palette: Record<string, string> }) {
  const colors = SWATCH_KEYS.map((k) => palette[k]).filter(Boolean).slice(0, 6);
  return (
    <div className="flex gap-1">
      {colors.map((c, i) => (
        <span key={i} className="h-4 w-4 rounded border border-slate-200" style={{ background: `#${c}` }} title={`#${c}`} />
      ))}
    </div>
  );
}

/** Template choice for the "Crea PPT" dialog: built-in styles + uploaded example decks. */
export default function PptTemplatePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openAnalysis, setOpenAnalysis] = useState<string | null>(null);
  const { data: templates, isLoading } = useQuery({
    queryKey: ["ppt-templates"],
    queryFn: () => api.get<PptTemplate[]>("/api/reports/templates"),
  });

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const base = (window as unknown as { __API_BASE__?: string }).__API_BASE__ || "";
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`${base}/api/reports/templates`, { method: "POST", body });
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail || res.statusText);
      const meta = await res.json();
      await qc.invalidateQueries({ queryKey: ["ppt-templates"] });
      onChange(meta.id);
      setOpenAnalysis(meta.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(t: PptTemplate) {
    if (!confirm(`Eliminare il template "${t.name}"?`)) return;
    await api.del(`/api/reports/templates/${t.id}`);
    if (value === t.id) onChange("builtin:accenture");
    qc.invalidateQueries({ queryKey: ["ppt-templates"] });
  }

  if (isLoading) return <div className="text-sm text-slate-500">Caricamento template…</div>;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Stile di partenza</span>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1 rounded-lg border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
          Carica PPT di esempio
        </button>
        <input ref={fileRef} type="file" accept=".pptx" className="hidden"
               onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      </div>
      {error && <div className="mb-2 rounded bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>}
      <div className="grid max-h-72 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
        {(templates || []).map((t) => (
          <div
            key={t.id}
            onClick={() => onChange(t.id)}
            className={`cursor-pointer rounded-lg border p-3 text-left transition ${
              value === t.id
                ? "border-brand-500 ring-2 ring-brand-300 dark:ring-brand-700"
                : "border-slate-200 hover:border-brand-300 dark:border-slate-600"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">{t.name}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  {t.kind === "builtin" ? "Preconfigurato" : "Caricato"} · {t.description}
                </div>
              </div>
              {t.kind === "uploaded" && (
                <button onClick={(e) => { e.stopPropagation(); remove(t); }}
                        className="text-slate-400 hover:text-red-600" title="Elimina template">
                  <Trash2 size={14} />
                </button>
              )}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <Swatches palette={t.palette} />
              <span className="text-[11px] text-slate-400">
                {t.fonts.heading}{t.fonts.body && t.fonts.body !== t.fonts.heading ? ` / ${t.fonts.body}` : ""}
              </span>
            </div>
            {t.analysis && (
              <button
                onClick={(e) => { e.stopPropagation(); setOpenAnalysis(openAnalysis === t.id ? null : t.id); }}
                className="mt-2 flex items-center gap-1 text-[11px] font-medium text-brand-700 dark:text-brand-400"
              >
                {openAnalysis === t.id ? <ChevronDown size={12} /> : <ChevronRight size={12} />} Analisi del template
              </button>
            )}
            {t.analysis && openAnalysis === t.id && (
              <div className="mt-1 space-y-1 text-[11px] text-slate-600 dark:text-slate-300">
                <div>
                  Formato {t.analysis.slide_width_in}×{t.analysis.slide_height_in} in · contenuti:{" "}
                  {Object.entries(t.analysis.content_totals).map(([k, v]) => `${v} ${k}`).join(", ") || "-"}
                </div>
                <div>Layout: {t.analysis.layouts.map((l) => l.name).join(", ")}</div>
                <div>
                  Slide:{" "}
                  {t.analysis.slides.map((s) => `${s.n}. ${s.title || "(senza titolo)"} [${s.layout}]`).join(" · ")}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
