# PM Control Center - Architettura Tecnica

## 📐 Overview Architetturale

```
┌─────────────────────────────────────────────────────────────┐
│                    Desktop Application                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Electron Main Process                      │ │
│  │  - Window management                                   │ │
│  │  - Menu bar & tray                                     │ │
│  │  - Auto-update (GitHub Releases)                       │ │
│  │  - Python subprocess manager                           │ │
│  └───────────────────┬────────────────────────────────────┘ │
│                      │                                        │
│  ┌───────────────────▼──────────────┐  ┌──────────────────┐ │
│  │   React Frontend (BrowserView)   │  │  FastAPI Backend │ │
│  │   - React 18 + Vite              │◄─┤  (Embedded)      │ │
│  │   - Tailwind CSS                 │  │  - Python 3.11   │ │
│  │   - TanStack Query               │  │  - SQLAlchemy    │ │
│  │   - i18next (IT/EN)              │  │  - Pandas        │ │
│  │   http://localhost:3000          │  │  :8000           │ │
│  └────────────────┬─────────────────┘  └────────┬─────────┘ │
│                   │                               │           │
└───────────────────┼───────────────────────────────┼───────────┘
                    │                               │
                    │         IPC Bridge            │
                    │    (settings, file picker)    │
                    │                               │
        ┌───────────▼───────────────────────────────▼─────┐
        │            Data Layer (Local)                    │
        │  ┌──────────────────┐  ┌───────────────────┐   │
        │  │ SQLite In-Memory │  │  Settings JSON    │   │
        │  │  (Runtime cache) │  │  %APPDATA%/...    │   │
        │  └──────────────────┘  └───────────────────┘   │
        └──────────────────┬───────────────────────────────┘
                           │
                           │ Sync on startup / refresh
                           │
        ┌──────────────────▼───────────────────────────────┐
        │      SharePoint Folder (via OneDrive Sync)       │
        │  ┌───────────────────────────────────────────┐  │
        │  │  contracts_financials.xlsx  [READ-ONLY]   │  │
        │  │  allocations.xlsx           [READ-ONLY]   │  │
        │  │  opportunities.xlsx         [READ-ONLY]   │  │
        │  │  pm_overlay.json            [READ-WRITE]  │  │
        │  └───────────────────────────────────────────┘  │
        └──────────────────────────────────────────────────┘
```

---

## 🧩 Componenti Principali

### 1. Electron Main Process

**Responsabilità:**
- Gestione finestra nativa
- Menu applicazione & system tray
- File dialog (selezione cartella dati)
- IPC communication con renderer
- Avvio/gestione subprocess Python (FastAPI)
- Auto-update da GitHub Releases
- Deep linking (protocol handler)

**File:**
- `electron/main.js` - Entry point
- `electron/python-runner.js` - FastAPI subprocess
- `electron/auto-updater.js` - GitHub releases check
- `electron/preload.js` - Secure bridge

**Tecnologie:**
- Electron 28
- electron-builder (packaging)
- electron-updater (auto-update)

---

### 2. Frontend (React)

**Responsabilità:**
- UI/UX completo
- Dashboard interattive (Account, Contract, Team, Person)
- Grafici (Recharts)
- Setup Wizard (prima configurazione)
- Settings manager
- i18n (italiano/inglese)

**File principali:**
```
frontend/src/
├── pages/
│   ├── SetupWizard.tsx          # Prima configurazione
│   ├── SettingsPage.tsx         # Gestione settings
│   ├── AccountDashboard.tsx     # Dashboard account
│   ├── ContractDashboard.tsx    # Dashboard contratto
│   ├── TeamDashboard.tsx        # Dashboard team
│   ├── PersonDashboard.tsx      # Dashboard persona
│   ├── OpportunityDetail.tsx    # Dettaglio opportunità + DD
│   ├── TimeReportGenerator.tsx  # Gestione time reports
│   ├── CostBalancer.tsx         # Ottimizzazione costi
│   └── AIChatPage.tsx           # Chat AI (future)
├── components/
│   ├── Layout.tsx               # Shell app (sidebar, theme)
│   ├── charts.tsx               # Componenti grafici
│   └── ui.tsx                   # Componenti base (Card, Loading)
├── lib/
│   ├── api.ts                   # Client API FastAPI
│   ├── types.ts                 # TypeScript types
│   ├── format.ts                # Formatters (€, date, %)
│   ├── settings.ts              # Settings manager
│   └── i18n.ts                  # Configurazione i18next
└── locales/
    ├── it.json                  # Traduzioni italiano
    └── en.json                  # Traduzioni inglese
```

**Tecnologie:**
- React 18
- Vite 5
- TanStack Query (cache API)
- Recharts (grafici)
- Tailwind CSS (styling)
- i18next (traduzioni)
- Lucide Icons

---

### 3. Backend (FastAPI)

