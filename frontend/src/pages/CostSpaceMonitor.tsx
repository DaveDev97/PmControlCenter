import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "../lib/api";
import type { BookedCostSpace, PlannedCosts } from "../lib/types";
import { Card, Loading, ErrorBox, AllocationBadge } from "../components/ui";
import { fmtEur, fmtMonth, fmtPct } from "../lib/format";

interface AllocationRow {
  resource_id: number;
  resource_name: string;
  loaded_cost_hourly: number;
  perc_charg: number | null;
  charged_hours: number | null;
  monthly_cost: number | null;
  sheet_cost: number | null;
  status: "ok" | "high" | "over" | "nd";
}

interface AllocationSummary {
  month: string;
  resources: AllocationRow[];
  other_costs: { name: string; cost: number }[];
  totals: {
    sheet_people_cost: number;
    sheet_other_cost: number;
    sheet_total_cost: number;
    sheet_sum_costi: number | null;
    monthly_cost: number; avg_perc_charg: number | null; over: number; high: number; ok: number; nd: number };
}

const ALL_FYS = ["FY25", "FY26", "FY27"];

function Kpi({ label, value, sub, tone = "text-slate-800 dark:text-slate-100" }: {
  label: string; value: string; sub?: string; tone?: string;
}) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${tone}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">{sub}</div>}
    </Card>
  );
}

/** Costs already planned in "Costi vs Forecast": people + other cost lines (= SUM costi). */
function PlannedCostsBlock({ costs, fys, wbs }: {
  costs: PlannedCosts; fys: string[]; wbs: BookedCostSpace["excel_wbs"];
}) {
  const gap = Math.abs(costs.total - costs.sum_costi_sheet);
  const available = wbs.reduce((s, w) => s + (w.available ?? 0), 0);
  return (
    <>
      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Kpi
          label={`Costi previsti ${fys.join(" + ")}`}
          value={fmtEur(costs.total)}
          sub={`risorse ${fmtEur(costs.people)} + altri costi ${fmtEur(costs.other)}`}
        />
        <Kpi
          label="Spazio costi disponibile (foglio)"
          value={wbs.length ? fmtEur(available) : "-"}
          sub={wbs.length ? `colonna Available delle righe ${wbs.map((w) => w.label).join(", ")}` : "righe WBS non trovate"}
          tone={available < 0 ? "text-red-600" : "text-emerald-600"}
        />
        <Kpi
          label="SUM costi nel foglio"
          value={fmtEur(costs.sum_costi_sheet)}
          sub={gap >= 1 ? `differenza ${fmtEur(gap)}: nel foglio alcune celle SUM sono valori fissi o non includono tutte le righe` : "coincide con risorse + altri costi"}
        />
      </div>
      <Card title="Altri costi da sostenere (non risorse)" className="mb-4">
        {costs.other_rows.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Nessuna riga di costo trovata.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
                <th className="py-2">Voce</th>
                <th className="text-right">Totale (colonna LC)</th>
                {fys.map((fy) => (
                  <th key={fy} className="text-right">{fy}</th>
                ))}
                <th className="text-right">Da sostenere da oggi</th>
              </tr>
            </thead>
            <tbody>
              {costs.other_rows.map((o) => (
                <tr key={o.name} className="border-b border-slate-50 dark:border-slate-800">
                  <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{o.name}</td>
                  <td className="text-right">{o.total == null ? "-" : fmtEur(o.total)}</td>
                  {fys.map((fy) => (
                    <td key={fy} className="text-right text-slate-600 dark:text-slate-300">
                      {o.by_fy[fy] ? fmtEur(o.by_fy[fy]) : "-"}
                    </td>
                  ))}
                  <td className="text-right font-medium text-slate-700 dark:text-slate-200">
                    {o.remaining ? fmtEur(o.remaining) : "-"}
                  </td>
                </tr>
              ))}
              <tr className="font-semibold text-slate-700 dark:text-slate-200">
                <td className="py-2">Totale</td>
                <td />
                {fys.map((fy) => (
                  <td key={fy} className="text-right">
                    {fmtEur(costs.other_rows.reduce((s, o) => s + (o.by_fy[fy] || 0), 0))}
                  </td>
                ))}
                <td className="text-right">{fmtEur(costs.other_rows.reduce((s, o) => s + o.remaining, 0))}</td>
              </tr>
            </tbody>
          </table>
        )}
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Subcontratti e costi non legati a una risorsa (es. Spazio costi Fusco, Unicredit, PMO Account), letti
          mese per mese dalle colonne "costo €" del foglio Costi vs Forecast.
        </p>
      </Card>
    </>
  );
}

