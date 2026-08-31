"""Shared calculation helpers used by dashboard services.

All heavy aggregation happens here in plain Python over already-loaded ORM
objects. Datasets are small (single-account scale) so this is both simple and
correct; swap for SQL aggregation only if volume grows.
"""
from __future__ import annotations

from datetime import date

from app.core.config import settings
from app.models import Allocation, Contract, Financial, Resource


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def allocation_active_in(alloc: Allocation, d: date) -> bool:
    """True if an allocation is active in the month starting at *d*."""
    if alloc.start_date and d < _first_of_month(alloc.start_date):
        return False
    if alloc.end_date and d > _last_relevant_month(alloc.end_date):
        return False
    return True


def _first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _last_relevant_month(d: date) -> date:
    return date(d.year, d.month, 1)


def allocation_monthly_cost(alloc: Allocation, rate: float) -> float:
    """Cost of one allocation for a single month = days * daily_rate."""
    return round(alloc.days_per_month * rate, 2)


def contract_month_series(fins: list[Financial]) -> list[dict]:
    """Return a chronologically ordered list of monthly points for a contract."""
    points: list[dict] = []
    for f in sorted(fins, key=lambda x: x.month):
        rev = f.revenues_actual if f.is_actual else f.revenues_forecast
        cost = f.total_costs_actual if f.is_actual else f.total_costs_forecast
        ci = rev - cost
        points.append(
            {
                "month": month_key(f.month),
                "revenues": round(rev, 2),
                "costs": round(cost, 2),
                "ci": round(ci, 2),
                "ci_pct": round(ci / rev, 4) if rev else 0.0,
                "is_actual": f.is_actual,
            }
        )
    return points


def contract_totals(fins: list[Financial]) -> dict:
    """Aggregate actual + forecast totals for a contract."""
    rev = sum(f.revenues_actual for f in fins)
    cost = sum(f.total_costs_actual for f in fins)
    billings = sum(f.billings_actual for f in fins)
    payroll = sum(f.payroll_costs_actual for f in fins)
    non_payroll = sum(f.non_payroll_costs_actual for f in fins)
    capital = sum(f.capital_charges_actual for f in fins)
    fc_rev = sum(f.revenues_forecast for f in fins)
    fc_cost = sum(f.total_costs_forecast for f in fins)
    ci = rev - cost
    return {
        "revenues": round(rev, 2),
        "costs": round(cost, 2),
        "billings": round(billings, 2),
        "payroll": round(payroll, 2),
        "non_payroll": round(non_payroll, 2),
        "capital": round(capital, 2),
        "ci": round(ci, 2),
        "ci_pct": round(ci / rev, 4) if rev else 0.0,
        "forecast_revenues": round(fc_rev, 2),
        "forecast_costs": round(fc_cost, 2),
    }


def ci_status(ci_pct: float) -> str:
    """Traffic-light status for CCI margin.

    Per documento operativo:
    - Verde (good): CCI ≥ 35%
    - Giallo (warning): CCI 30-35%
    - Rosso (bad): CCI < 30%
    """
    if ci_pct >= settings.cci_target_threshold:  # ≥ 35%
        return "good"
    if ci_pct >= settings.cci_warning_threshold:  # 30-35%
        return "warning"
    return "bad"  # < 30%


def util_status(util: float) -> str:
    if util >= settings.util_full_threshold:
        return "full"
    if util >= settings.util_bench_threshold:
        return "partial"
    return "bench"


def resource_rate(resource: Resource) -> float:
    return resource.daily_rate or 0.0


def contract_display_name(contract: Contract) -> str:
    return f"{contract.id} - {contract.name}"
