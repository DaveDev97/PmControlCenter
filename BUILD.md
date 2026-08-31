# PM Control Center - Build & Release Guide

Complete guide for building and releasing the PM Control Center Electron desktop application.

## Project Structure

```
pm_app/export/
├── frontend/              # React + Vite + TypeScript
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── backend/               # FastAPI Python backend
│   ├── app/
│   │   ├── main.py       # Entry point (version here)
│   │   ├── api/          # API routes
│   │   ├── models/       # SQLAlchemy models
│   │   ├── services/     # Business logic
│   │   └── core/         # Config, database
│   └── requirements.txt
├── electron/              # Electron main process
│   ├── main.js           # Electron entry point
│   └── preload.js
├── scripts/
│   └── anonymize_data.py # Excel anonymization
├── sample_data/
│   └── security_financials.xlsx
├── package.json           # Root package.json (version here)
├── .github/
│   └── workflows/
│       └── release.yml    # CI/CD automation
└── BUILD.md              # This file
```

## Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Frontend | React 18 + Vite + TypeScript | SPA with Tailwind CSS |
| State | React Query (TanStack Query) | Server state management |
| Backend | FastAPI 0.109+ (Python 3.11+) | Embedded, async-first |
| Database | SQLite (in-memory) | Loaded from Excel on startup |
| Desktop | Electron 28+ | Main + renderer process |
| Packaging | PyInstaller --onedir | Backend bundled as exe |
| Updates | electron-updater | Auto-update from GitHub releases |
| CI/CD | GitHub Actions | Windows build on tag push |
| AI Integration | Local Claude Code CLI | Subprocess spawning `claude -p` |
| Excel Read | openpyxl (read_only, data_only) | Contract/resource/opp data |
| Excel Anonymize | Surgical ZIP/XML editing | Preserves pivot tables |
| PPT Generation | python-pptx | Management-grade decks |

## Version Management

**Three files must be updated for each release:**

1. **`package.json`** (root)
   ```json
   {
     "version": "1.0.14"
   }
   ```

2. **`backend/app/main.py`**
   ```python
   app = FastAPI(
       title="PM Control Center API",
       version="1.0.14",
   )
   ```

3. **`frontend/src/components/Layout.tsx`** (footer text)
   ```tsx
   <div className="text-xs text-slate-400 dark:text-slate-500">v1.0.14</div>
   ```

## Build Process

### 1. Frontend Build

```bash
cd frontend
npm run build
# Output: frontend/dist/
```

**Key points:**
- Vite builds optimized production bundle
- Output goes to `frontend/dist/`
- Electron serves from this directory
- Build warnings about chunk size are normal

### 2. Backend PyInstaller Bundle

Done automatically by GitHub Actions (`.github/workflows/release.yml`), but can be run locally:

```bash
cd backend
pip install -r requirements.txt
pip install pyinstaller

# --onedir mode (current, fast startup after AV scan)
pyinstaller --name backend \
  --onedir \
  --noconfirm \
  --clean \
  --add-data "app:app" \
  --hidden-import=uvicorn.logging \
  --hidden-import=uvicorn.loops \
  --hidden-import=uvicorn.protocols \
  --hidden-import=sqlalchemy.ext.asyncio \
  --collect-all pptx \
  app/main.py

# Output: backend/dist/backend/ (directory with backend.exe + dependencies)
```

**PyInstaller flags explained:**
- `--onedir`: Bundle as directory (not single exe) — faster startup, AV-friendly after first scan
- `--add-data "app:app"`: Include app/ directory
- `--hidden-import`: Force inclusion of dynamic imports
- `--collect-all pptx`: Bundle python-pptx templates/resources

### 3. Electron Packaging

Done by GitHub Actions via `electron-builder`:

```bash
# Install dependencies
npm install

# Build Setup installer (with auto-updater)
npm run build:setup

# Build Portable exe (standalone)
npm run build:portable
```

**Output:**
- `release/PM-Control-Center-Setup-{version}-x64.exe` (installer, ~180 MB)
- `release/PM-Control-Center-Portable-{version}-x64.exe` (portable, ~180 MB)

**electron-builder.json config:**
```json
{
  "appId": "com.pmcontrol.desktop",
  "productName": "PM Control Center",
  "directories": {
    "output": "release"
  },
  "files": [
    "electron/**/*",
    "frontend/dist/**/*",
    "backend/dist/backend/**/*",
    "package.json"
  ],
  "win": {
    "target": ["nsis", "portable"],
    "icon": "electron/icon.ico"
  },
  "nsis": {
    "oneClick": false,
    "allowToChangeInstallationDirectory": true
  },
  "publish": {
    "provider": "github",
    "owner": "DaveDev97",
    "repo": "PmControlCenter"
  }
}
```

## Automated Release (GitHub Actions)

