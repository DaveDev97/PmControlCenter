import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, Loading, ErrorBox, DataAsOfBadge } from "../components/ui";
import { fmtMonth, fmtPct } from "../lib/format";
import { settingsApi } from "../lib/settings";
import TeamDashboard from "./TeamDashboard";
import Resources from "./Resources";

type AllocStatus = "ok" | "bench" | "over" | "nd" | "np";

interface MonthAlloc {
  month: string;
  status: AllocStatus;
  hours: number | null;
  month_hours: number | null;
  share: number | null;
  other_pct: number | null;
  absence_hours: number | null;
}

interface AllocationData {
  available: boolean;
  month: string | null;
  months: string[];
  counts: { ok: number; bench: number; over: number; nd: number; np: number; partial: number };
  people: { name: string; resource_id: number | null; lc: number | null; perc_charg: number | null;
            current: MonthAlloc; months: MonthAlloc[] }[];
}

const STATUS: Record<AllocStatus, { label: string; cls: string; cell: string; dot: string }> = {
  ok: { label: "OK", cls: "border-emerald-200 bg-emerald-50 text-emerald-700", cell: "bg-emerald-100 text-emerald-800", dot: "🟢" },
  bench: { label: "Bench", cls: "border-red-200 bg-red-50 text-red-700", cell: "bg-red-100 text-red-700", dot: "🔴" },
  over: { label: "Sovrallocata", cls: "border-red-300 bg-red-100 text-red-800", cell: "bg-red-300 text-red-900", dot: "🔴" },
  nd: { label: "%Charg n/d", cls: "border-slate-200 bg-slate-50 text-slate-500", cell: "bg-slate-100 text-slate-400", dot: "⚪" },
  np: { label: "Non pianificato", cls: "border-slate-200 bg-white text-slate-400", cell: "bg-slate-50 text-slate-300", dot: "⚪" },
};

function StatusPill({ a }: { a: MonthAlloc }) {
  const s = STATUS[a.status];
  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.dot} {s.label}
    </span>
  );
}

function Kpi({ label, value, tone = "text-slate-800 dark:text-slate-100", sub }: {
  label: string; value: number | string; tone?: string; sub?: string;
}) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${tone}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </Card>
  );
}

