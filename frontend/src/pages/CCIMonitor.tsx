import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import type { CciContract, CciOverview, CciSnapshotValues } from "../lib/types";
import { Card, Loading, ErrorBox } from "../components/ui";
import { CciTrendChart } from "../components/charts";
import { fmtEur, fmtMonth, fmtPct } from "../lib/format";

const pctOrDash = (v: number | null | undefined) => (v == null ? "-" : fmtPct(v));

function SnapshotCard({ title, values, target }: { title: string; values: CciSnapshotValues | null; target: number }) {
  const pct = values?.cci_pct;
  const below = pct != null && pct < target;
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
      <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">{title}</div>
      <div className="mt-1 flex items-center gap-2">
        <span className="text-2xl font-bold text-slate-800 dark:text-slate-100">{pctOrDash(pct)}</span>
        {pct != null && (
          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            below ? "border-red-200 bg-red-50 text-red-600" : "border-emerald-200 bg-emerald-50 text-emerald-600"
          }`}>
            {below ? "🔴 sotto target" : "🟢 in target"}
          </span>
        )}
      </div>
      <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Ricavi {values?.revenue == null ? "-" : fmtEur(values.revenue)} · Costi{" "}
        {values?.total_cost == null ? "-" : fmtEur(values.total_cost)}
      </div>
    </div>
  );
}

function RecoveryBox({ c, target }: { c: CciContract; target: number }) {
  const blocks: { title: string; gapPct: number | null; gapEur: number | null; months: number; leva: number | null }[] = [];
  if (c.recovery_snapshot) {
    blocks.push({
      title: "Forecast del quarter (Sheet1)",
      gapPct: c.recovery_snapshot.gap_pct, gapEur: c.recovery_snapshot.gap_eur,
      months: c.recovery_snapshot.remaining_months, leva: c.recovery_snapshot.leva_ricavi,
    });
  }
  if (c.recovery.below_target) {
    blocks.push({
      title: `${c.recovery.fy} (actual + forecast)`,
      gapPct: c.recovery.gap_pct, gapEur: c.recovery.gap_eur,
      months: c.recovery.remaining_months, leva: c.recovery.leva_ricavi,
    });
  }
  if (blocks.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
        <CheckCircle2 size={16} /> Forecast in linea con il target {fmtPct(target)}.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
      <div className="mb-2 flex items-center gap-2 font-semibold">
        <AlertTriangle size={16} /> CCI sotto il target {fmtPct(target)}: forecast di recupero
      </div>
      {blocks.map((b) => (
        <div key={b.title} className="mb-2 last:mb-0">
          <div className="font-medium">{b.title}</div>
          <div>
            Mancano {pctOrDash(b.gapPct)} di CCI = {b.gapEur == null ? "-" : fmtEur(b.gapEur)} da recuperare.
          </div>
          {b.leva != null ? (
            <div>
              Su {b.months} mesi di forecast: <strong>+{fmtEur(b.leva)}/mese di ricavi</strong> oppure{" "}
              <strong>−{fmtEur(b.leva)}/mese di costi</strong> (o una combinazione).
            </div>
          ) : (
            <div>Nessun mese di forecast rimanente su cui distribuire il recupero.</div>
          )}
        </div>
      ))}
    </div>
  );
}

function ContractPanel({ c, target, quarter }: { c: CciContract; target: number; quarter: string | null }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <Card
      title={`${c.client || "Cliente"} · ${c.id} — ${c.description}`}
      actions={<span className="text-xs text-slate-400">WBS {c.wbs || "-"}</span>}
      className="mb-6"
    >
      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <SnapshotCard title={`CCI Actual ${quarter || ""}`} values={c.snapshot?.actual ?? null} target={target} />
        <SnapshotCard title={`CCI Forecast ${quarter || ""}`} values={c.snapshot?.forecast ?? null} target={target} />
        <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
            CCI {c.recovery.fy} (actual + forecast)
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">{pctOrDash(c.recovery.cci_pct)}</div>
          <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Ricavi {fmtEur(c.recovery.revenue)} · Costi {fmtEur(c.recovery.total_cost)}
          </div>
        </div>
      </div>
      {!c.snapshot && (
        <p className="mb-3 text-xs text-amber-600">
          Cliente non trovato nel foglio Sheet1: KPI Actual/Forecast del quarter non disponibili.
        </p>
      )}

      <div className="mb-4">
        <RecoveryBox c={c} target={target} />
      </div>

      <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Trend mensile CCI %</div>
      <div className="text-xs text-slate-400 dark:text-slate-500">
        Scala da −50% a 100%: i mesi fuori scala e quelli senza ricavi sono nel dettaglio mensile.
      </div>
      <CciTrendChart months={c.months} target={target} />

      <button onClick={() => setShowTable((s) => !s)}
              className="mt-2 text-xs font-medium text-brand-700 hover:underline dark:text-brand-400">
        {showTable ? "Nascondi dettaglio mensile" : "Mostra dettaglio mensile"}
      </button>
      {showTable && (
        <table className="mt-2 w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-700">
              <th className="py-1.5">Mese</th>
              <th>Tipo</th>
              <th className="text-right">Revenue</th>
              <th className="text-right">Total Cost</th>
              <th className="text-right">CCI</th>
              <th className="text-right">CCI %</th>
            </tr>
          </thead>
          <tbody>
            {c.months.map((m) => (
              <tr key={m.month} className="border-b border-slate-50 dark:border-slate-800">
                <td className="py-1">{fmtMonth(m.month)}</td>
                <td className={m.tipo === "actual" ? "text-slate-700 dark:text-slate-200" : "text-slate-400"}>{m.tipo}</td>
                <td className="text-right">{fmtEur(m.revenue)}</td>
                <td className="text-right">{fmtEur(m.total_cost)}</td>
                <td className="text-right">{fmtEur(m.cci)}</td>
                <td className={`text-right font-medium ${m.cci_pct != null && m.cci_pct < target ? "text-red-600" : ""}`}>
                  {pctOrDash(m.cci_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export default function CCIMonitor() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cci"],
    queryFn: () => api.get<CciOverview>("/api/cci"),
  });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  if (!data.available) return <ErrorBox error="File Excel non configurato o non trovato" />;

  const alerts = data.contracts.filter((c) => c.alerts.length > 0);
  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">CCI per contratto</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Fonte: foglio Contracts (P&amp;L ufficiale) e Sheet1 (vista del quarter). CCI = Revenue − Total Cost ·
          CCI % = CCI / Revenue · target {fmtPct(data.target)}
        </p>
      </header>

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Contratti sotto target</div>
          <div className={`mt-1 text-2xl font-bold ${alerts.length ? "text-red-600" : "text-emerald-600"}`}>
            {alerts.length} di {data.contracts.length}
          </div>
        </Card>
        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Quarter Sheet1</div>
          <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">{data.snapshot?.quarter || "-"}</div>
        </Card>
        <Card>
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Spazio costi guadagnato</div>
          <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">
            {data.snapshot?.spazio_costi_guadagnato == null ? "-" : fmtEur(data.snapshot.spazio_costi_guadagnato)}
          </div>
          <div className="mt-1 text-xs text-slate-400">Tot Cost Actual − Tot Cost Forecast (Sheet1)</div>
        </Card>
      </div>

      {data.contracts.length === 0 && (
        <p className="text-sm text-slate-500">Nessun contratto trovato nel foglio Contracts.</p>
      )}
      {data.contracts.map((c) => (
        <ContractPanel key={c.id} c={c} target={data.target} quarter={data.snapshot?.quarter ?? null} />
      ))}
    </div>
  );
}
