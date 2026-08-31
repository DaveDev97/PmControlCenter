"use strict";
// Secure bridge between the renderer (React) and the Electron main process.
// contextIsolation is enabled, so the renderer only sees the whitelisted API.
const { contextBridge, ipcRenderer } = require("electron");

// NOTE: we intentionally do NOT expose a fixed __API_BASE__. The SPA is served
// same-origin by the backend on a runtime-chosen port, so the frontend uses
// relative "/api/..." requests that always hit the correct backend.

contextBridge.exposeInMainWorld("electronAPI", {
  /** Open the native file picker (Excel); resolves to the chosen path or null. */
  selectFile: () => ipcRenderer.invoke("dialog:selectFile"),
  getPlatform: () => process.platform,
  /** Trigger an update check; auto-downloads if one is found. */
  checkForUpdates: () => ipcRenderer.invoke("updates:check"),
  /** Poll the current update state ({status, percent, info, error}). */
  getUpdateState: () => ipcRenderer.invoke("updates:state"),
  /** Quit and install a downloaded update. */
  installUpdate: () => ipcRenderer.invoke("updates:install"),
});
