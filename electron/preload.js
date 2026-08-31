"use strict";
// Secure bridge between the renderer (React) and the Electron main process.
// contextIsolation is enabled, so the renderer only sees the whitelisted API.
const { contextBridge, ipcRenderer } = require("electron");

const API_BASE = process.env.PMCC_API_BASE || "http://127.0.0.1:8000";

// The frontend API client reads window.__API_BASE__ to target the backend.
contextBridge.exposeInMainWorld("__API_BASE__", API_BASE);

contextBridge.exposeInMainWorld("electronAPI", {
  /** Open the native directory picker; resolves to the chosen path or null. */
  selectFolder: () => ipcRenderer.invoke("dialog:selectFolder"),
  getPlatform: () => process.platform,
  /** Ask the main process to check for updates (no-op if unsupported). */
  checkForUpdates: () => ipcRenderer.invoke("app:checkForUpdates"),
});
