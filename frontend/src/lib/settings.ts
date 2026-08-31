// Settings & data-management API client + Electron IPC bridge helpers.
import { api } from "./api";

export interface AppSettings {
  app_name: string;
  data_folder: string | null;
  last_sync: string | null;
  language: string;
  theme: string;
  auto_refresh_minutes: number;
  configured: boolean;
}

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
declare global {
  interface Window {
    electronAPI?: {
      selectFolder: () => Promise<string | null>;
      getPlatform: () => string;
    };
  }
}

/** Open the native folder picker if running under Electron, else return null. */
export async function pickFolder(): Promise<string | null> {
  if (typeof window !== "undefined" && window.electronAPI?.selectFolder) {
    return window.electronAPI.selectFolder();
  }
  return null;
}

export const isElectron = () =>
  typeof window !== "undefined" && Boolean(window.electronAPI);
