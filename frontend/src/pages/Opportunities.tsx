import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Contract, Opportunity } from "../lib/types";
import { Card, Loading, ErrorBox, DataAsOfBadge } from "../components/ui";
import { fmtEur } from "../lib/format";
import { settingsApi } from "../lib/settings";
import { useSort, SortTh } from "../lib/useTable";

const STAGES = ["Lead", "Qualified", "Proposal", "CloseWon", "CloseLost"];
// Values used in the Opp sheets. "" = empty cell.
const MMS_STATUSES = ["CloseWon", "3B", "1", "0", ""];
const ACN_STATUSES = ["Done", "Da Fatturare", "MMS", ""];
const FYS = ["FY25", "FY26", "FY27"];
const QUARTERS = ["Q1", "Q2", "Q3", "Q4"];

const fyOf = (o: Opportunity) => (o.fiscal_year ? `FY${o.fiscal_year.slice(-2)}` : "-");

/** Inline select for an Excel-backed field; keeps unknown current values selectable. */
function CellSelect({
  value,
  options,
  disabled,
  onChange,
}: {
  value: string | null | undefined;
  options: string[];
  disabled?: boolean;
  onChange: (v: string) => void;
}) {
  const current = value ?? "";
  const opts = options.includes(current) ? options : [current, ...options];
  return (
    <select
      value={current}
      disabled={disabled}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => {
        e.stopPropagation();
        onChange(e.target.value);
      }}
      className="rounded border border-slate-200 bg-white px-2 py-1 text-xs disabled:opacity-50 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
    >
      {opts.map((o) => (
        <option key={o || "empty"} value={o}>
          {o || "(vuoto)"}
        </option>
      ))}
    </select>
  );
}
const LEGAL_ENTITIES = [
  "BNL S.p.A.",
  "Mooney S.p.A.",
  "Cardif",
  "Worldline",
  "Altra"
];

