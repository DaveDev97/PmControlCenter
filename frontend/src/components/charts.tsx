import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MonthlyPoint } from "../lib/types";
import { fmtEurCompact, fmtMonth } from "../lib/format";

const BRAND = ["#a100ff", "#7500c0", "#be82ff", "#dcafff", "#460073", "#5f009c"];

export function RevCostChart({ data }: { data: MonthlyPoint[] }) {
  const rows = data.map((d) => ({ ...d, label: fmtMonth(d.month) }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#a100ff" stopOpacity={0.5} />
            <stop offset="95%" stopColor="#a100ff" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="cost" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v) => fmtEurCompact(v)} tick={{ fontSize: 11 }} width={60} />
        <Tooltip formatter={(v: number) => fmtEurCompact(v)} />
        <Legend />
        <Area type="monotone" dataKey="revenues" name="Ricavi" stroke="#a100ff" fill="url(#rev)" strokeWidth={2} />
        <Area type="monotone" dataKey="costs" name="Costi" stroke="#f59e0b" fill="url(#cost)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function RevCostBars({ data }: { data: MonthlyPoint[] }) {
  const rows = data.map((d) => ({ ...d, label: fmtMonth(d.month) }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v) => fmtEurCompact(v)} tick={{ fontSize: 11 }} width={60} />
        <Tooltip formatter={(v: number) => fmtEurCompact(v)} />
        <Legend />
        <Bar dataKey="revenues" name="Ricavi" fill="#a100ff" radius={[3, 3, 0, 0]} />
        <Bar dataKey="costs" name="Costi" fill="#be82ff" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DonutBreakdown({ data }: { data: { name: string; value: number }[] }) {
  const clean = data.filter((d) => d.value > 0);
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={clean} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
          {clean.map((_, i) => (
            <Cell key={i} fill={BRAND[i % BRAND.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v: number) => fmtEurCompact(v)} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function PipelineBars({
  data,
}: {
  data: { quarter: string; value: number; count: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis type="number" tickFormatter={(v) => fmtEurCompact(v)} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="quarter" tick={{ fontSize: 11 }} width={50} />
        <Tooltip formatter={(v: number) => fmtEurCompact(v)} />
        <Bar dataKey="value" name="Valore" fill="#7500c0" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
