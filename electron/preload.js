"use strict";
// Secure bridge between the renderer (React) and the Electron main process.
// contextIsolation is enabled, so the renderer only sees the whitelisted API.
const { contextBridge, ipcRenderer } = require("electron");

// NOTE: we intentionally do NOT expose a fixed __API_BASE__. The SPA is served
// same-origin by the backend on a runtime-chosen port, so the frontend uses
// relative "/api/..." requests that always hit the correct backend.

contextBridge.exposeInMainWorld("electronAPI", {
  /** Open the native directory picker; resolves to the chosen path or null. */
  selectFolder: () => ipcRenderer.invoke("dialog:selectFolder"),
  getPlatform: () => process.platform,
  /** Ask the main process to check for updates (no-op if unsupported). */
  checkForUpdates: () => ipcRenderer.invoke("app:checkForUpdates"),
});
