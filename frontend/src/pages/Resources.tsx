import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Resource, Role } from "../lib/types";
import { Card, Loading, ErrorBox } from "../components/ui";
import { fmtEur } from "../lib/format";

export default function Resources() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", daily_rate: 0, role_id: "" as string | number, email: "" });

  const { data, isLoading, error } = useQuery({
    queryKey: ["resources"],
    queryFn: () => api.get<Resource[]>("/api/resources"),
  });
  const { data: roles } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/api/roles"),
  });

  const create = useMutation({
    mutationFn: (body: typeof form) =>
      api.post<Resource>("/api/resources", {
        name: body.name,
        email: body.email || null,
        daily_rate: Number(body.daily_rate),
        role_id: body.role_id ? Number(body.role_id) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resources"] });
      setShowForm(false);
      setForm({ name: "", daily_rate: 0, role_id: "", email: "" });
    },
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  return (
    <div className="p-6">
      <header className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Risorse</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">{data?.length || 0} risorse</p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-lg bg-brand-400 px-4 py-2 text-sm font-medium text-slate-800 dark:text-white hover:bg-brand-500"
        >
          {showForm ? "Annulla" : "+ Nuova risorsa"}
        </button>
      </header>

      {showForm && (
        <Card title="Nuova risorsa" className="mb-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <input
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              placeholder="Nome"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <input
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              placeholder="Email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <input
              type="number"
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              placeholder="Tariffa/gg (€)"
              value={form.daily_rate}
              onChange={(e) => setForm({ ...form, daily_rate: Number(e.target.value) })}
            />
            <select
              className="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:border-slate-600 dark:bg-slate-700 dark:text-slate-800 dark:text-white px-3 py-2 text-sm"
              value={form.role_id}
              onChange={(e) => setForm({ ...form, role_id: e.target.value })}
            >
              <option  value="" className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">(ruolo)</option>
              {roles?.map((r) => (
                <option  key={r.id} value={r.id} className="text-slate-800 dark:text-white bg-white dark:bg-slate-700">
                  {r.name}
                </option>
              ))}
            </select>
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
              <th>Ruolo</th>
              <th>Email</th>
              <th className="text-right">Tariffa/gg</th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((r) => (
              <tr
                key={r.id}
                onClick={() => navigate(`/person/${r.id}`)}
                className="cursor-pointer border-b border-slate-50 hover:bg-brand-50"
              >
                <td className="py-2 font-medium text-brand-700">{r.name}</td>
                <td>{r.role_name || "-"}</td>
                <td className="text-slate-500 dark:text-slate-400">{r.email || "-"}</td>
                <td className="text-right">{fmtEur(r.daily_rate)}</td>
                <td>{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
