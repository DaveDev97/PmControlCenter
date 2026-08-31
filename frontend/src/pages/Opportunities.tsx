import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Contract, Opportunity } from "../lib/types";
import { Card, Loading, ErrorBox, StatusBadge } from "../components/ui";
import { fmtEur } from "../lib/format";

const STAGES = ["Lead", "Qualified", "Proposal", "CloseWon", "CloseLost"];

export default function Opportunities() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    contract_id: "",
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

  const create = useMutation({
    mutationFn: (body: typeof form) =>
      api.post<Opportunity>("/api/opportunities", {
        ...body,
        contract_id: body.contract_id || null,
        close_date: body.close_date || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      setShowForm(false);
      setForm({ name: "", contract_id: "", estimated_value: 0, quarter: "Q1", stage: "Lead", close_date: "" });
    },
  });

  const updateStage = useMutation({
    mutationFn: ({ id, stage }: { id: number; stage: string }) =>
      api.put<Opportunity>(`/api/opportunities/${id}`, { stage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opportunities"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/opportunities/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opportunities"] }),
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  const total = (data || []).reduce((s, o) => s + o.estimated_value, 0);

  return (
    <div className="p-6">
      <header className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Opportunità</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {data?.length || 0} opportunità · pipeline {fmtEur(total)}
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-lg bg-brand-400 px-4 py-2 text-sm font-medium text-slate-800 dark:text-white hover:bg-brand-500"
        >
          {showForm ? "Annulla" : "+ Nuova opportunità"}
        </button>
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

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <th className="py-2">Nome</th>
              <th>Contratto</th>
              <th>Quarter</th>
              <th className="text-right">Valore</th>
              <th>Stage</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.map((o) => (
              <tr
                key={o.id}
                className="cursor-pointer border-b border-slate-50 hover:bg-slate-50 dark:bg-slate-900"
                onClick={() => navigate(`/opportunities/${o.id}`)}
              >
                <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{o.name}</td>
                <td>{o.contract_id || "-"}</td>
                <td>{o.quarter || "-"}</td>
                <td className="text-right">{fmtEur(o.estimated_value)}</td>
                <td>
                  <select
                    value={o.stage}
                    onChange={(e) => updateStage.mutate({ id: o.id, stage: e.target.value })}
                    className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1 text-xs"
                  >
                    {STAGES.map((s) => (
                      <option  key={s} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">{s}</option>
                    ))}
                  </select>
                </td>
                <td className="text-right">
                  <button
                    onClick={() => remove.mutate(o.id)}
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
