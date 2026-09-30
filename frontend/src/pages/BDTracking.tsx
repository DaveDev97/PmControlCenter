import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { BDOverview, BDRow, BDState } from "../lib/types";
import { Card, Loading, ErrorBox, DataAsOfBadge } from "../components/ui";
import { fmtEur, fmtPct } from "../lib/format";
import { settingsApi } from "../lib/settings";
import { useSort, SortTh } from "../lib/useTable";

const STATES: BDState[] = ["Attivo", "Chiuso", "Sconosciuto"];

const stateStyle: Record<BDState, { cls: string; dot: string }> = {
  Attivo: { cls: "text-emerald-700 bg-emerald-50 border-emerald-200", dot: "🟢" },
  Chiuso: { cls: "text-red-700 bg-red-50 border-red-200", dot: "🔴" },
  Sconosciuto: { cls: "text-amber-700 bg-amber-50 border-amber-200", dot: "🟡" },
};

function StateBadge({ row }: { row: BDRow }) {
  const s = stateStyle[row.stato];
  return (
    <span title={row.stato_motivo}
          className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.dot} {row.stato}
      {row.monitor && " · monitorare"}
    </span>
  );
}

function UsageBar({ row }: { row: BDRow }) {
  const pct = row.perc_utilizzo;
  if (pct == null) return <span className="text-xs text-slate-400">-</span>;
  const width = Math.max(0, Math.min(pct, 1)) * 100;
  const color = pct > 1 ? "bg-red-500" : pct > 0.9 ? "bg-amber-500" : "bg-brand-400";
  return (
    <div className="flex items-center gap-2" title={`${fmtEur(row.consumato)} di ${fmtEur(row.totale)}`}>
      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
      <span className="text-xs text-slate-600 dark:text-slate-300">{fmtPct(pct)}</span>
    </div>
  );
}

