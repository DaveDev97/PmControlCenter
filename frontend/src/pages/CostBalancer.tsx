import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { CostBalanceProposal, Contract } from "../lib/types";
import { Card, KpiCard, Loading, ErrorBox } from "../components/ui";
import { RevCostBars } from "../components/charts";
import { fmtMonth, fmtEur } from "../lib/format";

export default function CostBalancer() {
  const [selectedContract, setSelectedContract] = useState<string | null>(null);

  const { data: contracts } = useQuery({
    queryKey: ["contracts"],
    queryFn: () => api.get<Contract[]>("/api/contracts"),
  });

  const { data: proposal, isLoading, error } = useQuery({
    queryKey: ["cost-proposal", selectedContract],
    queryFn: () => api.get<CostBalanceProposal>(`/api/cost-balance/proposal/${selectedContract}`),
    enabled: !!selectedContract,
  });

  return (
    <div className="p-6">
      <h1 className="mb-5 text-2xl font-bold text-slate-800 dark:text-slate-100">Cost Balancing Tool</h1>

      <div className="mb-6">
        <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-200">Seleziona Contratto</label>
        <select
          className="w-full max-w-md rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2"
          value={selectedContract || ""}
          onChange={(e) => setSelectedContract(e.target.value || null)}
        >
          <option  value="" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">-- Seleziona --</option>
          {contracts?.map((c) => (
            <option  key={c.id} value={c.id} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">
              {c.id} · {c.name}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <Loading />}
      {error && <ErrorBox error={error} />}

      {proposal && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KpiCard kpi={{ label: "CI% Attuale", value: proposal.ci_pct_current, unit: "PCT" }} />
            <KpiCard kpi={{ label: "CI% Proposto", value: proposal.ci_pct_proposed, unit: "PCT" }} />
            <KpiCard kpi={{ label: "CI Attuale", value: proposal.ci_current, unit: "EUR" }} />
            <KpiCard kpi={{ label: "CI Proposto", value: proposal.ci_proposed, unit: "EUR" }} />
          </div>

          <Card title="Confronto Costi: Attuale vs Proposto" className="mb-6">
            <RevCostBars
              data={proposal.months.map((m, i) => ({
                month: m,
                revenues: proposal.current_revenues[i],
                costs: proposal.current_costs[i],
                ci: 0,
                ci_pct: 0,
                is_actual: false,
              }))}
            />
          </Card>

          <Card title="Breakdown Mensile" className="mb-6">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 dark:border-slate-700 text-left text-xs uppercase text-slate-400">
                  <tr>
                    <th className="py-2">Mese</th>
                    <th className="text-right">Revenue</th>
                    <th className="text-right">Costi Attuali</th>
                    <th className="text-right">CI Attuale</th>
                    <th className="text-right">Costi Proposti</th>
                    <th className="text-right">CI Proposto</th>
                    <th className="text-right">Delta CI</th>
                  </tr>
                </thead>
                <tbody>
                  {proposal.months.map((month, i) => {
                    const currentCI = proposal.current_revenues[i] - proposal.current_costs[i];
                    const proposedCI = proposal.current_revenues[i] - proposal.proposed_costs[i];
                    const delta = proposedCI - currentCI;

                    return (
                      <tr key={month} className="border-b border-slate-50 hover:bg-slate-50 dark:bg-slate-900">
                        <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{fmtMonth(month)}</td>
                        <td className="text-right text-slate-600 dark:text-slate-300">{fmtEur(proposal.current_revenues[i])}</td>
                        <td className="text-right text-slate-600 dark:text-slate-300">{fmtEur(proposal.current_costs[i])}</td>
                        <td className="text-right text-slate-700 dark:text-slate-200">{fmtEur(currentCI)}</td>
                        <td className="text-right font-semibold text-brand-600">
                          {fmtEur(proposal.proposed_costs[i])}
                        </td>
                        <td className="text-right font-semibold text-brand-600">
                          {fmtEur(proposedCI)}
                        </td>
                        <td className={`text-right font-semibold ${delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {delta >= 0 ? '+' : ''}{fmtEur(Math.abs(delta))}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Proposta di Ottimizzazione">
            <p className="text-sm text-slate-600 dark:text-slate-300">{proposal.reason}</p>
          </Card>
        </>
      )}
    </div>
  );
}
