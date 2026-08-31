import type { KpiValue } from "./types";

const eur = new Intl.NumberFormat("it-IT", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const eurCompact = new Intl.NumberFormat("it-IT", {
  notation: "compact",
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 1,
});

const pct = new Intl.NumberFormat("it-IT", {
  style: "percent",
  maximumFractionDigits: 1,
});

export const fmtEur = (v: number) => eur.format(v);
export const fmtEurCompact = (v: number) => eurCompact.format(v);
export const fmtPct = (v: number) => pct.format(v);
export const fmtNum = (v: number) =>
  new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(v);

export function fmtKpi(k: KpiValue): string {
  if (k.unit === "PCT") return fmtPct(k.value);
  if (k.unit === "NUM") return fmtNum(k.value);
  return fmtEur(k.value);
}

export const statusColor: Record<string, string> = {
  good: "text-emerald-600 bg-emerald-50 border-emerald-200",
  warning: "text-amber-600 bg-amber-50 border-amber-200",
  bad: "text-red-600 bg-red-50 border-red-200",
  full: "text-emerald-600 bg-emerald-50 border-emerald-200",
  partial: "text-amber-600 bg-amber-50 border-amber-200",
  bench: "text-red-600 bg-red-50 border-red-200",
};

export const statusDot: Record<string, string> = {
  good: "🟢",
  warning: "🟡",
  bad: "🔴",
  full: "🟢",
  partial: "🟡",
  bench: "🔴",
};

// Format "2026-06" -> "Giu 26"
const MONTHS_IT = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];
export function fmtMonth(m: string): string {
  if (!m || typeof m !== "string") return "N/A";
  const parts = m.split("-");
  if (parts.length !== 2) return m; // Return as-is if format is unexpected
  const [y, mo] = parts;
  const monthIndex = parseInt(mo, 10) - 1;
  if (isNaN(monthIndex) || monthIndex < 0 || monthIndex > 11) return m;
  return `${MONTHS_IT[monthIndex]} ${y.slice(2)}`;
}
