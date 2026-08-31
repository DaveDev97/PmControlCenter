// Settings & data-management API client + Electron IPC bridge helpers.
import { api } from "./api";

export interface AppSettings {
  app_name: string;
  data_folder: string | null;
  last_sync: string | null;
  language: string;
  theme: string;
  auto_refresh_minutes: number;
  chat_model: string;
  configured: boolean;
}

export interface ChatStatus {
  available: boolean;
  path: string | null;
  model: string;
}

export const chatApi = {
  status: () => api.get<ChatStatus>("/api/chat/status"),
  send: (message: string) =>
    api.post<{ reply: string; available: boolean; model?: string }>("/api/chat", { message }),
};

export interface FolderValidation {
  valid: boolean;
  found: string[];
  missing: string[];
  optional: string[];
  error?: string;
}

export interface LoadCounts {
  clients: number;
  contracts: number;
  resources: number;
  roles: number;
  financials: number;
  allocations: number;
  opportunities: number;
}

export interface ConfigureResult {
  success: boolean;
  counts: LoadCounts;
  overlay_applied: number;
  last_sync: string;
  data_folder: string;
  settings: AppSettings;
}

export interface DataStatus {
  configured: boolean;
  loaded: boolean;
  contracts: number;
  last_sync: string | null;
  data_folder: string | null;
}

export const settingsApi = {
  get: () => api.get<AppSettings>("/api/settings"),
  update: (body: Partial<AppSettings>) => api.put<AppSettings>("/api/settings", body),
  status: () => api.get<DataStatus>("/api/data/status"),
  validate: (path: string) =>
    api.get<FolderValidation>(`/api/settings/validate?path=${encodeURIComponent(path)}`),
  configure: (dataFolder: string) =>
    api.post<ConfigureResult>("/api/settings/configure", { data_folder: dataFolder }),
  refresh: () => api.post<{ success: boolean; counts: LoadCounts; last_sync: string }>(
    "/api/data/refresh",
    {},
  ),
};

// ---- Electron IPC bridge (optional; present only in the desktop app) ----
export type UpdateStatus =
  | "idle" | "checking" | "available" | "downloading" | "downloaded"
  | "none" | "error" | "unsupported";

export interface UpdateState {
  status: UpdateStatus;
  percent?: number;
  info?: { version?: string } | null;
  error?: string | null;
}

declare global {
  interface Window {
    electronAPI?: {
      selectFile: () => Promise<string | null>;
      getPlatform: () => string;
      checkForUpdates: () => Promise<UpdateState>;
      getUpdateState: () => Promise<UpdateState>;
      installUpdate: () => Promise<{ ok: boolean }>;
    };
  }
}

/** Open the native Excel-file picker if running under Electron, else null. */
export async function pickFile(): Promise<string | null> {
  if (typeof window !== "undefined" && window.electronAPI?.selectFile) {
    return window.electronAPI.selectFile();
  }
  return null;
}

export const isElectron = () =>
  typeof window !== "undefined" && Boolean(window.electronAPI);

export const updates = {
  supported: () => isElectron() && Boolean(window.electronAPI?.getUpdateState),
  check: () => window.electronAPI?.checkForUpdates() ?? Promise.resolve({ status: "unsupported" as const }),
  state: () => window.electronAPI?.getUpdateState() ?? Promise.resolve({ status: "unsupported" as const }),
  install: () => window.electronAPI?.installUpdate() ?? Promise.resolve({ ok: false }),
};