function AllocationTab() {
  const navigate = useNavigate();
  const [month, setMonth] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["team-allocation", month],
    queryFn: () => api.get<AllocationData>(`/api/team/allocation${month ? `?month=${month}` : ""}`),
  });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data || !data.available) return <ErrorBox error="Foglio Costi vs Forecast non disponibile" />;
  const c = data.counts;
  const cur = data.month || "";
  const fyMonths = data.months.filter((m) => {
    const fy = (y: number, mo: number) => (mo >= 9 ? y + 1 : y);
    return fy(+m.slice(0, 4), +m.slice(5, 7)) === fy(+cur.slice(0, 4), +cur.slice(5, 7));
  });

  return (
    <>
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm text-slate-600 dark:text-slate-300">Mese</span>
        <select value={cur} onChange={(e) => setMonth(e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white">
          {data.months.map((m) => <option key={m} value={m}>{fmtMonth(m)}</option>)}
        </select>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-4 md:grid-cols-5">
        <Kpi label="Allocate correttamente" value={c.ok} tone="text-emerald-600" />
        <Kpi label="di cui con quota Other" value={c.partial} sub="parte del tempo su altri progetti" />
        <Kpi label="Bench" value={c.bench} tone={c.bench ? "text-red-600" : "text-slate-800 dark:text-slate-100"}
             sub="%Charg presente ma 0 ore nel mese" />
        <Kpi label="Sovrallocate" value={c.over} tone={c.over ? "text-red-600" : "text-slate-800 dark:text-slate-100"}
             sub="ore oltre quelle lavorabili" />
        <Kpi label="%Charg n/d" value={c.nd} sub="colonna %Charg vuota" />
      </div>

      <Card title={`Allocazione · ${fmtMonth(cur)}`} className="mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700 [&>th]:px-3">
              <th className="py-2">Risorsa</th>
              <th className="text-right">%Charg (target)</th>
              <th className="text-right">Ore nel mese</th>
              <th className="text-right">Ore al 100% %Charg</th>
              <th>Quota sull'account</th>
              <th className="text-right">Assenze</th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>
            {data.people.map((p) => {
              const a = p.current;
              const full = p.perc_charg != null && a.month_hours ? a.month_hours * p.perc_charg : null;
              return (
                <tr key={p.name}
                    onClick={() => p.resource_id && navigate(`/person/${p.resource_id}`)}
                    className={`border-b border-slate-50 dark:border-slate-800 [&>td]:px-3 ${p.resource_id ? "cursor-pointer hover:bg-brand-50 dark:hover:bg-slate-700" : ""}`}>
                  <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{p.name}</td>
                  <td className="text-right">{p.perc_charg == null ? "-" : fmtPct(p.perc_charg)}</td>
                  <td className="text-right">{a.hours == null ? "-" : `${a.hours.toLocaleString("it-IT")}h`}</td>
                  <td className="text-right text-slate-500">{full == null ? "-" : `${full.toLocaleString("it-IT", { maximumFractionDigits: 1 })}h`}</td>
                  <td>
                    {a.share == null ? "-" : (
                      <span className="flex items-center gap-2">
                        {fmtPct(a.share)}
                        {a.other_pct != null && (
                          <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700"
                                title="Parte del tempo è staffata su altri progetti">
                            {fmtPct(a.other_pct)} Other
                          </span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className="text-right text-slate-500">{a.absence_hours ? `−${a.absence_hours.toLocaleString("it-IT")}h` : "-"}</td>
                  <td><StatusPill a={a} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Ogni risorsa è confrontata con la propria %Charg (foglio Costi vs Forecast). Una quota inferiore al 100%
          indica tempo staffato su altri progetti ("Other") e non è un'anomalia; le ore di assenza sono mostrate a parte.
        </p>
      </Card>

      <Card title="Timeline del FY">
        <div className="overflow-x-auto">
          <table className="text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 bg-white p-2 text-left dark:bg-slate-800">Risorsa</th>
                {fyMonths.map((m) => (
                  <th key={m} className={`p-2 text-center font-medium ${m === cur ? "text-brand-600" : "text-slate-500"}`}>{fmtMonth(m)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.people.map((p) => (
                <tr key={p.name}>
                  <td className="sticky left-0 bg-white p-2 font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">{p.name}</td>
                  {fyMonths.map((m) => {
                    const a = p.months.find((x) => x.month === m);
                    if (!a) return <td key={m} />;
                    return (
                      <td key={m} className="p-1">
                        <div className={`flex h-8 w-14 items-center justify-center rounded ${STATUS[a.status].cell}`}
                             title={`${STATUS[a.status].label}${a.hours != null ? ` · ${a.hours}h` : ""}${a.other_pct ? ` · ${Math.round(a.other_pct * 100)}% Other` : ""}`}>
                          {a.status === "ok" ? (a.other_pct ? `${Math.round((a.share || 0) * 100)}%` : "✓") : a.status === "bench" ? "0h" : a.status === "over" ? "!" : a.status === "np" ? "–" : ""}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500 dark:text-slate-400">
          <span>✓ allocata al 100% della propria %Charg</span>
          <span>50% = quota sull'account (resto su Other)</span>
          <span>0h = bench</span>
          <span>! = sovrallocata</span>
          <span>– = mese non ancora pianificato nel foglio</span>
        </div>
      </Card>
    </>
  );
}

const TABS = [
  { id: "allocazione", label: "Allocazione" },
  { id: "costi", label: "Costi e margini" },
  { id: "anagrafica", label: "Anagrafica" },
];

export default function TeamResources() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? params.get("tab")! : "allocazione";
  const { data: status } = useQuery({ queryKey: ["data-status-badge"], queryFn: settingsApi.status });
  return (
    <div className="p-6">
      <header className="mb-4 flex items-center gap-3">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Team & Risorse</h1>
        <DataAsOfBadge lastSync={status?.last_sync} />
      </header>
      <div className="mb-5 flex gap-1 border-b border-slate-200 dark:border-slate-700">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setParams({ tab: t.id })}
                  className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                    tab === t.id
                      ? "border-brand-500 text-brand-700 dark:text-brand-400"
                      : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
                  }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "allocazione" && <AllocationTab />}
      {tab === "costi" && <TeamDashboard embedded />}
      {tab === "anagrafica" && <Resources embedded />}
    </div>
  );
}
