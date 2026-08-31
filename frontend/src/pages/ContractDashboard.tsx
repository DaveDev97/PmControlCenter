import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate, Link } from "react-router-dom";
import DatePicker from "react-datepicker";
import { Filter } from "lucide-react";
import { api } from "../lib/api";
import type { ContractDashboard as ContractData } from "../lib/types";
import { Card, KpiCard, Loading, ErrorBox } from "../components/ui";
import { RevCostBars, DonutBreakdown } from "../components/charts";
import { fmtEur, fmtPct } from "../lib/format";

export default function ContractDashboard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState<[Date | null, Date | null]>([null, null]);
  const [selectedFY, setSelectedFY] = useState<string>("2026");
  const [filtersActive, setFiltersActive] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["contract", id, dateRange, selectedFY, filtersActive],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filtersActive && dateRange[0]) {
        const from = `${dateRange[0].getFullYear()}-${String(dateRange[0].getMonth() + 1).padStart(2, "0")}`;
        params.append("from_month", from);
      }
      if (filtersActive && dateRange[1]) {
        const to = `${dateRange[1].getFullYear()}-${String(dateRange[1].getMonth() + 1).padStart(2, "0")}`;
        params.append("to_month", to);
      }
      if (filtersActive && selectedFY) {
        params.append("fy", selectedFY);
      }
      const url = `/api/dashboard/contract/${id}${params.toString() ? `?${params}` : ""}`;
      return api.get<ContractData>(url);
    },
    enabled: !!id,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const c = data.contract;
  const breakdown = [
    { name: "Payroll", value: data.cost_breakdown.payroll || 0 },
    { name: "Non Payroll", value: data.cost_breakdown.non_payroll || 0 },
    { name: "Capital Charges", value: data.cost_breakdown.capital || 0 },
  ];

  const filterControls = (
    <div className="mb-3 flex flex-wrap items-center gap-2 border-t border-slate-100 dark:border-slate-800 pt-3">
      <DatePicker
        selectsRange
        startDate={dateRange[0]}
        endDate={dateRange[1]}
        onChange={(update) => setDateRange(update as [Date | null, Date | null])}
        dateFormat="MM/yyyy"
        showMonthYearPicker
        placeholderText="Range mesi..."
        className="w-40 rounded border border-slate-300 bg-white dark:bg-slate-700 text-slate-800 dark:text-white border-slate-300 dark:border-slate-600 px-2 py-1 text-xs"
      />

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
            setDateRange([null, null]);
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
      <button onClick={() => navigate(-1)} className="mb-3 text-sm text-brand-600 hover:underline">
        ← Indietro
      </button>

      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
          {c.id} · {c.name}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {c.client_name} · WBS {c.wbs_l1 || "-"} · {c.fiscal_year || "-"} · {c.status}
        </p>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-6">
        {data.kpis.map((k) => (
          <KpiCard key={k.label} kpi={k} />
        ))}
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Ricavi & Costi (mensile, actual + forecast)" className="lg:col-span-2">
          {filterControls}
          <RevCostBars data={data.monthly} />
        </Card>
        <Card title="Ripartizione costi">
          <DonutBreakdown data={breakdown} />
        </Card>
      </div>

      <Card title="Allocazione persone">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <th className="py-2">Nome</th>
              <th>Ruolo</th>
              <th className="text-right">Giorni/mese</th>
              <th className="text-right">Tariffa</th>
              <th className="text-right">Util%</th>
              <th className="text-right">Costo/mese</th>
              <th className="text-right">Ricavo attribuito</th>
            </tr>
          </thead>
          <tbody>
            {data.people.map((p) => (
              <tr
                key={p.resource_id}
                onClick={() => navigate(`/person/${p.resource_id}`)}
                className="cursor-pointer border-b border-slate-50 hover:bg-brand-50"
              >
                <td className="py-2 font-medium text-brand-700">{p.resource_name}</td>
                <td>{p.role || "-"}</td>
                <td className="text-right">{p.days_per_month}</td>
                <td className="text-right">{fmtEur(p.daily_rate)}</td>
                <td className="text-right">{fmtPct(p.utilization)}</td>
                <td className="text-right">{fmtEur(p.monthly_cost)}</td>
                <td className="text-right">{fmtEur(p.monthly_revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-slate-400">
          Ricavo attribuito = ricavo del contratto (ultimo mese actual) ripartito in base alla
          quota di costo della persona. <Link to="/team" className="text-brand-600">Vista team →</Link>
        </p>
      </Card>
    </div>
  );
}
