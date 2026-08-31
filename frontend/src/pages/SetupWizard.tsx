import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  FolderOpen,
  CheckCircle2,
  XCircle,
  Loader2,
  FileSpreadsheet,
  Rocket,
  ArrowRight,
  ArrowLeft,
} from "lucide-react";
import {
  settingsApi,
  pickFolder,
  isElectron,
  type FolderValidation,
  type ConfigureResult,
} from "../lib/settings";

const REQUIRED = ["security_financials.xlsx"];
const OPTIONAL: string[] = [];

type Step = 0 | 1 | 2 | 3;

export default function SetupWizard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>(0);
  const [folder, setFolder] = useState("");
  const [validation, setValidation] = useState<FolderValidation | null>(null);
  const [validating, setValidating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ConfigureResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleBrowse() {
    const picked = await pickFolder();
    if (picked) {
      setFolder(picked);
      setValidation(null);
    }
  }

  async function handleValidate() {
    if (!folder) return;
    setValidating(true);
    setError(null);
    try {
      const v = await settingsApi.validate(folder);
      setValidation(v);
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setValidating(false);
    }
  }

  async function handleLoad() {
    setLoading(true);
    setError(null);
    setStep(3);
    try {
      const r = await settingsApi.configure(folder);
      setResult(r);
      await queryClient.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStep(2);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6 dark:bg-slate-900">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-xl dark:bg-slate-800">
        <Stepper step={step} />

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
            <XCircle size={18} /> {error}
          </div>
        )}

        {/* Step 0 — Welcome */}
        {step === 0 && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <Rocket className="text-brand-500" size={28} />
              <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
                {t("setup.welcome.title")}
              </h1>
            </div>
            <p className="text-slate-600 dark:text-slate-300">{t("setup.welcome.body")}</p>
            <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-700/50">
              <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                {t("setup.welcome.requirements")}
              </p>
              <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
                {REQUIRED.map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <FileSpreadsheet size={14} className="text-brand-500" /> {f}
                  </li>
                ))}
                {OPTIONAL.map((f) => (
                  <li key={f} className="flex items-center gap-2 opacity-70">
                    <FileSpreadsheet size={14} /> {f} ({t("setup.validation.optional")})
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex justify-end">
              <PrimaryButton onClick={() => setStep(1)}>
                {t("setup.welcome.start")} <ArrowRight size={16} />
              </PrimaryButton>
            </div>
          </div>
        )}

        {/* Step 1 — Folder picker */}
        {step === 1 && (
          <div className="space-y-5">
            <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
              {t("setup.folder.title")}
            </h1>
            <p className="text-slate-600 dark:text-slate-300">{t("setup.folder.body")}</p>
            <div className="flex gap-2">
              <input
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder={t("setup.folder.placeholder")}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white"
              />
              {isElectron() && (
                <button
                  onClick={handleBrowse}
                  className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  <FolderOpen size={16} /> {t("setup.folder.browse")}
                </button>
              )}
            </div>
            <div className="flex justify-between">
              <SecondaryButton onClick={() => setStep(0)}>
                <ArrowLeft size={16} /> {t("common.back")}
              </SecondaryButton>
              <PrimaryButton onClick={handleValidate} disabled={!folder || validating}>
                {validating ? <Loader2 className="animate-spin" size={16} /> : null}
                {t("setup.folder.validate")} <ArrowRight size={16} />
              </PrimaryButton>
            </div>
          </div>
        )}

        {/* Step 2 — Validation */}
        {step === 2 && validation && (
          <div className="space-y-5">
            <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
              {t("setup.validation.title")}
            </h1>
            <div
              className={`flex items-center gap-2 rounded-lg px-4 py-3 text-sm ${
                validation.valid
                  ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                  : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300"
              }`}
            >
              {validation.valid ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
              {validation.valid ? t("setup.validation.valid") : t("setup.validation.invalid")}
            </div>
            <FileList label={t("setup.validation.found")} files={validation.found} ok />
            {validation.missing.length > 0 && (
              <FileList label={t("setup.validation.missing")} files={validation.missing} />
            )}
            {validation.optional.length > 0 && (
              <FileList label={t("setup.validation.optional")} files={validation.optional} ok />
            )}
            <div className="flex justify-between">
              <SecondaryButton onClick={() => setStep(1)}>
                <ArrowLeft size={16} /> {t("common.back")}
              </SecondaryButton>
              <PrimaryButton onClick={handleLoad} disabled={!validation.valid}>
                {t("common.next")} <ArrowRight size={16} />
              </PrimaryButton>
            </div>
          </div>
        )}

        {/* Step 3 — Loading / Complete */}
        {step === 3 && (
          <div className="space-y-5">
            {loading || !result ? (
              <div className="flex flex-col items-center gap-4 py-10 text-center">
                <Loader2 className="animate-spin text-brand-500" size={40} />
                <h1 className="text-xl font-bold text-slate-800 dark:text-white">
                  {t("setup.loading.title")}
                </h1>
                <p className="text-slate-600 dark:text-slate-300">{t("setup.loading.body")}</p>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="text-green-500" size={28} />
                  <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
                    {t("setup.complete.title")}
                  </h1>
                </div>
                <p className="text-slate-600 dark:text-slate-300">{t("setup.complete.body")}</p>
                <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-700/50">
                  <p className="mb-3 text-sm font-medium text-slate-700 dark:text-slate-200">
                    {t("setup.complete.summary")}
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    <CountTile n={result.counts.contracts} label={t("setup.counts.contracts")} />
                    <CountTile n={result.counts.resources} label={t("setup.counts.resources")} />
                    <CountTile n={result.counts.opportunities} label={t("setup.counts.opportunities")} />
                    <CountTile n={result.counts.financials} label={t("setup.counts.financials")} />
                    <CountTile n={result.counts.allocations} label={t("setup.counts.allocations")} />
                    <CountTile n={result.counts.clients} label={t("setup.counts.clients")} />
                  </div>
                </div>
                <div className="flex justify-end">
                  <PrimaryButton onClick={() => navigate("/")}>
                    {t("setup.complete.goToDashboard")} <ArrowRight size={16} />
                  </PrimaryButton>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Stepper({ step }: { step: Step }) {
  return (
    <div className="mb-8 flex items-center justify-center gap-2">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className={`h-2 rounded-full transition-all ${
            i === step ? "w-8 bg-brand-500" : i < step ? "w-8 bg-brand-300" : "w-2 bg-slate-300 dark:bg-slate-600"
          }`}
        />
      ))}
    </div>
  );
}

function FileList({ label, files, ok }: { label: string; files: string[]; ok?: boolean }) {
  if (!files.length) return null;
  return (
    <div>
      <p className="mb-1 text-sm font-medium text-slate-700 dark:text-slate-200">{label}</p>
      <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
        {files.map((f) => (
          <li key={f} className="flex items-center gap-2">
            {ok ? (
              <CheckCircle2 size={14} className="text-green-500" />
            ) : (
              <XCircle size={14} className="text-red-500" />
            )}
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CountTile({ n, label }: { n: number; label: string }) {
  return (
    <div className="rounded-lg bg-white p-3 text-center shadow-sm dark:bg-slate-800">
      <div className="text-2xl font-bold text-brand-600 dark:text-brand-400">{n}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

function PrimaryButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2 text-sm font-medium text-white shadow transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function SecondaryButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className="flex items-center gap-2 rounded-lg border border-slate-300 px-5 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
    >
      {children}
    </button>
  );
}