### Trigger a Release

```bash
# 1. Update version in 3 files (package.json, main.py, Layout.tsx)
sed -i 's/"version": "1.0.X"/"version": "1.0.Y"/' package.json
sed -i 's/version="1.0.X"/version="1.0.Y"/' backend/app/main.py
# Manually edit Layout.tsx footer

# 2. Build frontend locally (to verify)
cd frontend && npm run build && cd ..

# 3. Commit and push
git add -A
git commit -m "v1.0.Y: description of changes"
git push origin main

# 4. Create and push tag (triggers CI/CD)
git tag v1.0.Y -m "v1.0.Y"
git push origin v1.0.Y
```

**What happens automatically:**
1. GitHub Actions detects the tag push
2. Checks out code
3. Builds frontend (`npm run build`)
4. Sets up Python 3.11, installs dependencies
5. Runs PyInstaller to bundle backend
6. Runs electron-builder for Setup + Portable
7. Creates a **draft** GitHub release with both binaries
8. Uploads artifacts

### Publish the Release

```bash
# Get release ID
TOKEN=ghp_your_token_here
RELEASE_ID=$(curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/DaveDev97/PmControlCenter/releases" | \
  python3 -c "import sys,json;d=json.load(sys.stdin);print(next((r['id'] for r in d if r['tag_name']=='v1.0.Y'),''))")

# Publish (make latest)
curl -s -X PATCH -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/DaveDev97/PmControlCenter/releases/$RELEASE_ID" \
  -d '{"draft":false,"tag_name":"v1.0.Y","name":"v1.0.Y","make_latest":"true"}' | \
  python3 -c "import sys,json;print('Published:',json.load(sys.stdin).get('html_url'))"
```

## Complete Release Checklist

```bash
# Step 1: Bump version
sed -i 's/"version": "OLD"/"version": "NEW"/' package.json
sed -i 's/version="OLD"/version="NEW"/' backend/app/main.py
# Edit frontend/src/components/Layout.tsx footer manually

# Step 2: Build frontend
cd frontend && npm run build && cd ..

# Step 3: Commit
git add -A
git commit -m "vNEW: changelog summary"

# Step 4: Push
TOKEN=ghp_your_token_here
git push "https://DaveDev97:$TOKEN@github.com/DaveDev97/PmControlCenter.git" main

# Step 5: Tag and trigger build
git tag vNEW -m "vNEW"
git push "https://DaveDev97:$TOKEN@github.com/DaveDev97/PmControlCenter.git" vNEW

# Step 6: Monitor build
sleep 10
curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/DaveDev97/PmControlCenter/actions/runs?per_page=1" | \
  python3 -c "import sys,json;r=json.load(sys.stdin)['workflow_runs'][0];print('Build:',r['status'],'|',r['html_url'])"

# Step 7: Wait for completion (~13 min), then publish
# (Automated script monitors and publishes when done)
```

## GitHub Actions Workflow Details

**File:** `.github/workflows/release.yml`

**Trigger:** Push to tag matching `v*.*.*`

**Steps:**
1. **Checkout** — `actions/checkout@v3`
2. **Setup Node.js** — `actions/setup-node@v3` (Node 18)
3. **Setup Python** — `actions/setup-python@v4` (Python 3.11)
4. **Install Node deps** — `npm ci`
5. **Install Python deps** — `pip install -r backend/requirements.txt`
6. **Install PyInstaller** — `pip install pyinstaller`
7. **Build frontend** — `cd frontend && npm run build`
8. **Bundle backend** — PyInstaller with all flags
9. **Build Electron** — `electron-builder` for nsis + portable
10. **Create release** — Upload both exes as draft release

**Environment:**
- OS: `windows-latest` (required for electron-builder Windows target)
- Timeout: 30 minutes
- Artifacts: Setup + Portable exes (~180 MB each)

## Local Testing (Without CI)

```bash
# 1. Build frontend
cd frontend && npm run build && cd ..

# 2. Bundle backend (Windows)
cd backend
pip install -r requirements.txt pyinstaller
pyinstaller --name backend --onedir --noconfirm --clean \
  --add-data "app:app" \
  --hidden-import=uvicorn.logging \
  --hidden-import=uvicorn.loops \
  --hidden-import=uvicorn.protocols \
  --hidden-import=sqlalchemy.ext.asyncio \
  --collect-all pptx \
  app/main.py
cd ..

# 3. Run in dev mode
npm run dev
# Opens Electron window with hot reload

# 4. Build installers (optional, slow)
npm run build:setup
npm run build:portable
```

## Backend Entry Point

**File:** `backend/app/main.py`

