"""Load PM Control Center data from Excel workbooks into the SQLite database.

Source layout (see ``sample_data/README.md`` for the full column schema):

* ``contracts_financials.xlsx``  -> sheets ``Contracts``, ``Financials``, ``Resources``
* ``allocations.xlsx``           -> sheet  ``Allocations``
* ``opportunities.xlsx``         -> sheet  ``Opportunities`` (optional)

The reader is intentionally tolerant: missing optional columns fall back to
sensible defaults, ``NaN``/blank cells become ``None``, and unknown resource or
contract references in the allocations/opportunities sheets are skipped rather
than aborting the whole import.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Allocation,
    Client,
    Contract,
    Financial,
    Opportunity,
    Resource,
    Role,
)

REQUIRED_FILES = ("contracts_financials.xlsx", "allocations.xlsx")
OPTIONAL_FILES = ("opportunities.xlsx",)


# --------------------------------------------------------------------------- #
# Cell coercion helpers
# --------------------------------------------------------------------------- #
def _is_blank(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or value == ""


def _str(value) -> str | None:
    if _is_blank(value):
        return None
    return str(value).strip()


def _float(value, default: float = 0.0) -> float:
    if _is_blank(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value, default: bool = True) -> bool:
    if _is_blank(value):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "si", "sì"}
    return bool(value)


def _date(value) -> date | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except (ValueError, TypeError):
        return None


def _month(value) -> date | None:
    """Coerce a value to the first day of its month."""
    d = _date(value)
    return d.replace(day=1) if d else None


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
class ExcelDataLoader:
    """Loads data from Excel files into the (in-memory) database."""

    def validate_folder(self, data_folder: Path) -> dict:
        """Check required files exist in ``data_folder``.

        Returns ``{"valid": bool, "missing": [...], "found": [...], "optional": [...]}``.
        """
        data_folder = Path(data_folder)
        found, missing, optional = [], [], []
        if not data_folder.exists() or not data_folder.is_dir():
            return {
                "valid": False,
                "missing": list(REQUIRED_FILES),
                "found": [],
                "optional": [],
                "error": f"Folder not found: {data_folder}",
            }
        for name in REQUIRED_FILES:
            (found if (data_folder / name).exists() else missing).append(name)
        for name in OPTIONAL_FILES:
            if (data_folder / name).exists():
                optional.append(name)
        return {"valid": not missing, "missing": missing, "found": found, "optional": optional}

    async def load_all(self, data_folder: Path, session: AsyncSession) -> dict:
        """Load every workbook found in ``data_folder`` into ``session``.

        Assumes the tables are already empty (call ``reset_db`` first). Returns a
        dict of inserted row counts per entity.
        """
        data_folder = Path(data_folder)
        counts = {
            "clients": 0,
            "contracts": 0,
            "resources": 0,
            "roles": 0,
            "financials": 0,
            "allocations": 0,
            "opportunities": 0,
        }

        cf_path = data_folder / "contracts_financials.xlsx"
        sheets = pd.read_excel(cf_path, sheet_name=None)  # dict of DataFrames
        contracts_df = sheets.get("Contracts")
        financials_df = sheets.get("Financials")
        resources_df = sheets.get("Resources")

        # --- Clients + Contracts ---
        client_ids: dict[str, int] = {}
        if contracts_df is not None:
            for _, row in contracts_df.iterrows():
                client_name = _str(row.get("client_name")) or "Unknown"
                if client_name not in client_ids:
                    client = Client(name=client_name, industry=_str(row.get("industry")))
                    session.add(client)
                    await session.flush()
                    client_ids[client_name] = client.id
                    counts["clients"] += 1

                contract_id = _str(row.get("contract_id"))
                if not contract_id:
                    continue
                session.add(
                    Contract(
                        id=contract_id,
                        client_id=client_ids[client_name],
                        name=_str(row.get("contract_name")) or contract_id,
                        service_group=_str(row.get("service_group")),
                        wbs_l1=_str(row.get("wbs_l1")),
                        wbs_l2=_str(row.get("wbs_l2")),
                        description=_str(row.get("description")),
                        contract_type=_str(row.get("contract_type")) or "T&M",
                        fiscal_year=_str(row.get("fiscal_year")),
                        start_date=_date(row.get("start_date")),
                        end_date=_date(row.get("end_date")),
                        initial_budget=_float(row.get("initial_budget"), default=None)
                        if not _is_blank(row.get("initial_budget"))
                        else None,
                        status=_str(row.get("status")) or "active",
                    )
                )
                counts["contracts"] += 1
            await session.flush()

        # --- Roles + Resources ---
        resource_ids: dict[str, int] = {}
        if resources_df is not None:
            role_ids: dict[str, int] = {}
            for _, row in resources_df.iterrows():
                name = _str(row.get("name"))
                if not name:
                    continue
                role_name = _str(row.get("role"))
                role_id = None
                if role_name:
                    if role_name not in role_ids:
                        role = Role(name=role_name, default_rate=_float(row.get("daily_rate"), None))
                        session.add(role)
                        await session.flush()
                        role_ids[role_name] = role.id
                        counts["roles"] += 1
                    role_id = role_ids[role_name]

                resource = Resource(
                    name=name,
                    email=_str(row.get("email")),
                    role_id=role_id,
                    daily_rate=_float(row.get("daily_rate")),
                    loaded_cost_hourly=_float(row.get("loaded_cost_hourly"), None)
                    if not _is_blank(row.get("loaded_cost_hourly"))
                    else None,
                    chargeability=_float(row.get("chargeability"), 0.80),
                    status=_str(row.get("status")) or "active",
                    hire_date=_date(row.get("hire_date")),
                )
                session.add(resource)
                await session.flush()
                resource_ids[name] = resource.id
                if resource.email:
                    resource_ids[resource.email.lower()] = resource.id
                counts["resources"] += 1

        # --- Financials ---
        if financials_df is not None:
            valid_contracts = await self._contract_ids(session)
            for _, row in financials_df.iterrows():
                contract_id = _str(row.get("contract_id"))
                month = _month(row.get("month"))
                if not contract_id or month is None or contract_id not in valid_contracts:
                    continue
                session.add(
                    Financial(
                        contract_id=contract_id,
                        month=month,
                        fiscal_quarter=_str(row.get("fiscal_quarter")),
                        is_actual=_bool(row.get("is_actual")),
                        billings_actual=_float(row.get("billings_actual")),
                        billings_forecast=_float(row.get("billings_forecast")),
                        revenues_actual=_float(row.get("revenues_actual")),
                        revenues_forecast=_float(row.get("revenues_forecast")),
                        payroll_costs_actual=_float(row.get("payroll_costs_actual")),
                        payroll_costs_forecast=_float(row.get("payroll_costs_forecast")),
                        non_payroll_costs_actual=_float(row.get("non_payroll_costs_actual")),
                        non_payroll_costs_forecast=_float(row.get("non_payroll_costs_forecast")),
                        capital_charges_actual=_float(row.get("capital_charges_actual")),
                        capital_charges_forecast=_float(row.get("capital_charges_forecast")),
                    )
                )
                counts["financials"] += 1

        # --- Allocations ---
        alloc_path = data_folder / "allocations.xlsx"
        if alloc_path.exists():
            valid_contracts = await self._contract_ids(session)
            alloc_df = pd.read_excel(alloc_path, sheet_name=0)
            for _, row in alloc_df.iterrows():
                res_name = _str(row.get("resource_name"))
                res_email = _str(row.get("resource_email"))
                contract_id = _str(row.get("contract_id"))
                resource_id = resource_ids.get(res_name)
                if resource_id is None and res_email:
                    resource_id = resource_ids.get(res_email.lower())
                if resource_id is None or contract_id not in valid_contracts:
                    continue
                session.add(
                    Allocation(
                        resource_id=resource_id,
                        contract_id=contract_id,
                        utilization=_float(row.get("utilization"), 1.0),
                        days_per_month=_float(row.get("days_per_month")),
                        start_date=_date(row.get("start_date")),
                        end_date=_date(row.get("end_date")),
                    )
                )
                counts["allocations"] += 1

        # --- Opportunities (optional) ---
        opp_path = data_folder / "opportunities.xlsx"
        if opp_path.exists():
            valid_contracts = await self._contract_ids(session)
            opp_df = pd.read_excel(opp_path, sheet_name=0)
            for _, row in opp_df.iterrows():
                name = _str(row.get("name"))
                if not name:
                    continue
                contract_id = _str(row.get("contract_id"))
                if contract_id not in valid_contracts:
                    contract_id = None
                stage = _str(row.get("stage")) or "Lead"
                session.add(
                    Opportunity(
                        opp_id_mms=_str(row.get("opp_id_mms")),
                        contract_id=contract_id,
                        name=name,
                        description=_str(row.get("description")),
                        legal_entity=_str(row.get("legal_entity")),
                        fiscal_year=_str(row.get("fiscal_year")),
                        close_date=_date(row.get("close_date")),
                        quarter=_str(row.get("quarter")),
                        pds_status=_str(row.get("pds_status")),
                        acn_tool_status=_str(row.get("acn_tool_status")),
                        mms_status=_str(row.get("mms_status")) or stage,
                        stage=stage,
                        estimated_value=_float(row.get("estimated_value")),
                        probability=_float(row.get("probability")),
                        notes=_str(row.get("notes")),
                    )
                )
                counts["opportunities"] += 1

        await session.commit()
        return counts

    async def _contract_ids(self, session: AsyncSession) -> set[str]:
        rows = await session.scalars(select(Contract.id))
        return set(rows.all())
