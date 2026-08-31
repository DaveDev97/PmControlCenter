import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { PersonDashboard as PersonData } from "../lib/types";
import { Card, KpiCard, Loading, ErrorBox } from "../components/ui";
import { RevCostBars, DonutBreakdown } from "../components/charts";
import { fmtEur, fmtPct } from "../lib/format";

export default function PersonDashboard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["person", id],
    queryFn: () => api.get<PersonData>(`/api/dashboard/person/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const r = data.resource;
  const totalUtil = data.allocations.reduce((s, a) => s + a.utilization, 0);

  return (
    <div className="p-6">
      <button onClick={() => navigate(-1)} className="mb-3 text-sm text-brand-600 hover:underline">
        ← Indietro
      </button>
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{r.name}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {r.role_name || "-"} · Tariffa {fmtEur(r.daily_rate)}/gg · {r.status}
        </p>
        {totalUtil > 1 && (
          <span className="mt-2 inline-block rounded-full border border-brand-300 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">
            ⚠️ Overload: {fmtPct(totalUtil)} allocazione totale
          </span>
        )}
      </header>

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-6">
        {data.kpis.map((k) => (
          <KpiCard key={k.label} kpi={k} />
        ))}
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Costo vs Ricavo attribuito (mensile)" className="lg:col-span-2">
          <RevCostBars data={data.monthly} />
        </Card>
        <Card title="Mix contratti (per costo)">
          <DonutBreakdown data={data.contract_mix} />
        </Card>
      </div>

      <Card title="Allocazioni per contratto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <th className="py-2">Contratto</th>
              <th>Cliente</th>
              <th>WBS</th>
              <th>Periodo</th>
              <th className="text-right">Giorni/mese</th>
              <th className="text-right">Util%</th>
              <th className="text-right">Costo/mese</th>
              <th className="text-right">Ricavo/mese</th>
            </tr>
          </thead>
          <tbody>
            {data.allocations.map((a) => (
              <tr
                key={a.contract_id}
                onClick={() => navigate(`/contracts/${a.contract_id}`)}
                className="cursor-pointer border-b border-slate-50 hover:bg-brand-50"
              >
                <td className="py-2 font-medium text-brand-700">
                  {a.contract_id} · {a.contract_name}
                </td>
                <td>{a.client_name}</td>
                <td>{a.wbs || "-"}</td>
                <td className="text-xs text-slate-500 dark:text-slate-400">
                  {a.start_date || "?"} → {a.end_date || "?"}
                </td>
                <td className="text-right">{a.days_per_month}</td>
                <td className="text-right">{fmtPct(a.utilization)}</td>
                <td className="text-right">{fmtEur(a.monthly_cost)}</td>
                <td className="text-right">{fmtEur(a.monthly_revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
