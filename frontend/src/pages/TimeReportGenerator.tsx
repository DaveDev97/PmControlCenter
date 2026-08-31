import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Eye, Plus, Trash2, AlertCircle, Upload } from "lucide-react";
import * as XLSX from "xlsx";
import { api } from "../lib/api";
import type { Resource, TimeEntry, Contract, Project } from "../lib/types";
import { Card, Loading } from "../components/ui";

const MONTHS = [
  "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
  "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
];

interface WBSOption {
  wbs: string;
  contractName: string;
  budgetUsed: number;
  budgetTotal: number;
  budgetAvailable: number;
}

interface ValidationError {
  entryId: number | string;
  field: string;
  message: string;
}

export default function TimeReportGenerator() {
  const [selectedMonth, setSelectedMonth] = useState("Luglio");
  const [selectedQuindicina, setSelectedQuindicina] = useState<"1" | "2">("2");
  const [selectedResources, setSelectedResources] = useState<number[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<(TimeEntry & { tempId?: string })[]>([]);
  const [wbsOptions, setWbsOptions] = useState<WBSOption[]>([]);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [isDownloading, setIsDownloading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [isUploading, setIsUploading] = useState(false);

  const period = `${selectedQuindicina}Q-${selectedMonth}`;

  const { data: resources, isLoading } = useQuery({
    queryKey: ["resources"],
    queryFn: () => api.get<Resource[]>("/api/resources"),
  });

  const { data: contracts } = useQuery({
    queryKey: ["contracts"],
    queryFn: () => api.get<Contract[]>("/api/contracts"),
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.get<Project[]>("/api/projects"),
  });

  // Build WBS options with budget info
  useEffect(() => {
    if (contracts && projects) {
      const options: WBSOption[] = [];

      // Add contract WBS
      contracts.forEach(c => {
        if (c.wbs_l1) {
          options.push({
            wbs: c.wbs_l1,
            contractName: c.name,
            budgetTotal: 100000, // Mock: would come from financials
            budgetUsed: 45000,   // Mock: calculated from allocations
            budgetAvailable: 55000,
          });
        }
      });

      // Add project WBS
      projects.forEach(p => {
        if (p.wbs) {
          const contract = contracts.find(c => c.id === p.contract_id);
          options.push({
            wbs: p.wbs,
            contractName: `${contract?.name || 'Unknown'} / ${p.name}`,
            budgetTotal: p.budget || 0,
            budgetUsed: 0, // Mock
            budgetAvailable: p.budget || 0,
          });
        }
      });

      // Add common non-WBS entries
      options.push(
        { wbs: "Meeting Time", contractName: "Non Chargeable", budgetTotal: 0, budgetUsed: 0, budgetAvailable: 0 },
        { wbs: "Permesso", contractName: "Non Chargeable", budgetTotal: 0, budgetUsed: 0, budgetAvailable: 0 },
        { wbs: "Other Client", contractName: "Non Chargeable", budgetTotal: 0, budgetUsed: 0, budgetAvailable: 0 },
      );

      setWbsOptions(options);
    }
  }, [contracts, projects]);

  const handlePreview = async () => {
    try {
      const params = new URLSearchParams({ period });
      if (selectedResources.length > 0) {
        params.append("resource_ids", selectedResources.join(","));
      }

      const entries = await api.get<TimeEntry[]>(`/api/time-reports/entries?${params}`);

      // Add empty rows for selected resources that have no existing entries
      const entriesWithEmpty: (TimeEntry & { tempId?: string })[] = [...entries];
      const resourcesToShow = selectedResources.length > 0 ? selectedResources : resources?.map(r => r.id) || [];

      resourcesToShow.forEach(resId => {
        const hasEntries = entries.some(e => e.resource_id === resId);
        if (!hasEntries) {
          const res = resources?.find(r => r.id === resId);
          if (res) {
            // Add empty placeholder entry for this resource
            entriesWithEmpty.push({
              id: 0,
              tempId: `temp-${resId}-${Date.now()}`,
              resource_id: resId,
              resource_name: res.name,
              project_id: null,
              period,
              hours: 0,
              wbs: wbsOptions[0]?.wbs || "",
              type: "Chargeable",
              week_ending: null,
            });
          }
        }
      });

      // Sort by resource_id for better grouping
      entriesWithEmpty.sort((a, b) => a.resource_id - b.resource_id);

      setPreviewData(entriesWithEmpty);
      setShowPreview(true);
      validateEntries(entriesWithEmpty);
    } catch (error) {
      console.error("Preview error:", error);
      alert("Errore nel caricamento dell'anteprima");
    }
  };

  const addNewRow = () => {
    const tempId = `temp-${Date.now()}`;
    const newEntry: TimeEntry & { tempId: string } = {
      id: 0,
      tempId,
      resource_id: selectedResources[0] || (resources?.[0]?.id || 0),
      resource_name: resources?.find(r => r.id === selectedResources[0])?.name || "",
      project_id: null,
      period,
      hours: 0,
      wbs: wbsOptions[0]?.wbs || "",
      type: "Chargeable",
      week_ending: null,
    };
    setPreviewData([...previewData, newEntry]);
  };

  const removeRow = (id: number | string) => {
    setPreviewData(prev => prev.filter(e => (e.tempId || e.id) !== id));
  };

  const updateEntry = (id: number | string, field: keyof TimeEntry, value: any) => {
    setPreviewData(prev => {
      const updated = prev.map(e =>
        (e.tempId || e.id) === id ? { ...e, [field]: value } : e
      );
      validateEntries(updated);
      return updated;
    });
  };

  const validateEntries = (entries: (TimeEntry & { tempId?: string })[]) => {
    const errors: ValidationError[] = [];

    // Group by resource to check chargeability
    const byResource: Record<string, (TimeEntry & { tempId?: string })[]> = {};
    entries.forEach(e => {
      const key = e.resource_name || `res-${e.resource_id}`;
      if (!byResource[key]) byResource[key] = [];
      byResource[key].push(e);
    });

    Object.entries(byResource).forEach(([resName, resEntries]) => {
      const totalHours = resEntries.reduce((sum, e) => sum + e.hours, 0);
      const chargeableHours = resEntries.filter(e => e.type === "Chargeable").reduce((sum, e) => sum + e.hours, 0);
      const chargeability = totalHours > 0 ? chargeableHours / totalHours : 0;

      // Check chargeability threshold (< 70% is warning)
      if (chargeability < 0.7 && totalHours > 0) {
        resEntries.forEach(e => {
          errors.push({
            entryId: e.tempId || e.id,
            field: "chargeability",
            message: `Chargeability bassa per ${resName}: ${Math.round(chargeability * 100)}% (< 70%)`,
          });
        });
      }
    });

    // Check WBS budget availability
    entries.forEach(e => {
      if (e.type === "Chargeable") {
        const wbsInfo = wbsOptions.find(w => w.wbs === e.wbs);
        if (wbsInfo && wbsInfo.budgetAvailable < e.hours * 50) {  // Assume €50/hour cost
          errors.push({
            entryId: e.tempId || e.id,
            field: "wbs",
            message: `Budget insufficiente su WBS ${e.wbs}: disponibili €${wbsInfo.budgetAvailable}`,
          });
        }
      }
    });

    setValidationErrors(errors);
  };

  const hasError = (entryId: number | string, field?: string) => {
    return validationErrors.some(e => e.entryId === entryId && (!field || e.field === field));
  };

  const getErrorMessage = (entryId: number | string) => {
    const errors = validationErrors.filter(e => e.entryId === entryId);
    return errors.map(e => e.message).join("; ");
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/time-upload/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const result = await response.json();
      setUploadResult(result);

      // Refresh preview if same period
      if (showPreview) {
        handlePreview();
      }
    } catch (error: any) {
      alert(`Errore upload: ${error.message}`);
    } finally {
      setIsUploading(false);
      // Reset file input
      event.target.value = '';
    }
  };

  const downloadReportWithEdits = () => {
    setIsDownloading(true);
    try {
      const worksheet = XLSX.utils.json_to_sheet(
        previewData.map(e => ({
          TR: e.period,
          "Resource ID": e.resource_name?.split("@")[0] || e.resource_name,
          Ore: e.hours,
          WBS: e.wbs,
          Tipologia: e.type,
        }))
      );

      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "CHG Report");
      XLSX.writeFile(workbook, `CHG_${period}.xlsx`);
    } catch (error) {
      console.error("Download error:", error);
      alert("Errore durante il download del report");
    } finally {
      setIsDownloading(false);
    }
  };

  if (isLoading) return <Loading />;

  return (
    <div className="p-6">
      <h1 className="mb-5 text-2xl font-bold text-slate-800 dark:text-slate-100">Time Report Generator</h1>

      {/* Upload Section */}
      <Card title="Carica Time Report" className="mb-6">
        <div className="space-y-4">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Carica un file Excel (formato CHG) con le ore dichiarate. Colonne attese: <strong>TR, Resource ID, Ore, WBS, Tipologia</strong>
          </p>

          <div className="flex items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 px-6 py-3 text-sm font-medium text-slate-700 dark:text-slate-200 transition hover:border-brand-400 hover:bg-brand-50 dark:hover:bg-slate-700">
              <Upload size={18} />
              <span>{isUploading ? 'Caricamento...' : 'Seleziona File Excel'}</span>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileUpload}
                className="hidden"
                disabled={isUploading}
              />
            </label>

            {uploadResult && (
              <div className={`rounded-lg border px-4 py-2 text-sm ${
                uploadResult.errors?.length > 0
                  ? 'border-amber-300 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200'
                  : 'border-green-300 bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200'
              }`}>
                <p className="font-semibold">
                  ✓ {uploadResult.inserted} inserite, {uploadResult.updated} aggiornate
                </p>
                {uploadResult.errors?.length > 0 && (
                  <p className="text-xs mt-1">{uploadResult.errors.length} errori (vedi console)</p>
                )}
              </div>
            )}
          </div>

          {uploadResult?.errors?.length > 0 && (
            <details className="text-xs text-slate-600 dark:text-slate-400">
              <summary className="cursor-pointer font-medium">Mostra errori ({uploadResult.errors.length})</summary>
              <ul className="mt-2 list-disc pl-5 space-y-1">
                {uploadResult.errors.slice(0, 10).map((err: string, i: number) => (
                  <li key={i}>{err}</li>
                ))}
                {uploadResult.errors.length > 10 && (
                  <li className="italic">... e altri {uploadResult.errors.length - 10} errori</li>
                )}
              </ul>
            </details>
          )}
        </div>
      </Card>

      <Card title="Configurazione Report" className="mb-6">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-200">Mese</label>
              <select
                className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-white px-3 py-2"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
              >
                {MONTHS.map(m => <option  key={m} value={m} className="bg-white dark:bg-slate-700 text-slate-800 dark:text-white">{m}</option>)}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-200">Quindicina</label>
              <select
                className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-white px-3 py-2"
                value={selectedQuindicina}
                onChange={(e) => setSelectedQuindicina(e.target.value as "1" | "2")}
              >
                <option  value="1" className="bg-white dark:bg-slate-700 text-slate-800 dark:text-white">1ª Quindicina (1-15)</option>
                <option  value="2" className="bg-white dark:bg-slate-700 text-slate-800 dark:text-white">2ª Quindicina (16-31)</option>
              </select>
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm text-slate-600 dark:text-slate-300">
              Periodo: <span className="font-semibold text-brand-600">{period}</span>
            </p>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Risorse (lascia vuoto per tutte)
              </label>
              <button
                onClick={() => {
                  if (selectedResources.length === resources?.length) {
                    setSelectedResources([]);
                  } else {
                    setSelectedResources(resources?.map(r => r.id) || []);
                  }
                }}
                className="text-xs text-brand-600 hover:underline"
              >
                {selectedResources.length === resources?.length ? "Deseleziona tutti" : "Seleziona tutti"}
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2">
              {resources?.map((r) => (
                <label key={r.id} className="flex items-center gap-2 px-2 py-1 hover:bg-slate-50 dark:hover:bg-slate-700">
                  <input
                    type="checkbox"
                    checked={selectedResources.includes(r.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedResources([...selectedResources, r.id]);
                      } else {
                        setSelectedResources(selectedResources.filter((id) => id !== r.id));
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300 bg-white text-brand-600 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-700"
                  />
                  <span className="text-sm text-slate-700 dark:text-slate-200">{r.name}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            onClick={handlePreview}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-white hover:bg-brand-700"
          >
            <Eye size={18} />
            Anteprima
          </button>
        </div>
      </Card>

      {showPreview && (
        <Card title="Anteprima Modificabile" className="mb-6">
          {validationErrors.length > 0 && (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="flex items-start gap-2 text-sm text-amber-800">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Attenzione: {validationErrors.length} problemi rilevati</p>
                  <ul className="mt-1 list-disc pl-5 text-xs">
                    {Array.from(new Set(validationErrors.map(e => e.message))).map((msg, i) => (
                      <li key={i}>{msg}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 dark:border-slate-700 text-left text-xs uppercase text-slate-400">
                <tr>
                  <th className="py-2">TR</th>
                  <th>Resource</th>
                  <th className="text-right">Ore</th>
                  <th>WBS</th>
                  <th>Tipologia</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {previewData.map((entry, index) => {
                  const rowId = entry.tempId || entry.id;
                  const hasRowError = hasError(rowId);
                  const errorMsg = getErrorMessage(rowId);

                  // Group by resource for alternating background
                  const prevEntry = index > 0 ? previewData[index - 1] : null;
                  const isNewResource = !prevEntry || prevEntry.resource_id !== entry.resource_id;
                  const resourceIndex = previewData
                    .slice(0, index + 1)
                    .filter((e, i, arr) => i === 0 || arr[i - 1].resource_id !== e.resource_id)
                    .length - 1;
                  const bgColor = hasRowError
                    ? 'bg-red-50 dark:bg-red-900/20'
                    : resourceIndex % 2 === 0
                      ? 'bg-white dark:bg-slate-800'
                      : 'bg-slate-50 dark:bg-slate-900';

                  return (
                    <tr
                      key={rowId}
                      className={`border-b border-slate-200 dark:border-slate-700 ${bgColor} ${isNewResource ? 'border-t-2 border-t-slate-300' : ''}`}
                      title={hasRowError ? errorMsg : ''}
                    >
                      <td className="py-2 font-medium text-slate-700 dark:text-slate-200">{entry.period}</td>
                      <td className="text-slate-600 dark:text-slate-300">
                        <select
                          value={entry.resource_id}
                          onChange={(e) => {
                            const resId = parseInt(e.target.value);
                            const res = resources?.find(r => r.id === resId);
                            updateEntry(rowId, "resource_id", resId);
                            updateEntry(rowId, "resource_name", res?.name || "");
                          }}
                          className="w-full rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-white px-2 py-1 text-sm"
                        >
                          {resources?.map(r => (
                            <option  key={r.id} value={r.id} className="bg-white dark:bg-slate-700 text-slate-800 dark:text-white">{r.name}</option>
                          ))}
                        </select>
                      </td>
                      <td className="text-right">
                        <input
                          type="number"
                          step="0.1"
                          value={entry.hours}
                          onChange={(e) => updateEntry(rowId, "hours", parseFloat(e.target.value) || 0)}
                          className={`w-20 rounded border px-2 py-1 text-right bg-white dark:bg-slate-700 text-slate-800 dark:text-white ${
                            hasError(rowId, "hours") ? 'border-red-500' : 'border-slate-300 dark:border-slate-600'
                          }`}
                        />
                      </td>
                      <td>
                        <select
                          value={entry.wbs}
                          onChange={(e) => updateEntry(rowId, "wbs", e.target.value)}
                          className={`w-full max-w-xs rounded border px-2 py-1 text-sm bg-white dark:bg-slate-700 text-slate-800 dark:text-white ${
                            hasError(rowId, "wbs") ? 'border-red-500' : 'border-slate-300 dark:border-slate-600'
                          }`}
                        >
                          {wbsOptions.map(w => (
                            <option  key={w.wbs} value={w.wbs} className="bg-white dark:bg-slate-700 text-slate-800 dark:text-white">
                              {w.wbs} ({w.contractName}) {w.budgetTotal > 0 ? `- €${w.budgetAvailable} disponibili` : ''}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <select
                          value={entry.type}
                          onChange={(e) => updateEntry(rowId, "type", e.target.value)}
                          className="rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-white px-2 py-1 text-sm"
                        >
                          <option>Chargeable</option>
                          <option>Not Chargeable</option>
                        </select>
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() => removeRow(rowId)}
                          className="text-red-600 hover:text-red-800"
                          title="Rimuovi riga"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <button
              onClick={addNewRow}
              className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-white bg-white px-3 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              <Plus size={16} />
              Aggiungi Riga
            </button>

            <div className="flex gap-2">
              <button
                onClick={() => setShowPreview(false)}
                className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-white px-4 py-2 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                Annulla
              </button>
              <button
                onClick={downloadReportWithEdits}
                disabled={isDownloading || validationErrors.length > 0}
                className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-white hover:bg-brand-700 disabled:opacity-50"
                title={validationErrors.length > 0 ? "Risolvi gli errori prima di scaricare" : ""}
              >
                <Download size={18} />
                {isDownloading ? "Download..." : "Scarica Excel"}
              </button>
            </div>
          </div>
        </Card>
      )}

      <Card title="Info">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Il report generato seguirà il formato CHG con le colonne: TR (periodo), Resource ID (email),
          Ore, WBS, Tipologia (Chargeable/Not Chargeable).
          <br /><br />
          <strong>Quindicina:</strong> 1Q = prima quindicina (1-15), 2Q = seconda quindicina (16-31).
          <br /><br />
          <strong>Validazioni:</strong> Le righe in rosso indicano problemi (budget insufficiente, chargeability bassa).
        </p>
      </Card>
    </div>
  );
}
