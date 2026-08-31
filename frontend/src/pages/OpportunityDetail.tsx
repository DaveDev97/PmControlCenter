import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import { CheckCircle, Clock, AlertCircle, ChevronDown, ChevronRight, Edit2, Save, X } from "lucide-react";
import { api } from "../lib/api";
import type { OpportunityDetail as OpportunityDetailType, DueDiligence } from "../lib/types";
import { Card, Loading, ErrorBox } from "../components/ui";
import { fmtEur } from "../lib/format";

export default function OpportunityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expandedDD, setExpandedDD] = useState<number | null>(null);
  const [editingDD, setEditingDD] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<DueDiligence>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ["opportunity", id],
    queryFn: () => api.get<OpportunityDetailType>(`/api/dashboard/opportunity/${id}`),
    enabled: !!id,
  });

  const updateDDMutation = useMutation({
    mutationFn: async ({ ddId, updates }: { ddId: number; updates: Partial<DueDiligence> }) => {
      return api.put(`/api/due-diligence/${ddId}`, updates);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["opportunity", id] });
      setEditingDD(null);
      setEditForm({});
    },
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const statusIcon = (status: string) => {
    if (status === "completed") return <CheckCircle className="text-green-600 dark:text-green-400" size={18} />;
    if (status === "in_progress") return <Clock className="text-amber-600 dark:text-amber-400" size={18} />;
    if (status === "blocked") return <AlertCircle className="text-red-600 dark:text-red-400" size={18} />;
    return <AlertCircle className="text-slate-400" size={18} />;
  };

  // Calculate DD progress
  const ddStats = data.due_diligences?.reduce(
    (acc, dd) => {
      acc.total++;
      if (dd.status === "completed") acc.completed++;
      if (dd.status === "in_progress") acc.inProgress++;
      if (dd.status === "blocked") acc.blocked++;
      if (dd.is_mandatory) acc.mandatory++;
      return acc;
    },
    { total: 0, completed: 0, inProgress: 0, blocked: 0, mandatory: 0 }
  ) || { total: 0, completed: 0, inProgress: 0, blocked: 0, mandatory: 0 };

  const progressPct = ddStats.total > 0 ? Math.round((ddStats.completed / ddStats.total) * 100) : 0;
  const currentStep = data.due_diligences?.find(dd => dd.status === "in_progress" || dd.status === "pending");

  const startEdit = (dd: DueDiligence) => {
    setEditingDD(dd.id);
    setEditForm({
      status: dd.status,
      assigned_to: dd.assigned_to || "",
      due_date: dd.due_date || "",
      completed_date: dd.completed_date || "",
      approver: dd.approver || "",
      approval_date: dd.approval_date || "",
      notes: dd.notes || "",
    });
  };

  const cancelEdit = () => {
    setEditingDD(null);
    setEditForm({});
  };

  const saveEdit = (ddId: number) => {
    updateDDMutation.mutate({ ddId, updates: editForm });
  };

  return (
    <div className="p-6">
      <button onClick={() => navigate(-1)} className="mb-3 text-sm text-brand-600 hover:underline dark:text-brand-400">
        ← Indietro
      </button>

      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{data.name}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {data.opp_id_mms} · {data.stage} · {fmtEur(data.estimated_value)}
        </p>
      </header>

      {/* Opportunity Info */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card title="Valore Stimato">
          <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{fmtEur(data.estimated_value)}</div>
        </Card>
        <Card title="Probabilità">
          <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">
            {Math.round(data.probability * 100)}%
          </div>
        </Card>
        <Card title="Legal Entity">
          <div className="text-lg font-semibold text-slate-800 dark:text-slate-100">{data.legal_entity || "-"}</div>
        </Card>
        <Card title="Anno Fiscale">
          <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{data.fiscal_year || "-"}</div>
        </Card>
      </div>

      {data.description && (
        <Card title="Descrizione" className="mb-6">
          <p className="text-sm text-slate-600 dark:text-slate-300">{data.description}</p>
        </Card>
      )}

      {/* Invoices - MOVED ABOVE DD */}
      {data.invoices && data.invoices.length > 0 && (
        <Card title="Fatturazione" className="mb-6">
          <div className="space-y-2">
            {data.invoices.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center justify-between rounded-lg border border-slate-100 p-3 dark:border-slate-800"
              >
                <div>
                  <div className="font-medium text-slate-700 dark:text-slate-200">{inv.invoice_number}</div>
                  <div className="text-xs text-slate-400">
                    Emessa: {inv.invoice_date} · Pagata: {inv.payment_date || "In attesa"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-slate-800 dark:text-slate-100">{fmtEur(inv.amount)}</div>
                  <span
                    className={`text-xs font-medium ${
                      inv.status === "pagata"
                        ? "text-green-600 dark:text-green-400"
                        : "text-amber-600 dark:text-amber-400"
                    }`}
                  >
                    {inv.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Due Diligence Summary */}
      {data.due_diligences && data.due_diligences.length > 0 && (
        <Card title="Due Diligence Progress" className="mb-6">
          <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-5">
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Totale Steps</div>
              <div className="text-2xl font-bold text-slate-800 dark:text-slate-100">{ddStats.total}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Completati</div>
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">{ddStats.completed}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">In Corso</div>
              <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">{ddStats.inProgress}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Bloccati</div>
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">{ddStats.blocked}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Progress</div>
              <div className="text-2xl font-bold text-brand-600 dark:text-brand-400">{progressPct}%</div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-4 h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <div
              className="h-full bg-brand-600 dark:bg-brand-500 transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {/* Current Step */}
          {currentStep && (
            <div className="rounded-lg border border-brand-200 bg-brand-50 p-3 dark:border-brand-800 dark:bg-brand-950">
              <div className="text-xs font-medium uppercase tracking-wide text-brand-600 dark:text-brand-400">
                Step Corrente
              </div>
              <div className="mt-1 font-semibold text-slate-800 dark:text-slate-100">{currentStep.milestone}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Scadenza: {currentStep.due_date || "Non definita"} · Assegnato a: {currentStep.assigned_to || "-"}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* DD Activities - Expandable & Editable */}
      {data.due_diligences && data.due_diligences.length > 0 && (
        <Card title="Attività Due Diligence" className="mb-6">
          <div className="space-y-2">
            {data.due_diligences
              .sort((a, b) => a.step_order - b.step_order)
              .map((dd) => (
                <div key={dd.id} className="rounded-lg border border-slate-200 dark:border-slate-700">
                  <button
                    onClick={() => setExpandedDD(expandedDD === dd.id ? null : dd.id)}
                    className="flex w-full items-center gap-3 p-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    {expandedDD === dd.id ? (
                      <ChevronDown size={18} className="text-slate-400" />
                    ) : (
                      <ChevronRight size={18} className="text-slate-400" />
                    )}
                    {statusIcon(dd.status)}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
                          {dd.step_order}.
                        </span>
                        <span className="font-medium text-slate-700 dark:text-slate-200">{dd.milestone}</span>
                        {dd.is_mandatory && (
                          <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900 dark:text-red-300">
                            Obbligatorio
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-400 dark:text-slate-500">
                        {dd.due_date ? `Scadenza: ${dd.due_date}` : "Nessuna scadenza"}
                      </div>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        dd.status === "completed"
                          ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                          : dd.status === "in_progress"
                          ? "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                          : dd.status === "blocked"
                          ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                          : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                      }`}
                    >
                      {dd.status}
                    </span>
                  </button>

                  {/* Expanded Details - Editable */}
                  {expandedDD === dd.id && (
                    <div className="border-t border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900">
                      {editingDD === dd.id ? (
                        // Edit Mode
                        <div className="space-y-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                                Status
                              </label>
                              <select
                                value={editForm.status || ""}
                                onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                              >
                                <option value="pending">Pending</option>
                                <option value="in_progress">In Progress</option>
                                <option value="completed">Completed</option>
                                <option value="blocked">Blocked</option>
                                <option value="skipped">Skipped</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                                Assegnato a
                              </label>
                              <input
                                type="text"
                                value={editForm.assigned_to || ""}
                                onChange={(e) => setEditForm({ ...editForm, assigned_to: e.target.value })}
                                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                              />
                            </div>

                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                                Scadenza
                              </label>
                              <input
                                type="date"
                                value={editForm.due_date || ""}
                                onChange={(e) => setEditForm({ ...editForm, due_date: e.target.value })}
                                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                              />
                            </div>

                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                                Data Completamento
                              </label>
                              <input
                                type="date"
                                value={editForm.completed_date || ""}
                                onChange={(e) => setEditForm({ ...editForm, completed_date: e.target.value })}
                                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                              />
                            </div>

                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                                Approvatore
                              </label>
                              <input
                                type="text"
                                value={editForm.approver || ""}
                                onChange={(e) => setEditForm({ ...editForm, approver: e.target.value })}
                                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                              />
                            </div>

                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                                Data Approvazione
                              </label>
                              <input
                                type="date"
                                value={editForm.approval_date || ""}
                                onChange={(e) => setEditForm({ ...editForm, approval_date: e.target.value })}
                                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                              />
                            </div>
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                              Note
                            </label>
                            <textarea
                              value={editForm.notes || ""}
                              onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                              rows={3}
                              className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                            />
                          </div>

                          <div className="flex gap-2">
                            <button
                              onClick={() => saveEdit(dd.id)}
                              disabled={updateDDMutation.isPending}
                              className="flex items-center gap-2 rounded bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                            >
                              <Save size={16} />
                              {updateDDMutation.isPending ? "Salvataggio..." : "Salva"}
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="flex items-center gap-2 rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                              <X size={16} />
                              Annulla
                            </button>
                          </div>
                        </div>
                      ) : (
                        // View Mode
                        <>
                          <div className="mb-3 flex justify-end">
                            <button
                              onClick={() => startEdit(dd)}
                              className="flex items-center gap-1 text-xs text-brand-600 hover:underline dark:text-brand-400"
                            >
                              <Edit2 size={14} />
                              Modifica
                            </button>
                          </div>
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <div className="font-medium text-slate-500 dark:text-slate-400">Assegnato a</div>
                              <div className="text-slate-800 dark:text-slate-100">{dd.assigned_to || "-"}</div>
                            </div>
                            <div>
                              <div className="font-medium text-slate-500 dark:text-slate-400">Dipendenza</div>
                              <div className="text-slate-800 dark:text-slate-100">
                                {dd.depends_on_step ? `Step #${dd.depends_on_step}` : "Nessuna"}
                              </div>
                            </div>
                            {dd.completed_date && (
                              <div>
                                <div className="font-medium text-slate-500 dark:text-slate-400">Completato</div>
                                <div className="text-slate-800 dark:text-slate-100">{dd.completed_date}</div>
                              </div>
                            )}
                            {dd.approver && (
                              <div>
                                <div className="font-medium text-slate-500 dark:text-slate-400">Approvato da</div>
                                <div className="text-slate-800 dark:text-slate-100">{dd.approver}</div>
                              </div>
                            )}
                            {dd.approval_date && (
                              <div>
                                <div className="font-medium text-slate-500 dark:text-slate-400">Data Approvazione</div>
                                <div className="text-slate-800 dark:text-slate-100">{dd.approval_date}</div>
                              </div>
                            )}
                          </div>
                          {dd.notes && (
                            <div className="mt-3">
                              <div className="font-medium text-slate-500 dark:text-slate-400">Note</div>
                              <div className="text-sm text-slate-600 dark:text-slate-300">{dd.notes}</div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
          </div>
        </Card>
      )}

      {data.notes && (
        <Card title="Note Opportunità">
          <p className="text-sm text-slate-600 dark:text-slate-300">{data.notes}</p>
        </Card>
      )}
    </div>
  );
}