**Responsabilità:**
- REST API JSON
- Caricamento Excel → SQLite
- Business logic (dashboard, KPI, aggregazioni)
- Gestione overlay (modifiche utente)
- Time reports generation/upload

**Architettura:**

```
backend/app/
├── main.py                    # Entry point FastAPI
├── core/
│   ├── config.py              # Settings manager (Pydantic)
│   ├── database.py            # SQLAlchemy engine (in-memory)
│   └── dependencies.py        # DI (session, settings)
├── models.py                  # ORM models (SQLAlchemy)
├── schemas.py                 # Pydantic schemas (API)
├── services/
│   ├── excel_reader.py        # Parser Excel → DB
│   ├── data_sync.py           # Sync Excel ↔ SQLite
│   ├── overlay_manager.py     # Gestione pm_overlay.json
│   ├── dashboard.py           # Business logic dashboard
│   ├── dd_tracker.py          # Due Diligence logic
│   └── cost_balancer.py       # Algoritmo ottimizzazione
└── api/
    ├── dashboard.py           # Endpoints dashboard
    ├── resources.py           # CRUD resources
    ├── contracts.py           # CRUD contracts
    ├── opportunities.py       # CRUD opportunities
    ├── due_diligence.py       # DD endpoints
    ├── time_reports.py        # Time reports
    ├── time_upload.py         # Upload Excel ore
    └── settings.py            # Settings API
```

**Tecnologie:**
- FastAPI 0.109
- SQLAlchemy 2.0 (async)
- Pandas (Excel parsing)
- Openpyxl (Excel I/O)
- Pydantic 2.0 (validation)

---

## 🔄 Flusso Dati

### Startup Sequence

```
1. Electron Main avvia
   ↓
2. Legge settings da %APPDATA%/PMControlCenter/settings.json
   ↓
3. Se data_folder configurato:
   - Avvia FastAPI subprocess
   - Carica React frontend
   - Apre finestra → http://localhost:3000
   ↓
   Altrimenti:
   - Apre Setup Wizard
```

### Setup Wizard Flow

```
User seleziona cartella SharePoint
   ↓
Frontend → POST /api/settings/configure {"data_folder": "..."}
   ↓
Backend valida cartella:
   - contracts_financials.xlsx exists?
   - allocations.xlsx exists?
   - opportunities.xlsx exists? (opzionale)
   ↓
Backend carica Excel → SQLite in-memory
   ↓
Response: {success: true, counts: {...}}
   ↓
Frontend → Salva settings localmente
   ↓
Redirect → Dashboard
```

### Data Refresh Flow

```
User click "Refresh" button (o auto ogni N min)
   ↓
Frontend → POST /api/data/refresh
   ↓
Backend:
   1. Rilegge tutti gli Excel
   2. Rilegge pm_overlay.json
   3. Merge overlay su dati base
   4. Rebuild SQLite in-memory
   ↓
Response: {success: true, last_sync: "..."}
   ↓
Frontend → invalidate tutte le query (TanStack Query)
```

### Modifica DD Status Flow

```
User espande DD task → click "Modifica"
   ↓
Form edit → Salva
   ↓
Frontend → PUT /api/due-diligence/{dd_id}
   Body: {status: "completed", completed_date: "...", ...}
   ↓
Backend:
   1. Update SQLite row
   2. Salva in pm_overlay.json:
      {
        "due_diligence_updates": {
          "5": {
            "status": "completed",
            "completed_date": "2026-08-31",
            ...
          }
        }
      }
   ↓
Response: {success: true}
   ↓
Frontend → Invalidate query → Re-render
```

---

## 💾 Data Layer

### SQLite In-Memory

**Vantaggi:**
- Performance: query istantanee
- Relazioni SQL: JOIN tra tabelle
- Aggregazioni complesse

**Lifecycle:**
1. App start → CREATE TABLES
2. Carica Excel → INSERT rows
3. Runtime → SELECT queries (read-only per utente)
4. Modifiche → UPDATE (poi persist su overlay)
5. Refresh → DROP + reload

**Schema:** Identico a `pm_app/backend/app/models.py`

### pm_overlay.json

**Formato:**
```json
{
  "version": "1.0",
  "last_modified": "2026-08-31T15:30:00Z",
  "due_diligence_updates": {
    "5": {
      "status": "completed",
      "completed_date": "2026-08-31",
      "approver": "Manager A",
      "notes": "Approved with 35% margin"
    }
  },
  "custom_notes": {
    "opportunity_1": "Follow-up richiesto entro Q3"
  },
  "user_preferences": {
    "user@company.com": {
      "favorite_contracts": ["PROJ-001", "PROJ-002"]
    }
  }
}
```

**Merge Logic:**

```python
# Backend carica Excel → base_data
# Carica overlay → overlay_data
# Per ogni DD:
if dd.id in overlay_data["due_diligence_updates"]:
    dd.status = overlay_data["..."]["status"]
    dd.completed_date = overlay_data["..."]["completed_date"]
    # etc.
```

