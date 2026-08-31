"use strict";
// Manages the embedded FastAPI backend as a child process and waits until it
// is reachable. Works both in development (system Python + uvicorn) and in a
// packaged build (a PyInstaller-built backend executable bundled in resources).
//
// In a packaged build we bind to a FREE ephemeral port chosen at runtime: on
// locked-down/corporate machines a fixed port (e.g. 8000) is often already
// taken by another service (IIS/WCF/…), which would otherwise shadow our app.
// In development we keep 8000 so the Vite dev-server proxy keeps working.
const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");

const BACKEND_HOST = "127.0.0.1";
const DEV_PORT = Number(process.env.PMCC_BACKEND_PORT || 8000);

let backendProc = null;
let backendPort = DEV_PORT;

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
  const exe = process.platform === "win32" ? "pmcc-backend.exe" : "pmcc-backend";
  const candidate = path.join(backendDir(app), exe);
  return fs.existsSync(candidate) ? candidate : null;
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, BACKEND_HOST, () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

async function start(app, logStream) {
  backendPort = app.isPackaged ? await findFreePort() : DEV_PORT;
  const cwd = backendDir(app);
  const env = {
    ...process.env,
    PMCC_BACKEND_PORT: String(backendPort),
    PMCC_FRONTEND_DIR: frontendDir(app),
  };
  const exe = packagedExecutable(app);

  if (exe) {
    backendProc = spawn(exe, ["--host", BACKEND_HOST, "--port", String(backendPort)], { cwd, env });
  } else {
    const python = process.platform === "win32" ? "python" : "python3";
    backendProc = spawn(
      python,
      ["-m", "uvicorn", "app.main:app", "--host", BACKEND_HOST, "--port", String(backendPort)],
      { cwd, env },
    );
  }

  if (logStream) {
    backendProc.stdout?.pipe(logStream);
    backendProc.stderr?.pipe(logStream);
  }
  backendProc.on("error", (err) => console.error("[backend] failed to start:", err));
  backendProc.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
  return backendPort;
}

function apiBase() {
  return `http://${BACKEND_HOST}:${backendPort}`;
}

// Poll /api/health until it responds AND the body is clearly OUR backend
// (guards against latching onto a foreign service that happens to answer).
function waitUntilReady(retries = 60, intervalMs = 500) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      const req = http.get(
        { host: BACKEND_HOST, port: backendPort, path: "/api/health", timeout: 1000 },
        (res) => {
          let body = "";
          res.on("data", (c) => (body += c));
          res.on("end", () => {
            if (res.statusCode === 200 && body.includes('"status"') && body.includes("ok")) {
              resolve();
            } else {
              retry(n);
            }
          });
        },
      );
      const retry = (k) => {
        if (k <= 0) return reject(new Error("Backend not reachable"));
        setTimeout(() => attempt(k - 1), intervalMs);
      };
      req.on("error", () => retry(n));
      req.on("timeout", () => {
        req.destroy();
        retry(n);
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

module.exports = { start, stop, waitUntilReady, apiBase, BACKEND_HOST };
