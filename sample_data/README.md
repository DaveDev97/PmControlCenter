# Sample Data — `security_financials.xlsx`

Questo file è un **clone anonimizzato** del workbook reale
`BNL_Security_Financials_v02.xlsx`, generato da
[`scripts/anonymize_data.py`](../scripts/anonymize_data.py).

## Principio: stessa struttura, solo valori finti

Il clone mantiene **esattamente la stessa struttura e forma** dell'originale:
tutti i **16 fogli**, lo stesso layout, le stesse intestazioni e posizioni di
colonna. Vengono anonimizzati **solo i valori**:

| Categoria | Trasformazione |
|-----------|----------------|
| Nomi persone (`paolo.zinzi`, …) | nomi fittizi coerenti (`marco.rossi`) |
| Referenti commerciali (col. *Ref Name*) | nomi fittizi |
| Clienti / legal entity (BNL, Findomestic, …) | brand fittizi (AlphaBank, BetaCredit, …) |
| Importi economici (ricavi, costi, tariffe) | scalati con **un unico fattore globale** → i rapporti (es. CCI %) restano invariati |
| Identificatori (Opp ID, ODA, CCP, WBS, n° contratto) | codici fittizi della stessa lunghezza |

Le formule vengono "congelate" al loro valore (anonimizzato), così il file non
espone mai una cifra reale tramite una cache e viene letto in modo identico.

> ⚠️ Nessun dato reale è incluso: nomi, clienti, importi e ID sono tutti fittizi.

## Fogli letti dall'applicazione

Anche se il file contiene tutti i 16 fogli, l'app ne usa tre:

| Foglio | Uso |
|--------|-----|
| `Contracts` | Contratti + Financials mensili (blocchi per-contratto: header `<numero> - <nome>`, riga WBS, righe metriche Billing/Revenue/Payroll/Non Payroll/Capital Charge × colonne mese) |
| `Costi vs Forecast` | Risorse (colonne `Resource`, `LC`, `%Charg`) + allocazioni |
| `Opp. FY25/FY26/FY27` | Opportunità (intestazioni: Contract, PDS Status, MMS Status, Close Date, Opp ID MMS, WBS, Project, Ref Name, Revenues, …) |

## Rigenerare il clone

```bash
python scripts/anonymize_data.py [SORGENTE.xlsx] [OUTPUT.xlsx]
# default: ../BNL_Security_Financials_v02.xlsx -> sample_data/security_financials.xlsx
```

## Utilizzo nell'app

1. **Setup Wizard** → seleziona la cartella che contiene `security_financials.xlsx`
2. L'app carica i dati in SQLite in-memory
3. Le modifiche utente (es. Due Diligence) vengono salvate in `pm_overlay.json`