---

## 🔐 Security & Privacy

### Dati Sensibili

**Excel anonimizzati (sample_data/):**
- Nomi → "Manager A", "Senior Consultant 1"
- Email → "manager.a@company.com"
- Client → "Alpha Corp", "Beta Industries"
- Contratti → "PROJ-001", "PROJ-002"
- Importi → scalati 0.7-1.3x random

**Produzione:**
- Excel su SharePoint = dati reali
- Nessun telemetry inviato
- Nessun cloud backend
- Solo local storage

### Permessi Windows

- **Lettura**: SharePoint folder (OneDrive sync)
- **Scrittura**: pm_overlay.json
- **Nessun admin** richiesto

---

## 📦 Build & Packaging

### Build Process

```bash
npm run build
```

**Steps:**
1. `scripts/anonymize_data.py` → genera sample_data/
2. `cd frontend && npm run build` → dist/
3. `python -m PyInstaller backend/app/main.py` → backend.exe
4. `electron-builder` → package app
   - Include Python embedded (no install richiesto)
   - Include SQLite DLL
   - Include frontend/dist
   - Include backend.exe
5. Output:
   - `PM-Control-Center-Setup.exe` (NSIS installer)
   - `PM-Control-Center-Portable.zip`

### Installer (NSIS)

**Custom steps:**
- Verifica SQLite (scarica se manca)
- Copia sample_data → Documents/PMControlCenter/
- Crea desktop shortcut
- Registra uninstaller

---

## 🔄 Auto-Update

### GitHub Releases Strategy

**Versioning:** Semantic (1.0.0, 1.1.0, 2.0.0)

**Release workflow:**
1. Tag repo: `git tag v1.1.0`
2. GitHub Action build automatico
3. Pubblica release con:
   - `PM-Control-Center-Setup-v1.1.0.exe`
   - `PM-Control-Center-Portable-v1.1.0.zip`
   - `CHANGELOG.md`

**App check:**
- Ogni 24h al startup
- GET https://api.github.com/repos/org/pm-control-center/releases/latest
- Confronta `version` con app corrente
- Se nuovo → prompt download + install

---

## 🌐 i18n Internazionalization

### Supported Languages

- **Italiano** (default) - `it`
- **English** - `en`

### Structure

```
frontend/src/locales/
├── it.json
│   {
│     "dashboard": {
│       "title": "Dashboard",
│       "revenue": "Ricavi",
│       "costs": "Costi",
│       ...
│     }
│   }
└── en.json
    {
      "dashboard": {
        "title": "Dashboard",
        "revenue": "Revenue",
        "costs": "Costs",
        ...
      }
    }
```

### Usage

```tsx
import { useTranslation } from 'react-i18next';

const { t } = useTranslation();

<h1>{t('dashboard.title')}</h1>
```

### Language Switch

Settings → Language → IT/EN → salva in settings.json

---

## 🧪 Testing Strategy

### Unit Tests

- Backend: pytest
- Frontend: Vitest

### Integration Tests

- Excel parsing: vari formati Excel
- API endpoints: tutti i CRUD
- Dashboard: calcoli KPI

### E2E Tests

- Playwright: flow completo
  1. Setup Wizard
  2. Dashboard navigation
  3. DD edit & save
  4. Settings change

---

## 📊 Performance

### Targets

- **Startup time**: < 3s (cold start)
- **Excel load**: < 2s per 1000 rows
- **Dashboard render**: < 500ms
- **Graph render**: < 300ms
- **Memory**: < 200MB RAM

### Optimizations

- SQLite in-memory (vs file)
- TanStack Query cache
- React.memo su chart components
- Virtual scrolling per tabelle grandi
- Lazy load routes (React.lazy)

---

## 🐛 Logging & Debugging

### Log Files

```
%APPDATA%/PMControlCenter/logs/
├── app.log              # Electron main
├── backend.log          # FastAPI
└── frontend.log         # React errors
```

### Log Levels

- DEBUG: dettagli parsing Excel
- INFO: startup, refresh, API calls
- WARNING: file mancanti, dati inconsistenti
- ERROR: crash, exceptions

### Sentry Integration (Future)

Opzionale: crash reporting anonimo

---

## 🔮 Future Roadmap

### v1.1.0
- [ ] Export Excel custom (template)
- [ ] Dashboard Projects (contract → projects drill-down)
- [ ] Notifiche desktop (DD scadenze)

### v1.2.0
- [ ] AI Chat integrato (Claude local)
- [ ] Forecasting automatico (ML)
- [ ] Mobile companion app (read-only)

### v2.0.0
- [ ] Backend cloud opzionale (multi-tenant)
- [ ] Real-time collaboration
- [ ] Advanced analytics (BI dashboard)

---

**Last Updated:** 2026-08-31  
**Version:** 1.0.0  
**Maintainer:** PM Control Center Team
