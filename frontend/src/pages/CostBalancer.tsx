import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { Card, Loading, ErrorBox } from "../components/ui";
import { fmtEur, fmtMonth, fmtPct } from "../lib/format";

interface BalanceFigures {
  revenue: number;
  revenue_actual: number;
  revenue_forecast: number;
  costs: number;
  costs_actual: number;
  costs_forecast: number;
  cci: number;
  cci_pct: number | null;
  target: number;
  max_costs: number;
  residual: number;
  revenue_needed: number;
  remaining_months: number;
  remaining_revenue: number;
  remaining_costs: number;
  residual_per_month: number | null;
  months: { month: string; tipo: string; revenue: number; costs: number; cci_pct: number | null; max_costs: number; residual: number }[];
}

interface BalanceOverview {
  fy: string;
  available_fys: string[];
  target: number;
  account: BalanceFigures;
  contracts: (BalanceFigures & { id: string; description: string; wbs: string | null; client: string | null })[];
}

const pct = (v: number | null) => (v == null ? "-" : fmtPct(v));

function Metric({ label, value, sub, tone = "text-slate-800 dark:text-slate-100" }: {
  label: string; value: string; sub?: string; tone?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
      <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-xl font-bold ${tone}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{sub}</div>}
    </div>
  );
}

function BalancePanel({ title, f, fy }: { title: string; f: BalanceFigures; fy: string }) {
  const [showMonths, setShowMonths] = useState(false);
  const below = f.cci_pct != null && f.cci_pct < f.target;
  const empty = !f.revenue && !f.costs;
  const positive = f.residual >= 0;
  return (
    <Card title={title} className="mb-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Metric label="Revenue allocate" value={fmtEur(f.revenue)}
                sub={`actual ${fmtEur(f.revenue_actual)} · forecast ${fmtEur(f.revenue_forecast)}`} />
        <Metric label="Costi allocati" value={fmtEur(f.costs)}
                sub={`consuntivo ${fmtEur(f.costs_actual)} · pianificati ${fmtEur(f.costs_forecast)}`} />
        <Metric label="CCI corrente" value={pct(f.cci_pct)} sub={fmtEur(f.cci)}
                tone={below ? "text-red-600" : "text-emerald-600"} />
        <Metric label="CCI target" value={fmtPct(f.target)} sub={`costi max ${fmtEur(f.max_costs)}`} />
        <Metric label="Spazio residuo utilizzabile" value={fmtEur(f.residual)}
                sub={positive ? "costi ancora sostenibili al target" : "costi da ridurre per tornare al target"}
                tone={positive ? "text-emerald-600" : "text-red-600"} />
        <Metric label="Residuo / mese rimanente"
                value={f.residual_per_month == null ? "-" : fmtEur(f.residual_per_month)}
                sub={`${f.remaining_months} mesi di forecast da oggi`} />
      </div>

      {empty ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
          Nessun dato in {fy}: il foglio Contracts non ha revenue né costi per questo contratto nell'anno selezionato.
        </div>
      ) : (
      <div className={`mt-4 flex items-start gap-2 rounded-lg border p-3 text-sm ${
        positive
          ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-300"
          : "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"
      }`}>
        {positive ? <CheckCircle2 size={16} className="mt-0.5" /> : <AlertTriangle size={16} className="mt-0.5" />}
        <div>
          {positive ? (
            <>In {fy} si possono allocare ancora <strong>{fmtEur(f.residual)}</strong> di costi mantenendo il CCI al{" "}
              {fmtPct(f.target)} (costi max {fmtEur(f.max_costs)} = revenue × {fmtPct(1 - f.target)}).</>
          ) : (
            <>I costi allocati superano di <strong>{fmtEur(-f.residual)}</strong> il massimo compatibile con il CCI al{" "}
              {fmtPct(f.target)}: vanno ridotti di questo importo, oppure servono{" "}
              <strong>{fmtEur(f.revenue_needed)}</strong> di revenue aggiuntive a costi invariati.</>
          )}
        </div>
      </div>
      )}

      <button onClick={() => setShowMonths((s) => !s)}
              className="mt-3 text-xs font-medium text-brand-700 hover:underline dark:text-brand-400">
        {showMonths ? "Nascondi dettaglio mensile" : "Mostra dettaglio mensile"}
      </button>
      {showMonths && (
        <table className="mt-2 w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
              <th className="py-1.5">Mese</th>
              <th>Tipo</th>
              <th className="text-right">Revenue</th>
              <th className="text-right">Costi</th>
              <th className="text-right">CCI %</th>
              <th className="text-right">Costi max al target</th>
              <th className="text-right">Residuo</th>
            </tr>
          </thead>
          <tbody>
            {f.months.map((m) => (
              <tr key={`${m.month}-${m.tipo}`} className="border-b border-slate-50 dark:border-slate-800">
                <td className="py-1">{fmtMonth(m.month)}</td>
                <td className={m.tipo === "actual" ? "" : "text-slate-400"}>{m.tipo}</td>
                <td className="text-right">{fmtEur(m.revenue)}</td>
                <td className="text-right">{fmtEur(m.costs)}</td>
                <td className={`text-right ${m.cci_pct != null && m.cci_pct < f.target ? "text-red-600" : ""}`}>{pct(m.cci_pct)}</td>
                <td className="text-right">{fmtEur(m.max_costs)}</td>
                <td className={`text-right font-medium ${m.residual < 0 ? "text-red-600" : "text-emerald-600"}`}>{fmtEur(m.residual)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export default function CostBalancer() {
  const [fy, setFy] = useState<string | null>(null);
  const [scope, setScope] = useState<string>("all");
  const { data, isLoading, error } = useQuery({
    queryKey: ["cost-balance", fy],
    queryFn: () => api.get<BalanceOverview>(`/api/cost-balance${fy ? `?fy=${fy}` : ""}`),
  });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const shown = scope === "all" ? data.contracts : data.contracts.filter((c) => c.id === scope);

  return (
    <div className="p-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Cost Balancer</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Spazio costi residuo = Revenue × (1 − CCI target {fmtPct(data.target)}) − Costi allocati.
            Fonte: foglio Contracts (actual + forecast).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={data.fy} onChange={(e) => setFy(e.target.value)}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white">
            {data.available_fys.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <select value={scope} onChange={(e) => setScope(e.target.value)}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white">
            <option value="all">Account + tutti i contratti</option>
            {data.contracts.map((c) => (
              <option key={c.id} value={c.id}>{c.client || c.id} · {c.id}</option>
            ))}
          </select>
        </div>
      </header>

      {scope === "all" && <BalancePanel title={`Totale account · ${data.fy}`} f={data.account} fy={data.fy} />}
      {shown.map((c) => (
        <BalancePanel key={c.id} title={`${c.client || "Contratto"} · ${c.id} — ${c.description} (WBS ${c.wbs || "-"})`}
                      f={c} fy={data.fy} />
      ))}
      {data.contracts.length === 0 && <p className="text-sm text-slate-500">Nessun contratto nel foglio Contracts.</p>}
    </div>
  );
}
