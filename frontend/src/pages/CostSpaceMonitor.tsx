import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { api } from "../lib/api";
import { Card, Loading } from "../components/ui";

interface CostSpaceRow {
  resource_id: number;
  resource_name: string;
  chargeability: number;
  loaded_cost_hourly: number;
  available_hours: number;
  available_cost_space: number;
  allocated_hours: number;
  allocated_cost_space: number;
  remaining_hours: number;
  remaining_cost_space: number;
  utilization_pct: number;
  status: string;
}

interface CostSpaceSummary {
  month: string;
  resources: CostSpaceRow[];
  totals: {
    available_cost_space: number;
    allocated_cost_space: number;
    remaining_cost_space: number;
    avg_utilization_pct: number;
  };
}

interface PipelineImpact {
  total_pipeline_value: number;
  estimated_cost_space_required: number;
  opportunities_count: number;
}

const statusColors: Record<string, string> = {
  overallocated: "bg-red-100 border-red-300 text-red-800",
  full: "bg-amber-100 border-amber-300 text-amber-800",
  partial: "bg-blue-100 border-blue-300 text-blue-800",
  available: "bg-green-100 border-green-300 text-green-800",
};

const statusIcons: Record<string, JSX.Element> = {
  overallocated: <AlertTriangle size={14} className="text-red-600" />,
  full: <TrendingUp size={14} className="text-amber-600" />,
  partial: <Minus size={14} className="text-blue-600" />,
  available: <TrendingDown size={14} className="text-green-600" />,
};

