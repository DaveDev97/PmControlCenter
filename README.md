# PM Control Center - Export Package

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## 📋 Overview

PM Control Center è un'applicazione desktop Windows per la gestione di progetti, risorse, opportunità e analisi finanziarie. Progettata per team che utilizzano SharePoint come storage condiviso, elimina la necessità di un server dedicato mantenendo sincronizzazione multi-utente.

## ✨ Caratteristiche

- 🖥️ **Desktop App nativa** - Nessun browser o terminale da aprire
- 📊 **Dashboard interattive** - Account, Contract, Team, Person view
- 📈 **Grafici real-time** - Revenue, costi, CI%, chargeability
- 🔄 **Sync SharePoint** - Cartella condivisa come "database centrale"
- 🌐 **Multi-lingua** - Italiano (default) + Inglese
- 🎨 **Dark/Light mode** - Tema personalizzabile
- 📝 **Due Diligence tracking** - Workflow sequenziale 22 step
- 💰 **Fatturazione** - Tracking invoice per opportunità
- ⏱️ **Time Reports** - Gestione ore dichiarate (quindicine)
- 🔐 **Dati anonimizzati** - Excel demo inclusi per test

## 🚀 Quick Start

### Installazione

1. Scarica `PM-Control-Center-Setup.exe` da [Releases](https://github.com/DaveDev97/PmControlCenter/releases)
2. Esegui installer (verifica automatica dipendenze)
3. Avvia l'app dal desktop shortcut
4. **Setup Wizard**: Seleziona cartella SharePoint con file Excel
5. ✅ Pronto!

### Versione Portable

Estrai `PM-Control-Center-Portable.zip` in qualsiasi cartella ed esegui `PM-Control-Center.exe`.

### Dati Demo

Per testare l'app senza dati reali:

```bash
# La cartella sample_data/ viene copiata in:
C:\Users\<Nome>\Documents\PMControlCenter\sample_data\

# Contiene 3 Excel anonimizzati:
- contracts_financials.xlsx (contratti, costi, risorse)
- allocations.xlsx (allocazioni risorse)
- opportunities.xlsx (opportunità commerciali)
```

Al primo avvio, punta a questa cartella nel Setup Wizard.

## 📁 Struttura Dati

### File Richiesti (SharePoint)

```
SharePoint/PM_Data/
├── contracts_financials.xlsx   [OBBLIGATORIO]
│   ├── Sheet: Contracts
│   ├── Sheet: Financials
│   └── Sheet: Resources
├── allocations.xlsx             [OBBLIGATORIO]
│   └── Sheet: Allocations
└── opportunities.xlsx           [OPZIONALE]
    └── Sheet: Opportunities
```

### Schema Excel

Vedi [sample_data/README.md](sample_data/README.md) per struttura dettagliata colonne.

### Modifiche App

Le modifiche fatte dall'app (es. stato Due Diligence) vengono salvate in:

```
SharePoint/PM_Data/pm_overlay.json
```

Questo file NON va modificato manualmente. Contiene:
- Status aggiornamenti DD
- Note custom opportunità
- Configurazioni temporanee

## ⚙️ Configurazione

### Settings Applicazione

**Menu → Settings** (⚙️ in alto a destra)

- **Data Folder**: Cambia percorso cartella SharePoint
- **Reload Data**: Ricarica Excel (dopo modifiche esterne)
- **Language**: Italiano / English
- **Theme**: Light / Dark / Auto
- **Auto-refresh**: Ricarica automatica ogni N minuti
- **Check Updates**: Verifica aggiornamenti disponibili

### Sincronizzazione Multi-Utente

**Come funziona:**

1. Excel su SharePoint = **source of truth** (read-only)
2. Ogni utente carica Excel in SQLite locale (in-memory) all'avvio
3. Modifiche UI → salvate in `pm_overlay.json` condiviso
4. OneDrive/SharePoint sync automatico del JSON
5. Refresh → rilegge Excel + overlay

**Conflitti:**

- Excel: nessun conflitto (read-only)
- Overlay: last-write-wins (OneDrive gestisce versioning)

## 🛠️ Build da Sorgenti

### Prerequisiti

- Node.js 18+
- Python 3.11+
- Git

### Comandi

```bash
# Clone repo
git clone https://github.com/DaveDev97/PmControlCenter.git
cd pm-control-center/export

# Install dependencies
npm install
cd backend && pip install -r requirements.txt && cd ..

# Genera Excel anonimizzati
python scripts/anonymize_data.py

# Build React frontend
cd frontend && npm run build && cd ..

# Package Electron app
npm run build

# Output in: ./output/
```

## 📖 Documentazione

- [ARCHITECTURE.md](ARCHITECTURE.md) - Architettura tecnica
- [sample_data/README.md](sample_data/README.md) - Schema Excel
- [CHANGELOG.md](CHANGELOG.md) - Versioni e modifiche

## 🐛 Troubleshooting

### App non si avvia

1. Verifica dipendenze: SQLite DLL presente in `resources/sqlite/`
2. Controlla log: `%APPDATA%/PMControlCenter/logs/app.log`
3. Reinstalla app

### Dati non caricano

1. Verifica percorso cartella in Settings
2. Controlla che Excel abbiano nomi corretti
3. Apri Excel manualmente per verificare formato
4. Log dettagliato in `app.log`

### Modifiche non salvano

1. Verifica permessi scrittura su cartella SharePoint
2. Controlla che `pm_overlay.json` non sia in sola lettura
3. Disabilita temporaneamente OneDrive sync e riprova

## 🔄 Auto-Update

L'app verifica aggiornamenti all'avvio (ogni 24h). Se disponibile:

```
┌─────────────────────────────────────┐
│  Aggiornamento Disponibile          │
│  v1.1.0 → v1.2.0                    │
│                                      │
│  Novità:                            │
│  - Dashboard progetti               │
│  - Export Excel custom              │
│  - Bugfix chargeability             │
│                                      │
│  [Salta]        [Scarica e Installa]│
└─────────────────────────────────────┘
```

Download automatico da GitHub Releases.

## 📜 License

MIT License - vedi [LICENSE](LICENSE)

## 🤝 Contributing

Contributi benvenuti! Apri issue o PR su GitHub.

## 📧 Support

- Issues: https://github.com/DaveDev97/PmControlCenter/issues
- Docs: https://github.com/DaveDev97/PmControlCenter/wiki

---

**Sviluppato con** ❤️
