"use strict";
// Manages the embedded FastAPI backend as a child process and waits until it
// is reachable. Works both in development (system Python + uvicorn) and in a
// packaged build (a PyInstaller-built backend executable bundled in resources).
const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = Number(process.env.PMCC_BACKEND_PORT || 8000);
const API_BASE = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

let backendProc = null;

function backendDir(app) {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.join(__dirname, "..", "backend");
}

function frontendDir(app) {
  return app.isPackaged
    ? path.join(process.resourcesPath, "frontend", "dist")
    : path.join(__dirname, "..", "frontend", "dist");
}

function packagedExecutable(app) {
  // A PyInstaller onefile build placed next to the backend sources.
  const exe = process.platform === "win32" ? "pmcc-backend.exe" : "pmcc-backend";
  const candidate = path.join(backendDir(app), exe);
  return fs.existsSync(candidate) ? candidate : null;
}

function start(app, logStream) {
  const cwd = backendDir(app);
  const env = {
    ...process.env,
    PMCC_BACKEND_PORT: String(BACKEND_PORT),
    PMCC_FRONTEND_DIR: frontendDir(app),
  };
  const exe = packagedExecutable(app);

  if (exe) {
    backendProc = spawn(exe, ["--host", BACKEND_HOST, "--port", String(BACKEND_PORT)], {
      cwd,
      env,
    });
  } else {
    const python = process.platform === "win32" ? "python" : "python3";
    backendProc = spawn(
      python,
      ["-m", "uvicorn", "app.main:app", "--host", BACKEND_HOST, "--port", String(BACKEND_PORT)],
      { cwd, env },
    );
  }

  if (logStream) {
    backendProc.stdout?.pipe(logStream);
    backendProc.stderr?.pipe(logStream);
  }
  backendProc.on("error", (err) => console.error("[backend] failed to start:", err));
  backendProc.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
  return backendProc;
}

function waitUntilReady(retries = 60, intervalMs = 500) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      const req = http.get(
        { host: BACKEND_HOST, port: BACKEND_PORT, path: "/api/health", timeout: 1000 },
        (res) => {
          res.resume();
          resolve();
        },
      );
      const retry = () => {
        if (n <= 0) return reject(new Error("Backend not reachable"));
        setTimeout(() => attempt(n - 1), intervalMs);
      };
      req.on("error", retry);
      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    };
    attempt(retries);
  });
}

function stop() {
  if (backendProc && !backendProc.killed) {
    backendProc.kill();
    backendProc = null;
  }
}

module.exports = { start, stop, waitUntilReady, API_BASE, BACKEND_PORT, BACKEND_HOST };