```python
import sys
from pathlib import Path

# When bundled by PyInstaller, app/ is at _MEIPASS/app
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS) / "app"
else:
    BASE_DIR = Path(__file__).parent

# FastAPI app
app = FastAPI(title="PM Control Center API", version="1.0.14")

# SQLite database path (in-memory)
# Data loaded from Excel on /api/settings/configure

# Routes
app.include_router(contracts.router)
app.include_router(opportunities.router)
# ... etc
```

**Startup:**
- Electron spawns `backend.exe --port <random>`
- Backend binds to `127.0.0.1:<port>` (local only)
- Frontend connects via `http://127.0.0.1:<port>`

## Electron Main Process

**File:** `electron/main.js`

**Key responsibilities:**
1. Spawn backend subprocess (`backend/dist/backend/backend.exe`)
2. Create BrowserWindow serving `frontend/dist/index.html`
3. Implement IPC handlers (file picker, updates)
4. Auto-updater integration (electron-updater)

**Port allocation:**
```javascript
const port = 8000 + Math.floor(Math.random() * 1000);
const backendPath = isDev
  ? path.join(__dirname, "../backend/dist/backend/backend.exe")
  : path.join(process.resourcesPath, "backend/dist/backend/backend.exe");

const backendProcess = spawn(backendPath, ["--port", port.toString()]);
```

**Auto-updater:**
```javascript
const { autoUpdater } = require("electron-updater");
autoUpdater.checkForUpdatesAndNotify();

// Exposed via IPC to Settings page
ipcMain.handle("updates:check", async () => {
  return await autoUpdater.checkForUpdates();
});
```

## Dependencies

### Frontend (`frontend/package.json`)
- react, react-dom (18.x)
- react-query (@tanstack/react-query 5.x)
- react-router-dom (6.x)
- lucide-react (icons)
- recharts (charts)
- i18next (i18n)
- tailwindcss (styling)

### Backend (`backend/requirements.txt`)
```
fastapi>=0.109
uvicorn[standard]>=0.27
sqlalchemy>=2.0
aiosqlite>=0.19
pydantic>=2.6
openpyxl>=3.1
pandas>=2.2
python-pptx>=1.0
```

### Electron (root `package.json`)
- electron (28.x)
- electron-builder (24.x)
- electron-updater (6.x)

## Troubleshooting

### Build fails: "Module not found"
- Check PyInstaller `--hidden-import` flags
- Add missing imports to `release.yml`

### Frontend not loading in Electron
- Verify `frontend/dist/` exists after build
- Check `electron/main.js` path resolution

### Backend port conflict
- Random port allocation (8000-9000) avoids conflicts
- If blocked, kill `backend.exe` processes

### Auto-update not working
- Only works in **Setup** installer, not Portable
- Requires valid code signing (optional, works unsigned with warnings)

### PyInstaller --onefile vs --onedir
- `--onefile`: Single exe, slow startup (AV scans on every launch)
- `--onedir`: Directory with exe + DLLs, fast after first AV scan (current choice)

### Excel recovery prompt on anonymized file
- Fixed in v1.0.4+ with surgical ZIP/XML editing
- Preserves all 111 zip parts (pivots, calcChain, drawings)

## File Size Reference

| File | Size | Notes |
|------|------|-------|
| Setup installer | ~180 MB | Includes Electron + backend + frontend |
| Portable exe | ~180 MB | Same as Setup, single file |
| Backend bundle | ~120 MB | Python runtime + dependencies |
| Frontend dist | ~2 MB | Optimized Vite build |

## Security Notes

1. **Never commit GitHub tokens** — use environment secrets or manual input
2. **Backend is local-only** — binds to 127.0.0.1, not exposed to network
3. **Excel anonymization** — surgical editing, 0 leaks verified
4. **Auto-update** — unsigned builds show Windows warning (acceptable for internal use)

## CI/CD Workflow Summary

```
Tag push (v1.0.X)
  ↓
GitHub Actions triggered
  ↓
Build frontend (npm run build)
  ↓
Bundle backend (PyInstaller)
  ↓
Package Electron (electron-builder)
  ↓
Create draft release
  ↓
Upload Setup + Portable exes
  ↓
Manual: Publish release (undraft)
  ↓
electron-updater notifies users
```

## Version History

- **v1.0.14** — Sidebar collapse fix, Cost Balancer labels, PPT Opus 5
- **v1.0.13** — Due Diligence apply template
- **v1.0.12** — Real WBS values, PPT generation with python-pptx
- **v1.0.11** — Table sorting and filtering
- **v1.0.10** — In-app update check/install
- **v1.0.8** — File picker (direct .xlsx selection)
- **v1.0.6** — AI chat with local Claude Code CLI
- **v1.0.4** — Excel anonymization fix (surgical ZIP/XML)
- **v1.0.3** — Initial stable release

---

**Last updated:** 2026-08-31  
**Maintainer:** PM Control Center Team  
**Repository:** https://github.com/DaveDev97/PmControlCenter
