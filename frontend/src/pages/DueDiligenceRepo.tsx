import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Trash2, Loader2, Download, FileSpreadsheet, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { Card, Loading, ErrorBox } from "../components/ui";

interface RepoDoc {
  id: string;
  name: string;
  type: string;
  uploaded_at: string;
  items: number;
  with_answer: number;
  sheets: { sheet: string; items: number; method: string | null; question_col?: string; answer_col?: string }[];
}

interface JobItem {
  sheet: string;
  row: number;
  question: string;
  existing: boolean;
  answer: string;
  confidence: number | null;
  method: string | null;
  source: { doc: string; sheet: string; row: number; question: string } | null;
}

interface Job {
  id: string;
  file: string;
  status: string;
  message: string;
  total: number;
  done: number;
  warnings: string[];
  output_name?: string;
  summary?: { questions: number; already_answered: number; filled: number; empty: number; claude: boolean };
  items?: JobItem[];
}

const base = () => (window as unknown as { __API_BASE__?: string }).__API_BASE__ || "";

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${base()}${path}`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail || res.statusText);
  return res.json();
}

function RepositorySection() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [docType, setDocType] = useState("risposte");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["dd-repo"],
    queryFn: () => api.get<{ documents: RepoDoc[]; types: Record<string, string>; claude_available: boolean }>("/api/dd-repo/documents"),
  });

  async function upload(files: FileList) {
    setBusy(true);
    setError(null);
    try {
      for (const f of Array.from(files)) {
        const form = new FormData();
        form.append("file", f);
        form.append("doc_type", docType);
        await postForm("/api/dd-repo/documents", form);
      }
      qc.invalidateQueries({ queryKey: ["dd-repo"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(d: RepoDoc) {
    if (!confirm(`Rimuovere "${d.name}" dal repository?`)) return;
    await api.del(`/api/dd-repo/documents/${d.id}`);
    qc.invalidateQueries({ queryKey: ["dd-repo"] });
  }

  if (isLoading) return <Loading />;
  const docs = data?.documents || [];
  const totalAnswers = docs.reduce((s, d) => s + d.with_answer, 0);

  return (
    <Card title={`Repository · ${docs.length} documenti · ${totalAnswers} risposte standard`} className="mb-6"
          actions={
            <div className="flex items-center gap-2">
              <select value={docType} onChange={(e) => setDocType(e.target.value)}
                      className="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-700 dark:text-white">
                {Object.entries(data?.types || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <button onClick={() => fileRef.current?.click()} disabled={busy}
                      className="flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Carica documenti
              </button>
              <input ref={fileRef} type="file" accept=".xlsx,.xlsm" multiple className="hidden"
                     onChange={(e) => e.target.files?.length && upload(e.target.files)} />
            </div>
          }>
      {error && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {docs.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Carica file Excel con requisiti, domande e risposte standard o due diligence già compilate: diventano la
          base di conoscenza usata per compilare le nuove DD. Restano salvati solo su questo PC.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
              <th className="py-2">Documento</th>
              <th>Tipo</th>
              <th className="text-right">Domande</th>
              <th className="text-right">Con risposta</th>
              <th>Fogli riconosciuti</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} className="border-b border-slate-50 dark:border-slate-800">
                <td className="py-2 font-medium text-slate-700 dark:text-slate-200">
                  <FileSpreadsheet size={14} className="mr-1 inline text-emerald-600" />{d.name}
                </td>
                <td>{data?.types[d.type] || d.type}</td>
                <td className="text-right">{d.items}</td>
                <td className="text-right">{d.with_answer}</td>
                <td className="text-xs text-slate-500">
                  {d.sheets.filter((s) => s.items).map((s) => `${s.sheet} (${s.question_col}→${s.answer_col}, ${s.method})`).join(" · ") || "nessuna domanda riconosciuta"}
                </td>
                <td className="text-right">
                  <button onClick={() => remove(d)} className="text-slate-400 hover:text-red-600" title="Rimuovi">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data && !data.claude_available && (
        <p className="mt-3 text-xs text-amber-600">
          Claude Code non trovato: le colonne e le corrispondenze verranno valutate solo con il confronto testuale.
        </p>
      )}
    </Card>
  );
}

function FillSection() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [useClaude, setUseClaude] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "filled" | "empty">("all");

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      try {
        const j = await api.get<Job>(`/api/dd-repo/jobs/${jobId}`);
        if (stop) return;
        setJob(j);
        if (!["completato", "errore"].includes(j.status)) setTimeout(tick, 1500);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };
    tick();
    return () => { stop = true; };
  }, [jobId]);

  async function start(file: File) {
    setError(null);
    setJob(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("use_claude", String(useClaude));
      const { job_id } = await postForm<{ job_id: string }>("/api/dd-repo/fill", form);
      setJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const running = job && !["completato", "errore"].includes(job.status);
  const items = (job?.items || []).filter((it) =>
    filter === "all" ? true : filter === "filled" ? !!it.answer : !it.answer && !it.existing);

  return (
    <Card title="Compila una nuova Due Diligence"
          actions={
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">
                <input type="checkbox" checked={useClaude} onChange={(e) => setUseClaude(e.target.checked)} />
                <Sparkles size={12} /> Usa Claude per valutare le corrispondenze
              </label>
              <button onClick={() => fileRef.current?.click()} disabled={!!running}
                      className="flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50">
                <Upload size={14} /> Carica questionario
              </button>
              <input ref={fileRef} type="file" accept=".xlsx,.xlsm" className="hidden"
                     onChange={(e) => e.target.files?.[0] && start(e.target.files[0])} />
            </div>
          }>
      {error && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {!job && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Carica il file Excel della DD da compilare. Le domande con una corrispondenza affidabile nel repository
          vengono compilate ed evidenziate in giallo, con fonte e affidabilità in due colonne aggiuntive; le altre
          restano vuote. Il file originale non viene modificato: scarichi una copia pronta per la revisione.
        </p>
      )}
      {job && (
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium text-slate-700 dark:text-slate-200">{job.file}</span>
            {running && <Loader2 size={14} className="animate-spin text-brand-500" />}
            <span className={job.status === "errore" ? "text-red-600" : "text-slate-500 dark:text-slate-400"}>
              {job.status}{job.message ? ` · ${job.message}` : ""}
              {job.status === "matching" && job.total ? ` (${job.done}/${job.total})` : ""}
            </span>
            {job.status === "completato" && (
              <a href={`${base()}/api/dd-repo/jobs/${job.id}/download`}
                 className="ml-auto flex items-center gap-1 rounded-lg border border-brand-400 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50 dark:text-brand-400">
                <Download size={14} /> Scarica documento compilato
              </a>
            )}
          </div>
          {job.warnings.map((w, i) => <div key={i} className="mb-2 text-xs text-amber-600">{w}</div>)}
          {job.summary && (
            <>
              <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  ["Domande", job.summary.questions, ""],
                  ["Compilate", job.summary.filled, "text-emerald-600"],
                  ["Da compilare a mano", job.summary.empty, "text-amber-600"],
                  ["Già risposte nel file", job.summary.already_answered, ""],
                ].map(([l, v, tone]) => (
                  <div key={l as string} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                    <div className="text-xs uppercase text-slate-500">{l}</div>
                    <div className={`text-xl font-bold ${tone || "text-slate-800 dark:text-slate-100"}`}>{v}</div>
                  </div>
                ))}
              </div>
              <div className="mb-2 flex gap-2 text-xs">
                {(["all", "filled", "empty"] as const).map((f) => (
                  <button key={f} onClick={() => setFilter(f)}
                          className={`rounded border px-2 py-1 ${filter === f ? "border-brand-500 bg-brand-500 text-white" : "border-slate-300 text-slate-600 dark:border-slate-600 dark:text-slate-300"}`}>
                    {f === "all" ? "Tutte" : f === "filled" ? "Compilate" : "Vuote"}
                  </button>
                ))}
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
                    <th className="py-2">Riga</th>
                    <th className="w-1/3">Domanda</th>
                    <th className="w-1/3">Risposta proposta</th>
                    <th>Fonte</th>
                    <th className="text-right">Affidabilità</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => (
                    <tr key={`${it.sheet}-${it.row}`} className="border-b border-slate-50 align-top dark:border-slate-800">
                      <td className="py-2 text-xs text-slate-500">{it.sheet} · {it.row}</td>
                      <td className="pr-3 text-slate-700 dark:text-slate-200">{it.question}</td>
                      <td className={`pr-3 ${it.answer ? "bg-amber-50 text-slate-800 dark:bg-amber-900/20 dark:text-slate-100" : "text-slate-400"}`}>
                        {it.existing ? <span className="italic">già presente nel file</span> : it.answer || "— nessuna corrispondenza affidabile"}
                      </td>
                      <td className="text-xs text-slate-500" title={it.source?.question}>
                        {it.source ? `${it.source.doc} · ${it.source.sheet} r.${it.source.row} (${it.method})` : "-"}
                      </td>
                      <td className="text-right text-xs">{it.confidence == null ? "-" : `${Math.round(it.confidence * 100)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </Card>
  );
}

export default function DueDiligenceRepo() {
  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Due Diligence</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Repository di risposte standard e compilazione automatica dei nuovi questionari, da rivedere prima dell'invio.
        </p>
      </header>
      <RepositorySection />
      <FillSection />
    </div>
  );
}
