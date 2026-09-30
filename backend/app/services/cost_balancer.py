"""Cost Balancer: cost space still usable without breaking the CCI target.

For a contract (or the whole account) over a fiscal year, from the official P&L
in the ``Contracts`` sheet:

* revenue allocated  = actual + forecast revenue of the FY months;
* costs allocated    = actual (consumed) + forecast (planned) total costs;
* CCI %              = (revenue - costs) / revenue;
* max costs          = revenue x (1 - CCI target)   (target 35% -> 65% of revenue);
* **residual space** = max costs - costs allocated.

A positive residual is cost that can still be staffed while keeping the target
margin; a negative one is the cost to cut (or the extra revenue x 65% needed).
The residual is not "revenue - costs": it already reserves the 35% margin.
"""
from __future__ import annotations

from datetime import date

from app.core.config import settings
from app.services.cci import _parse_contracts, fiscal_year_of
from app.services.workbook_cache import cached_sheets, find_sheet


def _fy_of(month: str) -> int:
    return fiscal_year_of(date(int(month[:4]), int(month[5:7]), 1))


def _figures(months: list[dict], target: float, today: str, fy_total: dict | None = None) -> dict:
    rev_fc = sum(m["revenue"] for m in months if m["tipo"] == "forecast")
    cost_fc = sum(m["total_cost"] for m in months if m["tipo"] == "forecast")
    if fy_total and (fy_total.get("revenue") or fy_total.get("total_cost")):
        # The sheet's FY column also covers months before the first monthly column
        # ("Previous"): use it for the totals, the actual part being the rest.
        rev_act = fy_total["revenue"] - rev_fc
        cost_act = fy_total["total_cost"] - cost_fc
    else:
        rev_act = sum(m["revenue"] for m in months if m["tipo"] == "actual")
        cost_act = sum(m["total_cost"] for m in months if m["tipo"] == "actual")
    revenue, costs = rev_act + rev_fc, cost_act + cost_fc
    max_costs = revenue * (1 - target)
    remaining = [m for m in months if m["tipo"] == "forecast" and m["month"] >= today]
    rem_rev = sum(m["revenue"] for m in remaining)
    rem_cost = sum(m["total_cost"] for m in remaining)
    residual = max_costs - costs
    return {
        "revenue": round(revenue, 2),
        "revenue_actual": round(rev_act, 2),
        "revenue_forecast": round(rev_fc, 2),
        "costs": round(costs, 2),
        "costs_actual": round(cost_act, 2),
        "costs_forecast": round(cost_fc, 2),
        "cci": round(revenue - costs, 2),
        "cci_pct": round((revenue - costs) / revenue, 4) if revenue else None,
        "target": target,
        "max_costs": round(max_costs, 2),
        "residual": round(residual, 2),
        # If negative: extra revenue that would restore the target at current costs.
        "revenue_needed": round(-residual / (1 - target), 2) if residual < 0 else 0.0,
        "remaining_months": len(remaining),
        "remaining_revenue": round(rem_rev, 2),
        "remaining_costs": round(rem_cost, 2),
        "residual_per_month": round(residual / len(remaining), 2) if remaining else None,
    }


def _monthly(months: list[dict], target: float) -> list[dict]:
    out = []
    for m in months:
        max_costs = m["revenue"] * (1 - target)
        out.append({"month": m["month"], "tipo": m["tipo"], "revenue": m["revenue"],
                    "costs": m["total_cost"], "cci_pct": m["cci_pct"],
                    "max_costs": round(max_costs, 2), "residual": round(max_costs - m["total_cost"], 2)})
    return out


def balance_overview(client_by_contract: dict[str, str], fy: str | None = None,
                     today: date | None = None) -> dict:
    """Per-contract and account-level cost space for ``fy`` ("FY27"; default: current FY)."""
    target = settings.cci_target_threshold
    today = today or date.today()
    fy_num = int("20" + fy[-2:]) if fy else fiscal_year_of(today)
    rows = find_sheet(cached_sheets(), lambda t: t == "contracts") or []
    contracts = _parse_contracts(rows)
    all_fys = sorted({_fy_of(m["month"]) for c in contracts for m in c["months"]})
    now = today.strftime("%Y-%m")

    fy_label = f"FY{str(fy_num)[-2:]}"
    out, account_months = [], []
    acc_total = {"revenue": 0.0, "total_cost": 0.0}
    all_have_total = True
    for c in contracts:
        months = [m for m in c["months"] if _fy_of(m["month"]) == fy_num]
        account_months.extend(months)
        # First aggregate column labelled exactly like the FY (e.g. "FY26").
        fy_total = next((a for a in c["aggregates"] if a["label"].upper() == fy_label), None)
        if fy_total and (fy_total["revenue"] or fy_total["total_cost"]):
            acc_total["revenue"] += fy_total["revenue"]
            acc_total["total_cost"] += fy_total["total_cost"]
        else:
            all_have_total = False
        out.append({"id": c["id"], "description": c["description"], "wbs": c["wbs"],
                    "client": client_by_contract.get(c["id"]),
                    **_figures(months, target, now, fy_total), "months": _monthly(months, target)})

    # Account = sum of contracts, month by month.
    by_month: dict[tuple[str, str], dict] = {}
    for m in account_months:
        agg = by_month.setdefault((m["month"], m["tipo"]), {"month": m["month"], "tipo": m["tipo"],
                                                           "revenue": 0.0, "total_cost": 0.0})
        agg["revenue"] += m["revenue"]
        agg["total_cost"] += m["total_cost"]
    acc_months = []
    for agg in sorted(by_month.values(), key=lambda a: a["month"]):
        agg["cci_pct"] = round((agg["revenue"] - agg["total_cost"]) / agg["revenue"], 4) if agg["revenue"] else None
        acc_months.append(agg)
    return {
        "fy": f"FY{str(fy_num)[-2:]}",
        "available_fys": [f"FY{str(y)[-2:]}" for y in all_fys],
        "target": target,
        "account": {**_figures(acc_months, target, now, acc_total if all_have_total and contracts else None),
                    "months": _monthly(acc_months, target)},
        "contracts": out,
    }
