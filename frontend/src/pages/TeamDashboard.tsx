import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { TeamDashboard as TeamData } from "../lib/types";
import { Card, KpiCard, StatusBadge, Loading, ErrorBox } from "../components/ui";
import { fmtEur, fmtPct, fmtMonth } from "../lib/format";

function heatColor(u: number): string {
  if (u <= 0) return "bg-slate-100 text-slate-300";
  if (u < 0.5) return "bg-red-100 text-red-700";
  if (u < 0.8) return "bg-amber-100 text-amber-700";
  if (u <= 1.0) return "bg-emerald-100 text-emerald-700";
  return "bg-brand-400 text-white"; // overload
}

export default function TeamDashboard() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["team"],
    queryFn: () => api.get<TeamData>("/api/dashboard/team"),
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const heatByRes = new Map<number, Map<string, number>>();
  for (const cell of data.heatmap) {
    if (!heatByRes.has(cell.resource_id)) heatByRes.set(cell.resource_id, new Map());
    heatByRes.get(cell.resource_id)!.set(cell.month, cell.utilization);
  }

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Team Management</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">{data.roster.length} persone attive</p>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {data.kpis.map((k) => (
          <KpiCard key={k.label} kpi={k} />
        ))}
      </div>

      <Card title="Team roster" className="mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <th className="py-2">Nome</th>
              <th>Ruolo</th>
              <th className="text-right">Tariffa</th>
              <th className="text-right">Util%</th>
              <th className="text-right">Contratti</th>
              <th className="text-right">Costo/mese</th>
              <th className="text-right">Ricavo/mese</th>
              <th className="text-right">Margine</th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>
            {data.roster.map((r) => (
              <tr
                key={r.resource_id}
                onClick={() => navigate(`/person/${r.resource_id}`)}
                className="cursor-pointer border-b border-slate-50 hover:bg-brand-50"
              >
                <td className="py-2 font-medium text-brand-700">{r.name}</td>
                <td>{r.role || "-"}</td>
                <td className="text-right">{fmtEur(r.daily_rate)}</td>
                <td className={`text-right font-semibold ${r.utilization > 1 ? "text-brand-500" : ""}`}>
                  {fmtPct(r.utilization)}
                </td>
                <td className="text-right">{r.contracts_count}</td>
                <td className="text-right">{fmtEur(r.monthly_cost)}</td>
                <td className="text-right">{fmtEur(r.monthly_revenue)}</td>
                <td className="text-right">{fmtEur(r.margin)}</td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Heatmap utilizzo (per mese)">
        <div className="overflow-x-auto">
          <table className="text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 bg-white p-2 text-left">Persona</th>
                {data.months.map((m) => (
                  <th key={m} className="p-2 text-center font-medium text-slate-500 dark:text-slate-400">
                    {fmtMonth(m)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.roster.map((r) => {
                const row = heatByRes.get(r.resource_id) || new Map();
                return (
                  <tr key={r.resource_id}>
                    <td className="sticky left-0 bg-white p-2 font-medium text-slate-700 dark:text-slate-200">
                      {r.name}
                    </td>
                    {data.months.map((m) => {
                      const u = row.get(m) || 0;
                      return (
                        <td key={m} className="p-1">
                          <div
                            className={`flex h-8 w-12 items-center justify-center rounded ${heatColor(u)}`}
                            title={`${fmtPct(u)}`}
                          >
                            {u > 0 ? Math.round(u * 100) : ""}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex gap-4 text-xs text-slate-500 dark:text-slate-400">
          <span>🟥 &lt;50% bench</span>
          <span>🟨 50-80% parziale</span>
          <span>🟩 80-100% pieno</span>
          <span className="text-brand-500">🟪 &gt;100% overload</span>
        </div>
      </Card>
    </div>
  );
}