export default function BDTracking() {
  const navigate = useNavigate();
  const [stateFilter, setStateFilter] = useState<BDState | "all">("all");
  const [client, setClient] = useState("all");
  const [search, setSearch] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["bd"],
    queryFn: () => api.get<BDOverview>("/api/bd"),
  });
  const { data: status } = useQuery({ queryKey: ["data-status-badge"], queryFn: settingsApi.status });

  const rows = (data?.rows || []).filter(
    (r) =>
      (stateFilter === "all" || r.stato === stateFilter) &&
      (client === "all" || r.cliente === client) &&
      (search === "" ||
        `${r.bd_opp || ""} ${r.opp_name} ${r.wbs_bd || ""}`.toLowerCase().includes(search.toLowerCase())),
  );
  const { sorted, sortKey, dir, toggle } = useSort(
    rows,
    {
      cliente: (r) => r.cliente,
      opp: (r) => r.bd_opp,
      wbs: (r) => r.wbs_bd,
      totale: (r) => r.totale,
      consumato: (r) => r.consumato,
      residuo: (r) => r.residuo,
      uso: (r) => r.perc_utilizzo,
      stato: (r) => r.stato,
    },
    undefined,
  );

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const clients = Array.from(new Set(data.rows.map((r) => r.cliente).filter(Boolean))) as string[];
  const s = data.summary;

  return (
    <div className="p-6">
      <header className="mb-5">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">BD Tracking</h1>
          <DataAsOfBadge lastSync={status?.last_sync} />
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Budget BD dal foglio BD, collegato alle opportunità tramite OppID. Lo stato deriva dall'MMS
          Status dell'opportunità collegata; il residuo è il Delta del foglio.
        </p>
      </header>

      <div className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-3">
        {STATES.map((st) => (
          <button key={st} onClick={() => setStateFilter(stateFilter === st ? "all" : st)} className="text-left">
            <Card className={stateFilter === st ? "ring-2 ring-brand-400" : ""}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                  {stateStyle[st].dot} BD {st.toLowerCase()} ({s[st].count})
                </span>
              </div>
              <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">{fmtEur(s[st].residuo)}</div>
              <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                residuo · consumato {fmtEur(s[st].consumato)} su {fmtEur(s[st].totale)}
              </div>
            </Card>
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cerca opportunità o WBS…"
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        />
        <select
          value={client}
          onChange={(e) => setClient(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        >
          <option value="all">Tutti i clienti</option>
          {clients.sort().map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        {stateFilter !== "all" && (
          <button onClick={() => setStateFilter("all")} className="text-xs text-brand-700 hover:underline dark:text-brand-400">
            Mostra tutti gli stati
          </button>
        )}
        <span className="ml-auto text-xs text-slate-400">{rows.length} di {data.rows.length} righe</span>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
                <SortTh label="Cliente" sortKey="cliente" activeKey={sortKey} dir={dir} onSort={toggle} className="py-2" />
                <SortTh label="Opportunità BD" sortKey="opp" activeKey={sortKey} dir={dir} onSort={toggle} />
                <th>Opp collegata</th>
                <SortTh label="WBS BD" sortKey="wbs" activeKey={sortKey} dir={dir} onSort={toggle} />
                <SortTh label="Totale" sortKey="totale" activeKey={sortKey} dir={dir} onSort={toggle} className="text-right" />
                <SortTh label="Consumato" sortKey="consumato" activeKey={sortKey} dir={dir} onSort={toggle} className="text-right" />
                <SortTh label="Residuo" sortKey="residuo" activeKey={sortKey} dir={dir} onSort={toggle} className="text-right" />
                <SortTh label="Utilizzo" sortKey="uso" activeKey={sortKey} dir={dir} onSort={toggle} />
                <SortTh label="Stato BD" sortKey="stato" activeKey={sortKey} dir={dir} onSort={toggle} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 align-top dark:border-slate-800">
                  <td className="py-2 text-slate-600 dark:text-slate-300">{r.cliente || "-"}</td>
                  <td className="max-w-xs font-medium text-slate-700 dark:text-slate-200" title={r.note || undefined}>
                    {r.bd_opp || "-"}
                    <div className="text-xs font-normal text-slate-400">OppID {r.opp_id || "-"}</div>
                  </td>
                  <td className="max-w-xs">
                    {r.opportunity_id ? (
                      <button
                        onClick={() => navigate(`/opportunities/${r.opportunity_id}`)}
                        className="text-left text-brand-700 hover:underline dark:text-brand-400"
                      >
                        {r.opp_name}
                      </button>
                    ) : (
                      <span className="text-slate-400">N/D</span>
                    )}
                    {r.opportunity_id && (
                      <div className="text-xs text-slate-400">
                        {r.opp_fy} · MMS {r.mms_status || "(vuoto)"}
                        {r.linked_by === "nome" && " · collegata per nome"}
                      </div>
                    )}
                  </td>
                  <td className="whitespace-nowrap text-slate-600 dark:text-slate-300">
                    {r.wbs_bd || "-"}
                    {r.stop_utilizzo && (
                      <div className="text-xs font-semibold text-red-600">STOP UTILIZZO</div>
                    )}
                  </td>
                  <td className="text-right">{fmtEur(r.totale)}</td>
                  <td className="text-right">{fmtEur(r.consumato)}</td>
                  <td className={`text-right font-medium ${r.residuo < 0 ? "text-red-600" : "text-slate-700 dark:text-slate-200"}`}>
                    {fmtEur(r.residuo)}
                  </td>
                  <td><UsageBar row={r} /></td>
                  <td><StateBadge row={r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
          <span>🔴 Chiuso: opp CloseWon, budget non più utilizzabile</span>
          <span>🟢 Attivo: opp in stage 0, 1 o 3B (3B da monitorare)</span>
          <span>🟡 Sconosciuto: OppID non trovato o MMS Status vuoto</span>
        </div>
      </Card>
    </div>
  );
}