export default function Opportunities() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [fyFilter, setFyFilter] = useState<string>("all");
  const [quarterFilter, setQuarterFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    contract_id: "",
    legal_entity: "",
    estimated_value: 0,
    quarter: "Q1",
    stage: "Lead",
    close_date: "",
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["opportunities"],
    queryFn: () => api.get<Opportunity[]>("/api/opportunities"),
  });
  const { data: contracts } = useQuery({
    queryKey: ["contracts"],
    queryFn: () => api.get<Contract[]>("/api/contracts"),
  });
  const { data: status } = useQuery({ queryKey: ["data-status-badge"], queryFn: settingsApi.status });

  const create = useMutation({
    mutationFn: (body: typeof form) =>
      api.post<Opportunity>("/api/opportunities", {
        ...body,
        contract_id: body.contract_id || null,
        legal_entity: body.legal_entity || null,
        close_date: body.close_date || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      setShowForm(false);
      setForm({ name: "", contract_id: "", legal_entity: "", estimated_value: 0, quarter: "Q1", stage: "Lead", close_date: "" });
    },
  });

  // MMS Status / Stato ACN Tool are written straight into the Excel file.
  const updateField = useMutation({
    mutationFn: ({ id, field, value }: { id: number; field: "mms_status" | "acn_tool_status"; value: string }) =>
      api.put<Opportunity>(`/api/opportunities/${id}`, { [field]: value }),
    onMutate: () => setSaveError(null),
    onError: (e) => setSaveError(e instanceof Error ? e.message.replace(/^\d+: /, "") : String(e)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      qc.invalidateQueries({ queryKey: ["cost-space-booked"] });
      qc.invalidateQueries({ queryKey: ["bd"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/opportunities/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opportunities"] }),
  });

  const accessors = {
    name: (o: Opportunity) => o.name,
    fy: (o: Opportunity) => o.fiscal_year,
    contract: (o: Opportunity) => o.contract_id,
    quarter: (o: Opportunity) => o.quarter,
    value: (o: Opportunity) => o.estimated_value,
    mms: (o: Opportunity) => o.mms_status,
    acn: (o: Opportunity) => o.acn_tool_status,
  };
  const filtered = (data || []).filter(
    (o) =>
      (fyFilter === "all" || fyOf(o) === fyFilter) &&
      (quarterFilter === "all" || o.quarter === quarterFilter) &&
      (search === "" || (o.name || "").toLowerCase().includes(search.toLowerCase())),
  );
  const { sorted, sortKey, dir, toggle } = useSort(filtered, accessors, "value", "desc");

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const total = filtered.reduce((s, o) => s + o.estimated_value, 0);

  return (
    <div className="p-6">
      <header className="mb-5 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Opportunità</h1>
            <DataAsOfBadge lastSync={status?.last_sync} />
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {filtered.length} di {data?.length || 0} opportunità · valore {fmtEur(total)} · MMS Status e
            Stato ACN Tool si salvano direttamente sul file Excel
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowForm((s) => !s)}
            className="rounded-lg bg-brand-400 px-4 py-2 text-sm font-medium text-slate-800 dark:text-white hover:bg-brand-500"
          >
            {showForm ? "Annulla" : "+ Nuova opportunità"}
          </button>
        </div>
      </header>

      {showForm && (
        <Card title="Nuova opportunità" className="mb-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <input
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              placeholder="Nome"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <select
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              value={form.contract_id}
              onChange={(e) => setForm({ ...form, contract_id: e.target.value })}
            >
              <option  value="" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">(nessun contratto)</option>
              {contracts?.map((c) => (
                <option  key={c.id} value={c.id} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">
                  {c.id} · {c.name}
                </option>
              ))}
            </select>
            <select
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white px-3 py-2 text-sm"
              value={form.legal_entity}
              onChange={(e) => setForm({ ...form, legal_entity: e.target.value })}
            >
              <option value="" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">
                (seleziona entity)
              </option>
              {LEGAL_ENTITIES.map((entity) => (
                <option key={entity} value={entity} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">
                  {entity}
                </option>
              ))}
            </select>
            <input
              type="number"
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              placeholder="Valore stimato (€)"
              value={form.estimated_value}
              onChange={(e) => setForm({ ...form, estimated_value: Number(e.target.value) })}
            />
            <select
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              value={form.quarter}
              onChange={(e) => setForm({ ...form, quarter: e.target.value })}
            >
              {["Q1", "Q2", "Q3", "Q4"].map((q) => (
                <option  key={q} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">{q}</option>
              ))}
            </select>
            <select
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
            >
              {STAGES.map((s) => (
                <option  key={s} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">{s}</option>
              ))}
            </select>
            <input
              type="date"
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              value={form.close_date}
              onChange={(e) => setForm({ ...form, close_date: e.target.value })}
            />
          </div>
          <button
            onClick={() => create.mutate(form)}
            disabled={!form.name || create.isPending}
            className="mt-3 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-slate-800 dark:text-white disabled:opacity-50"
          >
            {create.isPending ? "Salvataggio..." : "Salva"}
          </button>
          {create.error && <ErrorBox error={create.error} />}
        </Card>
      )}

      {/* Filters: FY = sheet of origin, Quarter = Close Date Quarter */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cerca per nome…"
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white"
        />
        <span className="ml-2 text-xs font-medium uppercase text-slate-400">FY</span>
        {[...FYS, "all"].map((fy) => (
          <button
            key={fy}
            onClick={() => setFyFilter(fy)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
              fyFilter === fy
                ? "border-brand-500 bg-brand-500 text-white"
                : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            }`}
          >
            {fy === "all" ? "Tutto" : fy}
          </button>
        ))}
        <span className="ml-2 text-xs font-medium uppercase text-slate-400">Quarter</span>
        {["all", ...QUARTERS].map((q) => (
          <button
            key={q}
            onClick={() => setQuarterFilter(q)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
              quarterFilter === q
                ? "border-brand-500 bg-brand-500 text-white"
                : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            }`}
          >
            {q === "all" ? "Tutti" : q}
          </button>
        ))}
      </div>

      {saveError && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Modifica non salvata: {saveError}
        </div>
      )}

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <SortTh label="Nome" sortKey="name" activeKey={sortKey} dir={dir} onSort={toggle} className="py-2" />
              <SortTh label="FY" sortKey="fy" activeKey={sortKey} dir={dir} onSort={toggle} className="pr-3" />
              <SortTh label="Contratto" sortKey="contract" activeKey={sortKey} dir={dir} onSort={toggle} />
              <SortTh label="Quarter" sortKey="quarter" activeKey={sortKey} dir={dir} onSort={toggle} />
              <SortTh label="Valore" sortKey="value" activeKey={sortKey} dir={dir} onSort={toggle} className="text-right" />
              <SortTh label="MMS Status" sortKey="mms" activeKey={sortKey} dir={dir} onSort={toggle} />
              <SortTh label="Stato ACN Tool" sortKey="acn" activeKey={sortKey} dir={dir} onSort={toggle} />
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((o) => (
              <tr
                key={o.id}
                className="cursor-pointer border-b border-slate-50 hover:bg-slate-50 dark:bg-slate-900"
                onClick={() => navigate(`/opportunities/${o.id}`)}
              >
                <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{o.name}</td>
                <td className="pr-3">{fyOf(o)}</td>
                <td>{o.contract_id || "-"}</td>
                <td>{o.quarter || "-"}</td>
                <td className="text-right">{fmtEur(o.estimated_value)}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <CellSelect
                    value={o.mms_status}
                    options={MMS_STATUSES}
                    disabled={!o.source_sheet || updateField.isPending}
                    onChange={(v) => updateField.mutate({ id: o.id, field: "mms_status", value: v })}
                  />
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <CellSelect
                    value={o.acn_tool_status}
                    options={ACN_STATUSES}
                    disabled={!o.source_sheet || updateField.isPending}
                    onChange={(v) => updateField.mutate({ id: o.id, field: "acn_tool_status", value: v })}
                  />
                </td>
                <td className="text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Confermi l'eliminazione di "${o.name}"?`)) {
                        remove.mutate(o.id);
                      }
                    }}
                    className="text-xs text-red-500 hover:underline"
                  >
                    Elimina
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
