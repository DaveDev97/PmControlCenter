import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import DatePicker from "react-datepicker";
import { Filter, HelpCircle, Presentation, Loader2 } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { api } from "../lib/api";
import type { AccountDashboard as AccountData } from "../lib/types";
import { Card, KpiCard, StatusBadge, Loading, ErrorBox } from "../components/ui";
import { RevCostChart, PipelineBars } from "../components/charts";
import { fmtEur, fmtPct } from "../lib/format";

export default function AccountDashboard() {
  const navigate = useNavigate();
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [selectedFY, setSelectedFY] = useState<string>("2026");
  const [compareFY, setCompareFY] = useState(false);
  const [filtersActive, setFiltersActive] = useState(false);
  const [genPpt, setGenPpt] = useState(false);

  async function generatePpt() {
    setGenPpt(true);
    try {
      const base = (window as unknown as { __API_BASE__?: string }).__API_BASE__ || "";
      const res = await fetch(`${base}/api/reports/account-ppt`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Account_Summary.pptx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("Errore nella generazione del PPT: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setGenPpt(false);
    }
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ["account", startDate, endDate, selectedFY, compareFY, filtersActive],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filtersActive && startDate) {
        const from = `${startDate.getFullYear()}-${String(startDate.getMonth() + 1).padStart(2, "0")}`;
        params.append("from_month", from);
      }
      if (filtersActive && endDate) {
        const to = `${endDate.getFullYear()}-${String(endDate.getMonth() + 1).padStart(2, "0")}`;
        params.append("to_month", to);
      }
      if (filtersActive && selectedFY) {
        params.append("fy", selectedFY);
      }
      if (filtersActive && compareFY) {
        params.append("compare", "true");
      }
      const url = `/api/dashboard/account${params.toString() ? `?${params}` : ""}`;
      return api.get<AccountData>(url);
    },
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  // Aggregate pipeline by quarter for the bar chart.
  const byQuarter = Object.values(
    data.pipeline.reduce<Record<string, { quarter: string; value: number; count: number }>>(
      (acc, p) => {
        acc[p.quarter] = acc[p.quarter] || { quarter: p.quarter, value: 0, count: 0 };
        acc[p.quarter].value += p.value;
        acc[p.quarter].count += p.count;
        return acc;
      },
      {}
    )
  ).sort((a, b) => a.quarter.localeCompare(b.quarter));

  const filterControls = (
    <div className="mb-3 flex flex-wrap items-center gap-2 border-t border-slate-100 dark:border-slate-800 pt-3">
      <div className="flex items-center gap-1">
        <label className="text-xs text-slate-600 dark:text-slate-300">Da:</label>
        <DatePicker
          selected={startDate}
          onChange={(date) => setStartDate(date)}
          dateFormat="MM/yyyy"
          showMonthYearPicker
          placeholderText="mm/aaaa"
          className="w-24 rounded border border-slate-300 bg-white dark:bg-slate-700 text-slate-800 dark:text-white border-slate-300 dark:border-slate-600 px-2 py-1 text-xs"
        />
      </div>

      <div className="flex items-center gap-1">
        <label className="text-xs text-slate-600 dark:text-slate-300">A:</label>
        <DatePicker
          selected={endDate}
          onChange={(date) => setEndDate(date)}
          dateFormat="MM/yyyy"
          showMonthYearPicker
          placeholderText="mm/aaaa"
          className="w-24 rounded border border-slate-300 bg-white dark:bg-slate-700 text-slate-800 dark:text-white border-slate-300 dark:border-slate-600 px-2 py-1 text-xs"
        />
      </div>

      <select
        value={selectedFY}
        onChange={(e) => setSelectedFY(e.target.value)}
        className="rounded border border-slate-300 bg-white dark:bg-slate-700 text-slate-800 dark:text-white border-slate-300 dark:border-slate-600 px-2 py-1 text-xs"
      >
        <option  value="2024" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">FY 2024</option>
        <option  value="2025" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">FY 2025</option>
        <option  value="2026" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">FY 2026</option>
        <option  value="2027" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">FY 2027</option>
      </select>

      <button
        onClick={() => setCompareFY(!compareFY)}
        className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
          compareFY
            ? "bg-amber-600 text-white"
            : "border border-slate-300 bg-white text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:bg-slate-900"
        }`}
        title={`Confronta con FY ${parseInt(selectedFY) - 1}`}
      >
        {compareFY ? `vs FY ${parseInt(selectedFY) - 1}` : "Compare FY"}
      </button>

      <button
        onClick={() => setFiltersActive(!filtersActive)}
        className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
          filtersActive
            ? "bg-brand-600 text-white"
            : "border border-slate-300 bg-white text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:bg-slate-900"
        }`}
      >
        {filtersActive ? "✓ Attivi" : "Applica"}
      </button>

      {filtersActive && (
        <button
          onClick={() => {
            setStartDate(null);
            setEndDate(null);
            setCompareFY(false);
            setFiltersActive(false);
          }}
          className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:text-slate-200 underline"
        >
          Reset
        </button>
      )}
    </div>
  );

  return (
    <div className="p-6">
      <header className="mb-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Account Dashboard</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {data.client_name} · {data.contracts_count} contratti attivi ·{" "}
              {data.opportunities_count} opportunità
            </p>
          </div>
          <div className="flex items-start gap-3">
            <button
              onClick={generatePpt}
              disabled={genPpt}
              className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white shadow transition hover:bg-brand-600 disabled:opacity-50"
              title="Genera un riepilogo PPT dell'account (usa Claude Code)"
            >
              {genPpt ? <Loader2 size={16} className="animate-spin" /> : <Presentation size={16} />}
              {genPpt ? "Generazione…" : "Genera PPT"}
            </button>
            <div className="rounded-lg bg-brand-100 px-4 py-2 text-right">
            <div className="text-xs font-medium text-brand-700">Fiscal Year</div>
            <div className="text-2xl font-bold text-brand-800">
              FY {selectedFY}
              {filtersActive && compareFY && (
                <span className="ml-2 text-sm text-amber-700">vs FY {parseInt(selectedFY) - 1}</span>
              )}
            </div>
            {filtersActive && startDate && (
              <div className="mt-1 text-xs text-brand-600">
                {startDate.toLocaleDateString('it-IT', { month: 'short', year: 'numeric' })}
                {endDate && ` - ${endDate.toLocaleDateString('it-IT', { month: 'short', year: 'numeric' })}`}
              </div>
            )}
            </div>
          </div>
        </div>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {data.kpis.map((k) => (
          <KpiCard key={k.label} kpi={k} />
        ))}
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Ricavi vs Costi (mensile)" className="lg:col-span-2">
          {filterControls}
          <RevCostChart data={data.monthly} />
        </Card>
        <Card title="Pipeline opportunità (per quarter)">
          <PipelineBars data={byQuarter} />
        </Card>
      </div>

      <Card title="Contratti">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <th className="py-2">Contratto</th>
              <th>Cliente</th>
              <th className="text-right">
                <span className="inline-flex items-center gap-1">
                  Ricavi
                  <Tooltip.Provider delayDuration={200}>
                    <Tooltip.Root>
                      <Tooltip.Trigger asChild>
                        <HelpCircle size={12} className="text-slate-400" />
                      </Tooltip.Trigger>
                      <Tooltip.Portal>
                        <Tooltip.Content className="max-w-xs rounded-md bg-slate-800 px-3 py-2 text-xs text-slate-800 dark:text-white shadow-lg" sideOffset={5}>
                          Totale ricavi YTD del contratto
                          <Tooltip.Arrow className="fill-slate-800" />
                        </Tooltip.Content>
                      </Tooltip.Portal>
                    </Tooltip.Root>
                  </Tooltip.Provider>
                </span>
              </th>
              <th className="text-right">
                <span className="inline-flex items-center gap-1">
                  Costi
                  <Tooltip.Provider delayDuration={200}>
                    <Tooltip.Root>
                      <Tooltip.Trigger asChild>
                        <HelpCircle size={12} className="text-slate-400" />
                      </Tooltip.Trigger>
                      <Tooltip.Portal>
                        <Tooltip.Content className="max-w-xs rounded-md bg-slate-800 px-3 py-2 text-xs text-slate-800 dark:text-white shadow-lg" sideOffset={5}>
                          Totale costi YTD del contratto
                          <Tooltip.Arrow className="fill-slate-800" />
                        </Tooltip.Content>
                      </Tooltip.Portal>
                    </Tooltip.Root>
                  </Tooltip.Provider>
                </span>
              </th>
              <th className="text-right">
                <span className="inline-flex items-center gap-1">
                  CI
                  <Tooltip.Provider delayDuration={200}>
                    <Tooltip.Root>
                      <Tooltip.Trigger asChild>
                        <HelpCircle size={12} className="text-slate-400" />
                      </Tooltip.Trigger>
                      <Tooltip.Portal>
                        <Tooltip.Content className="max-w-xs rounded-md bg-slate-800 px-3 py-2 text-xs text-slate-800 dark:text-white shadow-lg" sideOffset={5}>
                          Contribution Income (Ricavi - Costi)
                          <Tooltip.Arrow className="fill-slate-800" />
                        </Tooltip.Content>
                      </Tooltip.Portal>
                    </Tooltip.Root>
                  </Tooltip.Provider>
                </span>
              </th>
              <th className="text-right">
                <span className="inline-flex items-center gap-1">
                  CI %
                  <Tooltip.Provider delayDuration={200}>
                    <Tooltip.Root>
                      <Tooltip.Trigger asChild>
                        <HelpCircle size={12} className="text-slate-400" />
                      </Tooltip.Trigger>
                      <Tooltip.Portal>
                        <Tooltip.Content className="max-w-xs rounded-md bg-slate-800 px-3 py-2 text-xs text-slate-800 dark:text-white shadow-lg" sideOffset={5}>
                          CI % = (CI / Ricavi) × 100
                          <Tooltip.Arrow className="fill-slate-800" />
                        </Tooltip.Content>
                      </Tooltip.Portal>
                    </Tooltip.Root>
                  </Tooltip.Provider>
                </span>
              </th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>
            {data.contracts.map((c) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/contracts/${c.id}`)}
                className="cursor-pointer border-b border-slate-50 hover:bg-brand-50"
              >
                <td className="py-2 font-medium text-brand-700">
                  {c.id} · {c.name}
                </td>
                <td>{c.client_name}</td>
                <td className="text-right">{fmtEur(c.revenues)}</td>
                <td className="text-right">{fmtEur(c.costs)}</td>
                <td className="text-right">{fmtEur(c.ci)}</td>
                <td className="text-right font-semibold">{fmtPct(c.ci_pct)}</td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