function BookedSection() {
  const [fys, setFys] = useState<string[]>(["FY26", "FY27"]);
  const [showList, setShowList] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["cost-space-booked", fys],
    queryFn: () => api.get<BookedCostSpace>(`/api/cost-space/booked?fy=${fys.join(",")}`),
    enabled: fys.length > 0,
  });
  const toggleFy = (fy: string) =>
    setFys((cur) => (cur.includes(fy) ? cur.filter((f) => f !== fy) : [...cur, fy].sort()));

  return (
    <section className="mb-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Cost Space bookato</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium uppercase text-slate-400">FY</span>
          {ALL_FYS.map((fy) => (
            <button
              key={fy}
              onClick={() => toggleFy(fy)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                fys.includes(fy)
                  ? "border-brand-500 bg-brand-500 text-white"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
            >
              {fy}
            </button>
          ))}
        </div>
      </div>

      {fys.length === 0 && <p className="text-sm text-slate-500">Seleziona almeno un FY.</p>}
      {isLoading && fys.length > 0 && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && fys.length > 0 && (
        <>
          <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <Kpi
              label="Cost Space bookato"
              value={fmtEur(data.totals.booked_cost_space)}
              sub={`${data.totals.booked_count} opp CloseWon + 3B · ricavi ${fmtEur(data.totals.booked_revenue)}`}
              tone="text-brand-600 dark:text-brand-400"
            />
            <Kpi
              label="Cost Space pipeline (tutto incluso)"
              value={fmtEur(data.totals.pipeline_cost_space)}
              sub={`${data.totals.pipeline_count} opp · ricavi ${fmtEur(data.totals.pipeline_revenue)}`}
              tone="text-slate-400 dark:text-slate-500"
            />
            <Kpi
              label="Delta (non ancora bookato)"
              value={fmtEur(data.totals.delta_cost_space)}
              sub="pipeline − bookato"
            />
          </div>

          {data.planned_costs && <PlannedCostsBlock costs={data.planned_costs} fys={fys} wbs={data.excel_wbs} />}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Per FY">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
                    <th className="py-2">FY</th>
                    <th className="text-right">Bookato</th>
                    <th className="text-right">Pipeline</th>
                    <th className="text-right">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_fy.map((r) => (
                    <tr key={r.fy} className="border-b border-slate-50 dark:border-slate-800">
                      <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{r.fy}</td>
                      <td className="text-right text-slate-700 dark:text-slate-200">{fmtEur(r.booked_cost_space)}</td>
                      <td className="text-right text-slate-400">{fmtEur(r.pipeline_cost_space)}</td>
                      <td className="text-right text-slate-600 dark:text-slate-300">{fmtEur(r.delta_cost_space)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card title="Spazio costi nel foglio Costi vs Forecast">
              {data.excel_wbs.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">Righe WBS non trovate nel foglio.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
                      <th className="py-2">Riga</th>
                      <th className="text-right">Available</th>
                      <th className="text-right">Spazio costi tot</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.excel_wbs.map((w) => (
                      <tr key={w.label} className="border-b border-slate-50 dark:border-slate-800">
                        <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{w.label}</td>
                        <td className="text-right">{w.available == null ? "-" : fmtEur(w.available)}</td>
                        <td className="text-right">{w.total == null ? "-" : fmtEur(w.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                Valori calcolati in Excel, mostrati per confronto con il Cost Space bookato.
              </p>
            </Card>
          </div>

          <button
            onClick={() => setShowList((s) => !s)}
            className="mt-4 flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline dark:text-brand-400"
          >
            {showList ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            Opportunità bookate ({data.booked.length})
          </button>
          {showList && (
            <Card className="mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
                    <th className="py-2">Opportunità</th>
                    <th>FY</th>
                    <th>MMS</th>
                    <th className="text-right">Ricavi</th>
                    <th className="text-right">Cost Space</th>
                  </tr>
                </thead>
                <tbody>
                  {data.booked.map((o) => (
                    <tr key={o.id} className="border-b border-slate-50 dark:border-slate-800">
                      <td className="py-1.5 text-slate-700 dark:text-slate-200">{o.name}</td>
                      <td>{o.fy}</td>
                      <td>{o.mms_status}</td>
                      <td className="text-right">{fmtEur(o.revenues)}</td>
                      <td className="text-right">{fmtEur(o.cost_space)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
          <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
            Cost Space = Ricavi × (1 − CCI target {fmtPct(data.cci_target)}) = Ricavi × {fmtPct(data.ratio)}.
            Bookato: MMS Status CloseWon o 3B. Pipeline: tutte le opportunità non perse.
          </p>
        </>
      )}
    </section>
  );
}

function AllocationSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cost-space-allocation"],
    queryFn: () => api.get<AllocationSummary>("/api/cost-space/summary"),
  });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const over = data.resources.filter((r) => r.status === "over");

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold text-slate-800 dark:text-slate-100">Allocazione risorse (%Charg)</h2>
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Kpi label="Sovrallocate (> 100%)" value={String(data.totals.over)}
             tone={data.totals.over ? "text-red-600" : "text-emerald-600"} />
        <Kpi label="Piene (81–100%)" value={String(data.totals.high)} />
        <Kpi label="%Charg media" value={data.totals.avg_perc_charg == null ? "-" : fmtPct(data.totals.avg_perc_charg)} />
        <Kpi
          label={`Costi del mese ${fmtMonth(data.month)}`}
          value={fmtEur(data.totals.sheet_total_cost)}
          sub={`risorse ${fmtEur(data.totals.sheet_people_cost)} + altri costi ${fmtEur(data.totals.sheet_other_cost)}${
            data.totals.sheet_sum_costi != null ? ` · SUM costi foglio ${fmtEur(data.totals.sheet_sum_costi)}` : ""
          }`}
        />
      </div>

      {over.length > 0 && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
          <AlertTriangle size={20} className="mt-0.5 text-red-600" />
          <div>
            <p className="font-semibold text-red-800 dark:text-red-400">{over.length} risorse sovrallocate</p>
            <p className="text-sm text-red-700 dark:text-red-400">{over.map((r) => r.resource_name).join(", ")}</p>
          </div>
        </div>
      )}

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
              <th className="py-2">Risorsa</th>
              <th>Allocazione</th>
              <th className="text-right">LC (€/h)</th>
              <th className="text-right">Ore caricate / mese</th>
              <th className="text-right">Costo teorico (ore × %Charg × LC)</th>
              <th className="text-right">Costo mese (foglio)</th>
            </tr>
          </thead>
          <tbody>
            {data.resources.map((r) => (
              <tr key={r.resource_id} className="border-b border-slate-50 dark:border-slate-800">
                <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{r.resource_name}</td>
                <td><AllocationBadge value={r.perc_charg} /></td>
                <td className="text-right text-slate-600 dark:text-slate-300">
                  {r.loaded_cost_hourly.toLocaleString("it-IT", { maximumFractionDigits: 2 })}
                </td>
                <td className="text-right text-slate-600 dark:text-slate-300">
                  {r.charged_hours == null ? "-" : `${r.charged_hours.toLocaleString("it-IT")}h`}
                </td>
                <td className="text-right text-slate-600 dark:text-slate-300">
                  {r.monthly_cost == null ? "-" : fmtEur(r.monthly_cost)}
                </td>
                <td className="text-right font-medium text-slate-700 dark:text-slate-200">
                  {r.sheet_cost == null ? "-" : fmtEur(r.sheet_cost)}
                </td>
              </tr>
            ))}
            {data.other_costs.map((o) => (
              <tr key={o.name} className="border-b border-slate-50 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-900/40">
                <td className="py-2 text-slate-600 dark:text-slate-300">{o.name}</td>
                <td><span className="text-xs text-slate-400">altro costo</span></td>
                <td /><td /><td />
                <td className="text-right font-medium text-slate-700 dark:text-slate-200">{fmtEur(o.cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-4 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
          <span>🟢 ≤ 80%</span>
          <span>🟡 81–100%</span>
          <span>🔴 &gt; 100% sovrallocazione reale</span>
          <span>%Charg n/d = colonna vuota nel foglio Costi vs Forecast</span>
        </div>
      </Card>
    </section>
  );
}

export default function CostSpaceMonitor() {
  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-bold text-slate-800 dark:text-slate-100">Cost Space Monitor</h1>
      <BookedSection />
      <AllocationSection />
    </div>
  );
}
