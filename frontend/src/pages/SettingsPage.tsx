import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { FolderOpen, RefreshCw, Save, Check, Loader2 } from "lucide-react";
import { settingsApi, pickFolder, isElectron, type AppSettings } from "../lib/settings";
import { setLanguage, type Language } from "../lib/i18n";

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });

  const [draft, setDraft] = useState<Partial<AppSettings>>({});
  const [folder, setFolder] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !data) {
    return <div className="p-8 text-slate-500">{t("common.loading")}</div>;
  }

  const current = { ...data, ...draft, ...(folder !== null ? { data_folder: folder } : {}) };

  function set<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
    setSaved(false);
  }

  async function handleBrowse() {
    const picked = await pickFolder();
    if (picked) {
      setFolder(picked);
      setSaved(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const body: Partial<AppSettings> = { ...draft };
      if (folder !== null && folder !== data!.data_folder) body.data_folder = folder;
      const updated = await settingsApi.update(body);
      queryClient.setQueryData(["settings"], updated);
      if (updated.language) setLanguage(updated.language as Language);
      if (body.data_folder) await queryClient.invalidateQueries();
      setDraft({});
      setFolder(null);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleReload() {
    setReloading(true);
    setError(null);
    try {
      await settingsApi.refresh();
      await queryClient.invalidateQueries();
      queryClient.setQueryData(["settings"], await settingsApi.get());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReloading(false);
    }
  }

  const lastSync = current.last_sync
    ? new Date(current.last_sync).toLocaleString(i18n.language)
    : t("settings.never");

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-bold text-slate-800 dark:text-white">
        {t("settings.title")}
      </h1>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Data folder */}
        <Section title={t("settings.dataFolder")} help={t("settings.dataFolderHelp")}>
          <div className="flex gap-2">
            <input
              value={current.data_folder ?? ""}
              onChange={(e) => setFolder(e.target.value)}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white"
            />
            {isElectron() && (
              <button
                onClick={handleBrowse}
                className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                <FolderOpen size={16} /> {t("settings.change")}
              </button>
            )}
          </div>
          <div className="mt-2 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span>
              {t("settings.lastSync")}: {lastSync}
            </span>
            <button
              onClick={handleReload}
              disabled={reloading || !current.data_folder}
              className="flex items-center gap-1 rounded px-2 py-1 text-brand-600 hover:bg-brand-50 disabled:opacity-50 dark:text-brand-400 dark:hover:bg-slate-700"
            >
              {reloading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              {reloading ? t("settings.reloading") : t("settings.reloadData")}
            </button>
          </div>
        </Section>

        {/* Language */}
        <Section title={t("settings.language")}>
          <div className="flex gap-2">
            {(["it", "en"] as const).map((lng) => (
              <button
                key={lng}
                onClick={() => set("language", lng)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                  current.language === lng
                    ? "border-brand-500 bg-brand-500 text-white"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                {lng === "it" ? "🇮🇹 Italiano" : "🇬🇧 English"}
              </button>
            ))}
          </div>
        </Section>

        {/* Theme */}
        <Section title={t("settings.theme")}>
          <div className="flex gap-2">
            {(["light", "dark", "auto"] as const).map((th) => (
              <button
                key={th}
                onClick={() => set("theme", th)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                  current.theme === th
                    ? "border-brand-500 bg-brand-500 text-white"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                {t(`settings.theme${th.charAt(0).toUpperCase() + th.slice(1)}`)}
              </button>
            ))}
          </div>
        </Section>

        {/* Auto refresh */}
        <Section title={t("settings.autoRefresh")} help={t("settings.autoRefreshHelp")}>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              value={current.auto_refresh_minutes}
              onChange={(e) => set("auto_refresh_minutes", Number(e.target.value))}
              className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-white"
            />
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {t("settings.minutes")}
            </span>
          </div>
        </Section>

        {/* AI chat model (Claude Code) */}
        <Section title={t("settings.chatModel")} help={t("settings.chatModelHelp")}>
          <div className="flex flex-wrap gap-2">
            {[
              { v: "", label: t("settings.modelDefault") },
              { v: "opus", label: "Opus" },
              { v: "sonnet", label: "Sonnet" },
              { v: "haiku", label: "Haiku" },
            ].map((m) => (
              <button
                key={m.v || "default"}
                onClick={() => set("chat_model", m.v)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                  (current.chat_model || "") === m.v
                    ? "border-brand-500 bg-brand-500 text-white"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </Section>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2 text-sm font-medium text-white shadow transition hover:bg-brand-600 disabled:opacity-50"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {t("common.save")}
          </button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
              <Check size={16} /> {t("settings.saved")}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  help,
  children,
}: {
  title: string;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
      <h2 className="mb-1 text-sm font-semibold text-slate-800 dark:text-white">{title}</h2>
      {help && <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">{help}</p>}
      {children}
    </div>
  );
}