function fmtEur(n: number) {
  return `€${n.toLocaleString("it-IT", { maximumFractionDigits: 0 })}`;
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

export default function CostSpaceMonitor() {
  const [selectedMonth, setSelectedMonth] = useState("2026-08");

  const { data: summary, isLoading } = useQuery<CostSpaceSummary>({
    queryKey: ["cost-space", selectedMonth],
    queryFn: () => api.get(`/api/cost-space/summary?month=${selectedMonth}`),
  });

  const { data: pipeline } = useQuery<PipelineImpact>({
    queryKey: ["pipeline-impact"],
    queryFn: () => api.get("/api/cost-space/pipeline-impact"),
  });

  if (isLoading) return <Loading />;
  if (!summary) return null;

  const overallocated = summary.resources.filter((r) => r.status === "overallocated");
  const available = summary.resources.filter((r) => r.status === "available");

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Cost Space Monitor</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600 dark:text-slate-300">Mese:</label>
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2"
          >
            {Array.from({ length: 12 }, (_, i) => {
              const month = `2026-${String(i + 1).padStart(2, "0")}`;
              return (
                <option  key={month} value={month} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">
                  {new Date(month).toLocaleDateString("it-IT", { month: "long", year: "numeric" })}
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Spazio Disponibile</div>
          <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">
            {fmtEur(summary.totals.available_cost_space)}
          </div>
        </Card>

        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Spazio Allocato</div>
          <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">
            {fmtEur(summary.totals.allocated_cost_space)}
          </div>
        </Card>

        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Spazio Rimanente</div>
          <div
            className={`mt-1 text-2xl font-bold ${
              summary.totals.remaining_cost_space < 0 ? "text-red-600" : "text-green-600"
            }`}
          >
            {fmtEur(summary.totals.remaining_cost_space)}
          </div>
        </Card>

        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Utilizzo Medio</div>
          <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">
            {fmtPct(summary.totals.avg_utilization_pct)}
          </div>
        </Card>
      </div>

      {/* Alerts */}
      {overallocated.length > 0 && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle size={20} className="mt-0.5 text-red-600" />
            <div>
              <p className="font-semibold text-red-800">
                {overallocated.length} risorse sovrallocate
              </p>
              <p className="text-sm text-red-700">
                {overallocated.map((r) => r.resource_name.split("@")[0]).join(", ")}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Impact */}
      {pipeline && (
        <Card title="Impatto Pipeline" className="mb-6">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Valore Totale Pipeline</div>
              <div className="text-xl font-semibold text-slate-800 dark:text-slate-100">
                {fmtEur(pipeline.total_pipeline_value)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Costi Stimati</div>
              <div className="text-xl font-semibold text-slate-800 dark:text-slate-100">
                {fmtEur(pipeline.estimated_cost_space_required)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Opportunità</div>
              <div className="text-xl font-semibold text-slate-800 dark:text-slate-100">
                {pipeline.opportunities_count}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Resources Table */}
      <Card title="Dettaglio per Risorsa">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 dark:border-slate-700 text-left text-xs uppercase text-slate-400">
              <tr>
                <th className="py-2">Risorsa</th>
                <th className="text-center">Chargeability</th>
                <th className="text-right">Ore Disponibili</th>
                <th className="text-right">Spazio Disponibile</th>
                <th className="text-right">Ore Allocate</th>
                <th className="text-right">Spazio Allocato</th>
                <th className="text-right">Rimanenti (Ore)</th>
                <th className="text-right">Rimanenti (€)</th>
                <th className="text-center">Utilizzo</th>
                <th className="text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {summary.resources.map((row) => (
                <tr
                  key={row.resource_id}
                  className="border-b border-slate-50 hover:bg-slate-50 dark:bg-slate-900"
                >
                  <td className="py-2 font-medium text-slate-700 dark:text-slate-200">
                    {row.resource_name.split("@")[0]}
                  </td>
                  <td className="text-center text-slate-600 dark:text-slate-300">{fmtPct(row.chargeability)}</td>
                  <td className="text-right text-slate-600 dark:text-slate-300">
                    {row.available_hours.toFixed(1)}h
                  </td>
                  <td className="text-right text-slate-600 dark:text-slate-300">
                    {fmtEur(row.available_cost_space)}
                  </td>
                  <td className="text-right text-slate-600 dark:text-slate-300">
                    {row.allocated_hours.toFixed(1)}h
                  </td>
                  <td className="text-right text-slate-600 dark:text-slate-300">
                    {fmtEur(row.allocated_cost_space)}
                  </td>
                  <td
                    className={`text-right font-medium ${
                      row.remaining_hours < 0 ? "text-red-600" : "text-green-600"
                    }`}
                  >
                    {row.remaining_hours >= 0 ? "+" : ""}
                    {row.remaining_hours.toFixed(1)}h
                  </td>
                  <td
                    className={`text-right font-medium ${
                      row.remaining_cost_space < 0 ? "text-red-600" : "text-green-600"
                    }`}
                  >
                    {row.remaining_cost_space >= 0 ? "+" : ""}
                    {fmtEur(row.remaining_cost_space)}
                  </td>
                  <td className="text-center font-medium text-slate-700 dark:text-slate-200">
                    {fmtPct(row.utilization_pct)}
                  </td>
                  <td className="text-center">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
                        statusColors[row.status]
                      }`}
                    >
                      {statusIcons[row.status]}
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div className="mt-4 flex gap-4 border-t border-slate-100 dark:border-slate-800 pt-4 text-xs text-slate-600 dark:text-slate-300">
          <div className="flex items-center gap-1">
            <div className="h-3 w-3 rounded-full bg-red-200"></div>
            <span>Overallocated (&gt;100%)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="h-3 w-3 rounded-full bg-amber-200"></div>
            <span>Full (≥80%)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="h-3 w-3 rounded-full bg-blue-200"></div>
            <span>Partial (50-80%)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="h-3 w-3 rounded-full bg-green-200"></div>
            <span>Available (&lt;50%)</span>
          </div>
        </div>
      </Card>

      {/* Info */}
      <Card title="Info" className="mt-6">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          <strong>Spazio Costi</strong> = ore mensili × chargeability × costo orario caricato (loaded
          cost).
          <br />
          Il monitoraggio confronta lo spazio disponibile con quanto allocato sui contratti attivi.
          <br />
          <strong>Chargeability</strong> rappresenta la percentuale di ore caricabili per ogni risorsa
          (es. 80% = 128h su 160h mensili).
        </p>
      </Card>
    </div>
  );
}
