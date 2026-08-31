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
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());

  // The backend serves the built SPA same-origin, so we load it over HTTP
  // (not file://): this avoids CORS/preflight 405s and fixes absolute asset
  // paths like /logo.svg. In dev, ELECTRON_START_URL points at the Vite server.
  const startUrl = process.env.ELECTRON_START_URL || backend.apiBase();
  mainWindow.loadURL(startUrl);
  if (process.env.ELECTRON_START_URL) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }

  // Open external links in the system browser, not inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ---- IPC handlers ----
ipcMain.handle("dialog:selectFolder", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select the data folder",
    properties: ["openDirectory"],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

ipcMain.handle("app:checkForUpdates", async () => {
  if (updater) {
    try {
      await updater.checkForUpdatesAndNotify();
      return { checking: true };
    } catch (e) {
      return { error: String(e) };
    }
  }
  return { checking: false };
});

// Optional auto-updater: only wired when electron-updater is installed.
function setupAutoUpdater() {
  if (!app.isPackaged) return;
  try {
    const { autoUpdater } = require("electron-updater");
    updater = autoUpdater;
    updater.checkForUpdatesAndNotify().catch(() => {});
  } catch {
    // electron-updater not bundled — silently skip.
  }
}

app.whenReady().then(async () => {
  await backend.start(app, backendLogStream());
  try {
    await backend.waitUntilReady();
  } catch (e) {
    dialog.showErrorBox(
      "Backend error",
      "The application backend could not be started.\n\n" + String(e),
    );
  }
  createWindow();
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
