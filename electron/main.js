"use strict";
const { app, BrowserWindow, dialog, ipcMain, shell, Menu } = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const backend = require("./python-runner");

let mainWindow = null;
let updater = null;

// Log backend output to %APPDATA%/PMControlCenter/logs/backend.log
function backendLogStream() {
  try {
    const dir = path.join(app.getPath("userData"), "logs");
    fs.mkdirSync(dir, { recursive: true });
    return fs.createWriteStream(path.join(dir, "backend.log"), { flags: "a" });
  } catch {
    return null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: "PM Control Center",
    backgroundColor: "#0f172a",
    show: true, // show immediately so the user always sees a window
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Show a loading screen right away; the real app URL is loaded once the
  // backend is ready (see startApp). This avoids a long "nothing happens" gap.
  mainWindow.loadURL(loadingPage("Avvio in corso…", "Caricamento del motore dati…"));

  // Open external links in the system browser, not inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function loadingPage(title, subtitle) {
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;
    justify-content:center;background:#0f172a;color:#e2e8f0;font-family:Segoe UI,system-ui,sans-serif}
    .s{width:42px;height:42px;border:4px solid #334155;border-top-color:#6366f1;border-radius:50%;
    animation:spin 1s linear infinite;margin-bottom:22px}@keyframes spin{to{transform:rotate(360deg)}}
    h1{font-size:18px;margin:0 0 6px}p{color:#94a3b8;font-size:13px;margin:0}</style></head>
    <body><div class="s"></div><h1>${title}</h1><p>${subtitle}</p></body></html>`;
  return "data:text/html;charset=utf-8," + encodeURIComponent(html);
}

function errorPage(message, log) {
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;min-height:100vh;box-sizing:border-box;padding:36px;background:#0f172a;color:#e2e8f0;
    font-family:Segoe UI,system-ui,sans-serif}h1{color:#f87171;font-size:20px}
    pre{white-space:pre-wrap;background:#1e293b;padding:14px;border-radius:8px;font-size:12px;
    color:#cbd5e1;max-height:50vh;overflow:auto}</style></head>
    <body><h1>Errore backend</h1><p>${esc(message)}</p>
    <p style="color:#94a3b8;font-size:13px">Log del backend:</p>
    <pre>${esc(log || "(nessun log)")}</pre></body></html>`;
  return "data:text/html;charset=utf-8," + encodeURIComponent(html);
}

// ---- IPC handlers ----
ipcMain.handle("dialog:selectFile", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Seleziona il file Excel dei dati",
    properties: ["openFile"],
    filters: [
      { name: "Excel", extensions: ["xlsx", "xlsm"] },
      { name: "Tutti i file", extensions: ["*"] },
    ],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

// ---- Auto-update state + IPC ----
// status: idle | checking | available | downloading | downloaded | none | error | unsupported
let updateState = { status: app ? "idle" : "idle", info: null, percent: 0, error: null };

ipcMain.handle("updates:check", async () => {
  if (!updater) return { status: "unsupported" };
  updateState = { status: "checking", info: null, percent: 0, error: null };
  updater.checkForUpdates().catch((e) => {
    updateState = { status: "error", error: String(e), percent: 0, info: null };
  });
  return updateState;
});

ipcMain.handle("updates:state", async () => updateState);

ipcMain.handle("updates:install", async () => {
  if (updater && updateState.status === "downloaded") {
    setImmediate(() => updater.quitAndInstall());
    return { ok: true };
  }
  return { ok: false };
});

// Wire electron-updater (only in a packaged build). Auto-downloads when an
// update is found; the renderer polls updates:state to show a dot + button.
function setupAutoUpdater() {
  if (!app.isPackaged) return;
  try {
    const { autoUpdater } = require("electron-updater");
    updater = autoUpdater;
    updater.autoDownload = true;
    updater.autoInstallOnAppQuit = true;
    updater.on("checking-for-update", () => (updateState = { ...updateState, status: "checking" }));
    updater.on("update-available", (info) => (updateState = { status: "available", info, percent: 0, error: null }));
    updater.on("update-not-available", () => (updateState = { status: "none", info: null, percent: 0, error: null }));
    updater.on("download-progress", (p) => (updateState = { status: "downloading", percent: Math.round(p.percent || 0), info: updateState.info, error: null }));
    updater.on("update-downloaded", (info) => (updateState = { status: "downloaded", info, percent: 100, error: null }));
    updater.on("error", (e) => (updateState = { status: "error", error: String(e), percent: 0, info: null }));
    updater.checkForUpdates().catch(() => {}); // silent check at startup
  } catch {
    // electron-updater not bundled — silently skip.
  }
}

function readBackendLog() {
  try {
    return fs.readFileSync(path.join(app.getPath("userData"), "logs", "backend.log"), "utf-8").slice(-4000);
  } catch {
    return "(nessun backend.log trovato — il processo backend potrebbe essere stato bloccato dalle policy/antivirus prima di avviarsi)";
  }
}

app.whenReady().then(async () => {
  createWindow(); // window + loading screen appear immediately

  if (process.env.ELECTRON_START_URL) {
    mainWindow.loadURL(process.env.ELECTRON_START_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    await backend.start(app, backendLogStream());
    try {
      await backend.waitUntilReady();
      mainWindow.loadURL(backend.apiBase()); // backend serves the SPA same-origin
    } catch (e) {
      const log = readBackendLog();
      if (mainWindow) mainWindow.loadURL(errorPage(String(e), log));
      dialog.showErrorBox("Backend error", String(e) + "\n\n--- backend.log ---\n" + log);
    }
  }
  setupAutoUpdater();

  if (process.platform === "darwin") Menu.setApplicationMenu(null);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", () => backend.stop());
process.on("exit", () => backend.stop());
