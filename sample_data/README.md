# Sample Data - Excel Schema

Questi file Excel contengono dati **anonimizzati** per testing/demo dell'applicazione.

## 📁 File Struttura

### 1. contracts_financials.xlsx

#### Sheet: Contracts
| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| contract_id | String | ID univoco contratto | PROJ-001 |
| client_name | String | Nome cliente | Alpha Corp |
| contract_name | String | Nome contratto | Alpha - Security Services |
| service_group | String | Gruppo servizio | IMS, AMS, Security |
| wbs_l1 | String | WBS livello 1 | WBS001 |
| wbs_l2 | String | WBS livello 2 | SUB001 |
| description | String | Descrizione | Managed security services... |
| contract_type | String | Tipo | T&M, Fixed Price, Capped T&M |
| fiscal_year | String | Anno fiscale | 2026 |
| start_date | Date | Data inizio | 2026-01-01 |
| end_date | Date | Data fine | 2026-12-31 |
| initial_budget | Float | Budget iniziale (EUR) | 950000.00 |
| status | String | Stato | active, closed |

#### Sheet: Financials
| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| contract_id | String | Riferimento contratto | PROJ-001 |
| month | Date | Mese (primo giorno) | 2026-01-01 |
| fiscal_quarter | String | Quarter fiscale | Q1, Q2, Q3, Q4 |
| is_actual | Boolean | Actual vs Forecast | TRUE, FALSE |
| billings_actual | Float | Fatturato actual | 78000.00 |
| revenues_actual | Float | Ricavi actual | 78000.00 |
| payroll_costs_actual | Float | Costi personale actual | 52000.00 |
| non_payroll_costs_actual | Float | Costi non personale actual | 3000.00 |
| capital_charges_actual | Float | Ammortamenti actual | 2000.00 |
| *_forecast | Float | Stesse colonne per forecast | ... |

#### Sheet: Resources
| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| name | String | Nome risorsa | Manager A |
| email | String | Email | manager.a@company.com |
| role | String | Ruolo | Manager, Senior Consultant |
| daily_rate | Float | Tariffa giornaliera | 800.00 |
| loaded_cost_hourly | Float | Costo orario caricato | 95.00 |
| chargeability | Float | Chargeability target | 0.85 |
| status | String | Stato | active, inactive |
| hire_date | Date | Data assunzione | 2024-01-01 |

---

### 2. allocations.xlsx

#### Sheet: Allocations
| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| resource_name | String | Nome risorsa | Manager A |
| resource_email | String | Email risorsa | manager.a@company.com |
| contract_id | String | ID contratto | PROJ-001 |
| utilization | Float | Utilizzo (0-1) | 0.85 |
| days_per_month | Float | Giorni/mese | 18.0 |
| start_date | Date | Data inizio allocazione | 2026-01-01 |
| end_date | Date | Data fine allocazione | 2026-12-31 |

---

### 3. opportunities.xlsx

#### Sheet: Opportunities
| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| opp_id_mms | String | ID opportunità MMS | OPP-0001 |
| contract_id | String | Contratto collegato (se CloseWon) | PROJ-001 |
| name | String | Nome opportunità | Alpha Security Extension |
| description | String | Descrizione | Extension servizi SOC |
| legal_entity | String | Legal entity cliente | Alpha Corp S.p.A. |
| fiscal_year | String | Anno fiscale | 2026 |
| close_date | Date | Data chiusura prevista | 2026-10-31 |
| quarter | String | Quarter | Q1, Q2, Q3, Q4 |
| pds_status | String | Status PDS | Da inviare, Inviata, Approvata CVS |
| acn_tool_status | String | Status ACN Tool | Todo, In progress, Done |
| mms_status | String | Status MMS | Lead, Qualified, Proposal, CloseWon |
| stage | String | Stage opportunità | Lead, Qualified, Proposal, CloseWon |
| estimated_value | Float | Valore stimato (EUR) | 120000.00 |
| probability | Float | Probabilità (0-1) | 0.6 |
| notes | String | Note (opzionale) | Follow-up Q3 |

---

## 🔐 Anonimizzazione

Questi dati sono **completamente fittizi**:

- ✅ Nomi persone → "Manager A", "Senior Consultant 1"
- ✅ Email → "role.suffix@company.com"
- ✅ Clienti → "Alpha Corp", "Beta Industries"
- ✅ Contratti → "PROJ-001", "PROJ-002"
- ✅ Importi → scalati random (0.7x - 1.3x)

**Nessun dato reale incluso.**

---

## 🎯 Utilizzo

1. **Setup Wizard**: Punta alla cartella `sample_data/`
2. **App carica** i 3 Excel automaticamente
3. **Dashboard popolate** con dati demo
4. **Modifica DD/Overlay** → salvato in `pm_overlay.json`

---

**Generato da:** `scripts/anonymize_data.py`
**Data:** {datetime.now().strftime('%Y-%m-%d')}
**Versione:** 1.0.0
