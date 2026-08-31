import type { ReactNode } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { HelpCircle } from "lucide-react";
import type { KpiValue } from "../lib/types";
import { fmtKpi, statusColor, statusDot } from "../lib/format";

export function Card({
  title,
  children,
  className = "",
  actions,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800 ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
          {title && <h3 className="text-sm font-semibold text-brand-700 dark:text-brand-400">{title}</h3>}
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

const KPI_TOOLTIPS: Record<string, string> = {
  // Account Dashboard KPIs
  "Revenues YTD": "Somma dei ricavi di tutti i contratti (consuntivo + forecast) per il periodo selezionato.",
  "Costs YTD": "Somma dei costi del personale (Payroll + Not Payroll + Capex) per il periodo selezionato.",
  "Contribution Income": "Revenue - Total Costs. Rappresenta il margine lordo prima dei costi generali.",
  "CI Margin": "Contribution Income come percentuale del Revenue. Formula: (CI / Revenue) × 100",

  // Contract Dashboard KPIs
  "Revenues": "Ricavi totali del contratto per il periodo.",
  "Revenue": "Ricavi totali del contratto per il periodo.",
  "Total Costs": "Costi totali del contratto (Payroll + Not Payroll + Capex).",
  "Costs": "Costi totali del contratto per il periodo.",
  "CI": "Contribution Income del contratto (Revenue - Costs).",
  "CI %": "Margine CI in percentuale. Formula: (CI / Revenue) × 100",
  "Avg Utilization": "Utilizzo medio delle risorse allocate su questo contratto.",
  "Utilization": "Percentuale di utilizzo medio delle risorse allocate.",
  "Billings": "Totale fatturato sul contratto.",
  "Monthly Burn": "Costo mensile medio del contratto.",

  // Team Dashboard KPIs
  "Team Size": "Numero totale di risorse nel team.",
  "Total Cost": "Costo totale mensile del team.",
  "Bench Count": "Numero di risorse non allocate (in panchina).",

  // Person Dashboard KPIs
  "Utilization %": "Percentuale di utilizzo della risorsa sui contratti.",
  "Monthly Cost": "Costo mensile della risorsa basato su rate e giorni.",
  "Contracts": "Numero di contratti su cui la risorsa è allocata.",
  "Daily Rate": "Tariffa giornaliera della risorsa.",

  // Legacy/Alternative labels
  "Total Revenue": "Somma dei ricavi di tutti i contratti (consuntivo + forecast) per il periodo selezionato.",
  "Avg Daily Rate": "Tariffa giornaliera media ponderata. Formula: Σ(Rate × Utilization) / Σ(Utilization)",
  "Billable Rate": "Percentuale di ore fatturabili sul totale ore lavorate.",
  "Burn Rate": "Velocità di consumo del budget (costi mensili medi).",

  // Cost Space KPIs
  "Spazio Disponibile": "Capacità totale di costo mensile: ore lavorative × chargeability × loaded cost",
  "Spazio Allocato": "Costi già assegnati sui contratti attivi per questo mese",
  "Spazio Rimanente": "Differenza tra spazio disponibile e allocato. Negativo indica sovrallocazione",
  "Utilizzo Medio": "Percentuale media di utilizzo delle risorse (allocato / disponibile)",

  // Invoicing KPIs
  "Fatturato YTD": "Totale importi fatturati (invoice status: pagata o emessa) dall'inizio dell'anno",
  "Da Fatturare": "Importo totale ancora da fatturare sulle opportunità chiuse",
  "Invoices Count": "Numero totale di fatture emesse",
};

export function KpiCard({ kpi }: { kpi: KpiValue }) {
  const color = kpi.status ? statusColor[kpi.status] : "text-slate-700 bg-white border-slate-200";
  const tooltipText = KPI_TOOLTIPS[kpi.label];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {kpi.label}
        </div>

        {/* SEMPRE mostra tooltip icon, anche se non c'è testo custom usa label come fallback */}
        <Tooltip.Provider delayDuration={200}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className="text-slate-400 transition-colors hover:text-slate-600 dark:hover:text-slate-300">
                <HelpCircle size={14} />
              </button>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                className="max-w-xs rounded-md bg-slate-800 px-3 py-2 text-xs text-white shadow-lg dark:bg-slate-700"
                sideOffset={5}
              >
                {tooltipText || `Metrica: ${kpi.label}`}
                <Tooltip.Arrow className="fill-slate-800 dark:fill-slate-700" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </Tooltip.Provider>
      </div>

      <div className="mt-1 text-2xl font-bold text-slate-800 dark:text-white">{fmtKpi(kpi)}</div>
      {kpi.status && (
        <span className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
          {statusDot[kpi.status]} {kpi.status}
        </span>
      )}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const color = statusColor[status] || "text-slate-600 bg-slate-50 border-slate-200";
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {statusDot[status] || ""} {status}
    </span>
  );
}

export function Loading({ label = "Caricamento..." }: { label?: string }) {
  return <div className="p-8 text-center text-slate-400 dark:text-slate-500">{label}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="m-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
      Errore: {msg}
    </div>
  );
}
