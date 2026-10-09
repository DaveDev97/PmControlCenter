/**
 * Account Overview — sezione finanziaria di sintesi in cima alla pagina Account.
 *
 * Legge i dati freschi dall'endpoint /api/account-overview ogni volta che
 * cambiano i filtri (FY, contratto, periodo). Non modifica alcun contenuto
 * preesistente della pagina.
 */
import { useState, useEffect } from "react";
import { ChevronDown, AlertTriangle, Loader2, TrendingUp, TrendingDown } from "lucide-react";
import { api } from "../lib/api";

// ── Tipi ─────────────────────────────────────────────────────────────────────

interface OverviewData {
  available: boolean;
  error?: string;
  fy: string;
  fy_start: string;
  fy_end: string;
  contracts_available: { id: string; label: string }[];
  sales: { amount: number; count: number };
  revenue: { amount: number; coverage_pct: number | null };
  costi_ad_oggi: { amount: number; pct_spazio_costi: number | null };
  costi_totali_fy: { amount: number; cci_proiettato: number | null };
  monthly: MonthRow[];
  per_contract: ContractRow[];
  warnings: string[];
}

interface MonthRow {
  month: string;
  month_label: string;
  revenue: number;
  costi_allocati: number | null;
  costi_pianificati: number;
  spazio_costi: number;
  cci: number | null;
  is_past: boolean;
}

interface ContractRow {
  id: string;
  name: string;
  revenue_fy: number;
  spazio_costi_fy: number;
}

// ── Formatters ───────────────────────────────────────────────────────────────

/** € 1.234.567,00 — formato italiano */
function fmtEurIT(v: number): string {
  return (
    "€ " +
    v.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
}

function fmtPct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
}

function fmtCci(v: number | null): { text: string; color: string } {
  if (v === null || v === undefined) return { text: "—", color: "text-slate-400" };
  const text = v.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const color = v >= 1.2 ? "text-emerald-600 dark:text-emerald-400"
              : v >= 1.0 ? "text-amber-600 dark:text-amber-400"
              : "text-red-600 dark:text-red-400";
  return { text, color };
}

// ── Logica FY corrente ────────────────────────────────────────────────────────

function currentFyLabel(): string {
  const now = new Date();
  const m = now.getMonth() + 1; // 1-based
  const y = now.getFullYear();
  // Sep–Dec: FY starting this September; Jan–Aug: FY ending this August
  const fyYear = m >= 9 ? y + 1 : y;
  return `FY${String(fyYear).slice(2)}`;
}

// ── Skeleton loader ───────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded bg-slate-200 dark:bg-slate-700 ${className}`} />
  );
}

function CardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <Skeleton className="mb-3 h-3 w-24" />
      <Skeleton className="mb-2 h-7 w-40" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({
  title,
  main,
  sub,
  accent,
}: {
  title: string;
  main: string;
  sub?: string;
  accent?: "green" | "red" | "yellow" | "neutral";
}) {
  const accentClass =
    accent === "green" ? "border-l-4 border-l-emerald-500"
    : accent === "red" ? "border-l-4 border-l-red-500"
    : accent === "yellow" ? "border-l-4 border-l-amber-500"
    : "";

  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800 ${accentClass}`}
    >
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </div>
      <div className="text-xl font-bold text-slate-800 dark:text-white">{main}</div>
      {sub && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{sub}</div>}
    </div>
  );
}

// ── Tabella mensile ───────────────────────────────────────────────────────────

function MonthlyTable({ rows }: { rows: MonthRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60">
            {["Mese", "Revenue", "Costi allocati", "Costi pianificati", "Spazio costi", "CCI"].map(
              (h) => (
                <th
                  key={h}
                  className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-400"
                >
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const cci = fmtCci(r.cci);
            const rowCls = r.is_past
              ? "bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800"
              : "bg-slate-50/60 dark:bg-slate-800/30 text-slate-400 dark:text-slate-500";
            return (
              <tr key={r.month} className={`border-b border-slate-100 dark:border-slate-700/60 ${rowCls}`}>
                <td className="px-3 py-2 font-medium">{r.month_label}</td>
                <td className="px-3 py-2 text-right">{r.revenue > 0 ? fmtEurIT(r.revenue) : "—"}</td>
                <td className="px-3 py-2 text-right">
                  {r.costi_allocati !== null ? fmtEurIT(r.costi_allocati) : "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  {r.costi_pianificati > 0 ? fmtEurIT(r.costi_pianificati) : "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  {r.spazio_costi > 0 ? fmtEurIT(r.spazio_costi) : "—"}
                </td>
                <td className={`px-3 py-2 text-right font-semibold ${cci.color}`}>{cci.text}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-slate-200 bg-slate-100 font-semibold dark:border-slate-600 dark:bg-slate-800">
            <td className="px-3 py-2">Totale FY</td>
            <td className="px-3 py-2 text-right">{fmtEurIT(rows.reduce((s, r) => s + r.revenue, 0))}</td>
            <td className="px-3 py-2 text-right">
              {fmtEurIT(rows.reduce((s, r) => s + (r.costi_allocati ?? 0), 0))}
            </td>
            <td className="px-3 py-2 text-right">
              {fmtEurIT(rows.reduce((s, r) => s + r.costi_pianificati, 0))}
            </td>
            <td className="px-3 py-2 text-right">
              {fmtEurIT(rows.reduce((s, r) => s + r.spazio_costi, 0))}
            </td>
            <td className="px-3 py-2 text-right">—</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ── Tabella per contratto ─────────────────────────────────────────────────────

function ContractTable({
  rows,
  onSelect,
}: {
  rows: ContractRow[];
  onSelect: (id: string) => void;
}) {
  const totRevenue = rows.reduce((s, r) => s + r.revenue_fy, 0);
  const totSpazio = rows.reduce((s, r) => s + r.spazio_costi_fy, 0);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60">
            {["Contratto", "Revenue FY", "Spazio costi FY"].map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-400"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              onClick={() => onSelect(r.id)}
              className="cursor-pointer border-b border-slate-100 bg-white hover:bg-brand-50 dark:border-slate-700/60 dark:bg-slate-900 dark:hover:bg-slate-800"
            >
              <td className="px-3 py-2 font-medium text-brand-700 dark:text-brand-400">
                {r.id} – {r.name}
              </td>
              <td className="px-3 py-2 text-right">{fmtEurIT(r.revenue_fy)}</td>
              <td className="px-3 py-2 text-right">{fmtEurIT(r.spazio_costi_fy)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-slate-200 bg-slate-100 font-semibold dark:border-slate-600 dark:bg-slate-800">
            <td className="px-3 py-2">TOTALE</td>
            <td className="px-3 py-2 text-right">{fmtEurIT(totRevenue)}</td>
            <td className="px-3 py-2 text-right">{fmtEurIT(totSpazio)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ── Componente principale ─────────────────────────────────────────────────────

export default function AccountOverview() {
  const [fy, setFy] = useState<string>(currentFyLabel());
  const [contract, setContract] = useState<string>("all");
  const [period, setPeriod] = useState<"fy" | "monthly">("fy");
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get<OverviewData>(`/api/account-overview?fy=${fy}&contract=${contract}`)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  }, [fy, contract]);

  // When contract changes from "all" to specific, reset period to fy (table disappears)
  const handleContractChange = (id: string) => {
    setContract(id);
    if (id !== "all") setPeriod("fy");
  };

  const contracts = data?.contracts_available ?? [];

  // Determine CCI accent for card 4
  const cci = data?.costi_totali_fy.cci_proiettato ?? null;
  const cciAccent: "green" | "red" | "yellow" | "neutral" =
    cci === null ? "neutral" : cci >= 1.2 ? "green" : cci >= 1.0 ? "yellow" : "red";

  return (
    <section className="mb-0 border-b-4 border-brand-200 bg-slate-50/70 pb-6 pt-5 dark:border-slate-700 dark:bg-slate-900/50">
      <div className="px-6">
        {/* Header ──────────────────────────────────────────────────────────── */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-bold uppercase tracking-wider text-brand-700 dark:text-brand-400">
            Account Overview
          </h2>
          {data && (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              {data.fy_start} → {data.fy_end}
            </span>
          )}
        </div>

        {/* Filtri ──────────────────────────────────────────────────────────── */}
        <div className="mb-5 flex flex-wrap items-center gap-3">
          {/* FY selector */}
          <div className="relative">
            <select
              value={fy}
              onChange={(e) => { setFy(e.target.value); setContract("all"); }}
              className="appearance-none rounded-lg border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm font-medium text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
            >
              <option value="FY26">FY26 (Set 25 – Ago 26)</option>
              <option value="FY27">FY27 (Set 26 – Ago 27)</option>
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-2 top-2.5 text-slate-400" />
          </div>

          {/* Contract selector */}
          <div className="relative">
            <select
              value={contract}
              onChange={(e) => handleContractChange(e.target.value)}
              className="appearance-none rounded-lg border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm font-medium text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
            >
              <option value="all">Tutti i contratti</option>
              {contracts.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-2 top-2.5 text-slate-400" />
          </div>

          {/* Period toggle (only when "all contracts") */}
          {contract === "all" && (
            <div className="flex overflow-hidden rounded-lg border border-slate-300 dark:border-slate-600">
              {(["fy", "monthly"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => setPeriod(v)}
                  className={`px-3 py-1.5 text-sm font-medium transition ${
                    period === v
                      ? "bg-brand-500 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                  }`}
                >
                  {v === "fy" ? "Intero FY" : "Mese per mese"}
                </button>
              ))}
            </div>
          )}

          {loading && <Loader2 size={16} className="animate-spin text-brand-500" />}
        </div>

        {/* Warnings ────────────────────────────────────────────────────────── */}
        {data?.warnings?.length ? (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              {data.warnings.map((w, i) => <div key={i}>{w}</div>)}
            </div>
          </div>
        ) : null}

        {/* Errore ──────────────────────────────────────────────────────────── */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
            Errore nel caricamento dei dati: {error}
          </div>
        )}

        {/* KPI cards ───────────────────────────────────────────────────────── */}
        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {loading ? (
            <>
              <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
            </>
          ) : data?.available ? (
            <>
              {/* Sales FY */}
              <KpiCard
                title="Sales FY"
                main={fmtEurIT(data.sales.amount)}
                sub={
                  data.sales.count > 0
                    ? `${data.sales.count} opportunit${data.sales.count === 1 ? "à" : "à"} chiuse nel FY`
                    : "Nessuna opportunità chiusa nel FY selezionato"
                }
                accent={data.sales.amount > 0 ? "green" : "neutral"}
              />

              {/* Revenue FY */}
              <KpiCard
                title="Revenue FY"
                main={fmtEurIT(data.revenue.amount)}
                sub={
                  data.revenue.coverage_pct !== null
                    ? `Coverage: ${fmtPct(data.revenue.coverage_pct)}`
                    : "Coverage: n/d"
                }
                accent="neutral"
              />

              {/* Costi ad oggi */}
              <KpiCard
                title="Costi sostenuti ad oggi"
                main={fmtEurIT(data.costi_ad_oggi.amount)}
                sub={
                  data.costi_ad_oggi.pct_spazio_costi !== null
                    ? `${fmtPct(data.costi_ad_oggi.pct_spazio_costi)} dello spazio costi FY`
                    : undefined
                }
                accent={
                  (data.costi_ad_oggi.pct_spazio_costi ?? 0) > 100
                    ? "red"
                    : (data.costi_ad_oggi.pct_spazio_costi ?? 0) > 80
                    ? "yellow"
                    : "neutral"
                }
              />

              {/* Costi totali FY */}
              <KpiCard
                title="Costi totali FY (proiezione)"
                main={fmtEurIT(data.costi_totali_fy.amount)}
                sub={
                  data.costi_totali_fy.cci_proiettato !== null ? (
                    undefined
                  ) : undefined
                }
                accent={cciAccent}
              />
            </>
          ) : null}
        </div>

        {/* CCI proiettato badge (fuori dalla card per visibilità) */}
        {!loading && data?.costi_totali_fy.cci_proiettato !== null && (
          <div className="mb-5 flex items-center gap-2">
            {(data!.costi_totali_fy.cci_proiettato ?? 0) >= 1.2 ? (
              <TrendingUp size={14} className="text-emerald-600" />
            ) : (
              <TrendingDown size={14} className="text-red-600" />
            )}
            <span
              className={`text-sm font-semibold ${
                (data!.costi_totali_fy.cci_proiettato ?? 0) >= 1.2
                  ? "text-emerald-700 dark:text-emerald-400"
                  : (data!.costi_totali_fy.cci_proiettato ?? 0) >= 1.0
                  ? "text-amber-700 dark:text-amber-400"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              CCI proiettato: {data!.costi_totali_fy.cci_proiettato?.toLocaleString("it-IT", { minimumFractionDigits: 2 }) ?? "—"}
            </span>
            <span className="text-xs text-slate-400">(target ≥ 1.35)</span>
          </div>
        )}

        {/* Tabella mensile (mese per mese + tutti i contratti) ─────────────── */}
        {!loading && period === "monthly" && contract === "all" && data?.monthly?.length ? (
          <div className="mb-5">
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
              Dettaglio mensile
            </h3>
            <MonthlyTable rows={data.monthly} />
          </div>
        ) : null}

        {/* Tabella per contratto (solo quando "tutti") ─────────────────────── */}
        {!loading && contract === "all" && data?.per_contract?.length ? (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
              Riepilogo per contratto{" "}
              <span className="font-normal normal-case text-slate-400">(clicca per drill-down)</span>
            </h3>
            <ContractTable rows={data.per_contract} onSelect={handleContractChange} />
          </div>
        ) : null}
      </div>
    </section>
  );
}
