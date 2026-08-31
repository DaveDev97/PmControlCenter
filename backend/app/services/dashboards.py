"""Dashboard builders: turn ORM data into API dashboard payloads."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Allocation, Client, Contract, Financial, Opportunity, Resource
from app.schemas import (
    AccountDashboard,
    ContractDashboard,
    ContractKpiRow,
    ContractOut,
    HeatmapCell,
    KpiValue,
    MonthlyPoint,
    PeopleAllocationRow,
    PersonContractRow,
    PersonDashboard,
    PipelineStage,
    ResourceOut,
    TeamDashboard,
    TeamRosterRow,
)
from app.services import calc


# ---------------------------------------------------------------------------
# Allocation cost matrix helpers
# ---------------------------------------------------------------------------
async def _load_alloc_context(session: AsyncSession):
    """Load resources, allocations and financials once for team/person maths."""
    resources = (
        await session.scalars(select(Resource).options(selectinload(Resource.role)))
    ).all()
    allocations = (
        await session.scalars(
            select(Allocation).options(selectinload(Allocation.contract))
        )
    ).all()
    financials = (await session.scalars(select(Financial))).all()
    res_by_id = {r.id: r for r in resources}
    return resources, allocations, financials, res_by_id


def _filter_financials(
    financials: list[Financial],
    from_month: str | None = None,
    to_month: str | None = None,
    fy: str | None = None,
) -> list[Financial]:
    """Filter financials by date range or fiscal year."""
    if not (from_month or to_month or fy):
        return financials

    filtered = []
    for f in financials:
        month_key = f.month.strftime("%Y-%m")

        # FY filter (priority over from/to)
        if fy:
            year = int(fy)
            # Simple calendar year filter for MVP
            if f.month.year != year:
                continue

        # Date range filter
        if from_month and month_key < from_month:
            continue
        if to_month and month_key > to_month:
            continue

        filtered.append(f)

    return filtered


def _latest_actual_month(financials: list[Financial]) -> str | None:
    """Latest month key that has actual data (ignores forecast-only months)."""
    actual_months = [calc.month_key(f.month) for f in financials if f.is_actual]
    return max(actual_months) if actual_months else None


def _contract_month_revenue(financials: list[Financial]) -> dict[tuple[str, str], float]:
    """Map (contract_id, 'YYYY-MM') -> actual revenue for that month."""
    out: dict[tuple[str, str], float] = {}
    for f in financials:
        out[(f.contract_id, calc.month_key(f.month))] = (
            f.revenues_actual if f.is_actual else f.revenues_forecast
        )
    return out


def _contract_months(financials: list[Financial]) -> list[str]:
    return sorted({calc.month_key(f.month) for f in financials})


def _alloc_cost_by_contract_month(
    allocations: list[Allocation], res_by_id: dict[int, Resource], months: list[str]
) -> dict[tuple[str, str], float]:
    """Total allocated cost per (contract_id, month) across all resources."""
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for a in allocations:
        rate = calc.resource_rate(res_by_id[a.resource_id])
        for m in months:
            y, mo = int(m[:4]), int(m[5:7])
            from datetime import date

            if calc.allocation_active_in(a, date(y, mo, 1)):
                totals[(a.contract_id, m)] += a.days_per_month * rate
    return totals


# ---------------------------------------------------------------------------
# Account dashboard
# ---------------------------------------------------------------------------
async def build_account(
    session: AsyncSession,
    client_id: int | None,
    from_month: str | None = None,
    to_month: str | None = None,
    fy: str | None = None,
) -> AccountDashboard:
    q = select(Contract).options(
        selectinload(Contract.financials), selectinload(Contract.client)
    )
    if client_id is not None:
        q = q.where(Contract.client_id == client_id)
    contracts = (await session.scalars(q)).all()

    client_name = "Tutti i clienti"
    if client_id is not None:
        client = await session.get(Client, client_id)
        client_name = client.name if client else f"Client {client_id}"

    # Aggregate monthly across contracts.
    monthly_map: dict[str, dict] = {}
    tot_rev = tot_cost = 0.0
    tot_fc_rev = tot_fc_cost = 0.0
    contract_rows: list[ContractKpiRow] = []

    for c in contracts:
        # Apply filters to financials
        filtered_financials = _filter_financials(c.financials, from_month, to_month, fy)
        totals = calc.contract_totals(filtered_financials)
        tot_rev += totals["revenues"]
        tot_cost += totals["costs"]
        tot_fc_rev += totals["forecast_revenues"]
        tot_fc_cost += totals["forecast_costs"]
        contract_rows.append(
            ContractKpiRow(
                id=c.id,
                name=c.name,
                client_name=c.client.name if c.client else None,
                revenues=totals["revenues"],
                costs=totals["costs"],
                ci=totals["ci"],
                ci_pct=totals["ci_pct"],
                status=calc.ci_status(totals["ci_pct"]),
            )
        )
        for pt in calc.contract_month_series(filtered_financials):
            m = monthly_map.setdefault(
                pt["month"],
                {"revenues": 0.0, "costs": 0.0, "is_actual": True},
            )
            m["revenues"] += pt["revenues"]
            m["costs"] += pt["costs"]
            m["is_actual"] = m["is_actual"] and pt["is_actual"]

    monthly = [
        MonthlyPoint(
            month=k,
            revenues=round(v["revenues"], 2),
            costs=round(v["costs"], 2),
            ci=round(v["revenues"] - v["costs"], 2),
            ci_pct=round((v["revenues"] - v["costs"]) / v["revenues"], 4)
            if v["revenues"]
            else 0.0,
            is_actual=v["is_actual"],
        )
        for k, v in sorted(monthly_map.items())
    ]

    ci = tot_rev - tot_cost
    ci_pct = ci / tot_rev if tot_rev else 0.0
    # Forecast accuracy: how close forecast revenue is to actual (where both exist).
    fc_accuracy = 1 - abs(tot_fc_rev - tot_rev) / tot_rev if tot_rev else 0.0

    kpis = [
        KpiValue(label="Revenues YTD", value=round(tot_rev, 2), unit="EUR"),
        KpiValue(label="Costs YTD", value=round(tot_cost, 2), unit="EUR"),
        KpiValue(
            label="Contribution Income",
            value=round(ci, 2),
            unit="EUR",
            status=calc.ci_status(ci_pct),
        ),
        KpiValue(
            label="CI Margin",
            value=round(ci_pct, 4),
            unit="PCT",
            status=calc.ci_status(ci_pct),
        ),
    ]

    # Pipeline by quarter + stage.
    oq = select(Opportunity)
    if client_id is not None:
        contract_ids = [c.id for c in contracts]
        oq = oq.where(Opportunity.contract_id.in_(contract_ids))
    opps = (await session.scalars(oq)).all()
    pipe_map: dict[tuple[str, str], list[float]] = defaultdict(list)
    for o in opps:
        pipe_map[(o.quarter or "N/A", o.stage or "Lead")].append(o.estimated_value or 0.0)
    pipeline = [
        PipelineStage(quarter=q, stage=s, value=round(sum(v), 2), count=len(v))
        for (q, s), v in sorted(pipe_map.items())
    ]

    return AccountDashboard(
        client_id=client_id,
        client_name=client_name,
        contracts_count=len(contracts),
        opportunities_count=len(opps),
        kpis=kpis,
        monthly=monthly,
        pipeline=pipeline,
        contracts=contract_rows,
    )


# ---------------------------------------------------------------------------
# Contract dashboard
# ---------------------------------------------------------------------------
async def build_contract(
    session: AsyncSession,
    contract_id: str,
    from_month: str | None = None,
    to_month: str | None = None,
    fy: str | None = None,
) -> ContractDashboard | None:
    c = await session.get(
        Contract,
        contract_id,
        options=[selectinload(Contract.financials), selectinload(Contract.client)],
    )
    if c is None:
        return None

    # Apply filters to financials
    filtered_financials = _filter_financials(c.financials, from_month, to_month, fy)
    totals = calc.contract_totals(filtered_financials)
    monthly = [MonthlyPoint(**pt) for pt in calc.contract_month_series(filtered_financials)]

    # People allocated to this contract.
    allocations = (
        await session.scalars(
            select(Allocation)
            .where(Allocation.contract_id == contract_id)
            .options(selectinload(Allocation.resource).selectinload(Resource.role))
        )
    ).all()

    latest_month = _latest_actual_month(c.financials)
    month_rev = _contract_month_revenue(c.financials)
    # Total allocated cost on this contract in the latest month (for attribution).
    from datetime import date

    def alloc_cost(a: Allocation) -> float:
        return a.days_per_month * calc.resource_rate(a.resource)

    total_alloc_cost_latest = 0.0
    if latest_month:
        y, mo = int(latest_month[:4]), int(latest_month[5:7])
        total_alloc_cost_latest = sum(
            alloc_cost(a) for a in allocations if calc.allocation_active_in(a, date(y, mo, 1))
        )

    people: list[PeopleAllocationRow] = []
    for a in allocations:
        rate = calc.resource_rate(a.resource)
        mcost = round(a.days_per_month * rate, 2)
        # Attributed revenue (latest month) proportional to cost share.
        mrev = 0.0
        if latest_month and total_alloc_cost_latest:
            share = mcost / total_alloc_cost_latest
            mrev = round(month_rev.get((contract_id, latest_month), 0.0) * share, 2)
        people.append(
            PeopleAllocationRow(
                resource_id=a.resource_id,
                resource_name=a.resource.name,
                role=a.resource.role.name if a.resource.role else None,
                days_per_month=a.days_per_month,
                daily_rate=rate,
                utilization=round(a.days_per_month / settings.working_days_per_month, 4),
                monthly_cost=mcost,
                monthly_revenue=mrev,
            )
        )
    people.sort(key=lambda p: p.monthly_cost, reverse=True)

    avg_util = (
        round(sum(p.utilization for p in people) / len(people), 4) if people else 0.0
    )

    kpis = [
        KpiValue(label="Revenues", value=totals["revenues"], unit="EUR"),
        KpiValue(label="Total Costs", value=totals["costs"], unit="EUR"),
        KpiValue(
            label="Contribution Income",
            value=totals["ci"],
            unit="EUR",
            status=calc.ci_status(totals["ci_pct"]),
        ),
        KpiValue(
            label="CI Margin",
            value=totals["ci_pct"],
            unit="PCT",
            status=calc.ci_status(totals["ci_pct"]),
        ),
        KpiValue(label="Avg Utilization", value=avg_util, unit="PCT"),
        KpiValue(label="Billings", value=totals["billings"], unit="EUR"),
    ]

    cost_breakdown = {
        "payroll": totals["payroll"],
        "non_payroll": totals["non_payroll"],
        "capital": totals["capital"],
    }

    return ContractDashboard(
        contract=ContractOut(
            **{
                **{k: getattr(c, k) for k in ContractOut.model_fields if k != "client_name"},
                "client_name": c.client.name if c.client else None,
            }
        ),
        kpis=kpis,
        monthly=monthly,
        cost_breakdown=cost_breakdown,
        people=people,
    )


# ---------------------------------------------------------------------------
# Team dashboard
# ---------------------------------------------------------------------------
async def build_team(session: AsyncSession) -> TeamDashboard:
    resources, allocations, financials, res_by_id = await _load_alloc_context(session)
    months = _contract_months(financials)
    latest_month = _latest_actual_month(financials)
    month_rev = _contract_month_revenue(financials)
    alloc_cost_cm = _alloc_cost_by_contract_month(allocations, res_by_id, months)

    allocs_by_res: dict[int, list[Allocation]] = defaultdict(list)
    for a in allocations:
        allocs_by_res[a.resource_id].append(a)

    from datetime import date

    def month_date(m: str) -> date:
        return date(int(m[:4]), int(m[5:7]), 1)

    roster: list[TeamRosterRow] = []
    total_cost = 0.0
    total_rev = 0.0
    util_values: list[float] = []
    bench_count = 0

    for r in resources:
        r_allocs = allocs_by_res.get(r.id, [])
        rate = calc.resource_rate(r)
        # Latest-month utilization / cost / attributed revenue.
        util = cost = rev = 0.0
        contracts_active: list[str] = []
        if latest_month:
            md = month_date(latest_month)
            for a in r_allocs:
                if calc.allocation_active_in(a, md):
                    util += a.days_per_month / settings.working_days_per_month
                    a_cost = a.days_per_month * rate
                    cost += a_cost
                    contracts_active.append(a.contract_id)
                    denom = alloc_cost_cm.get((a.contract_id, latest_month), 0.0)
                    if denom:
                        share = a_cost / denom
                        rev += month_rev.get((a.contract_id, latest_month), 0.0) * share
        status = calc.util_status(util)
        if status == "bench":
            bench_count += 1
        util_values.append(util)
        total_cost += cost
        total_rev += rev
        roster.append(
            TeamRosterRow(
                resource_id=r.id,
                name=r.name,
                role=r.role.name if r.role else None,
                daily_rate=rate,
                utilization=round(util, 4),
                contracts_count=len(set(contracts_active)),
                contracts=sorted(set(contracts_active)),
                monthly_cost=round(cost, 2),
                monthly_revenue=round(rev, 2),
                margin=round(rev - cost, 2),
                status=status,
            )
        )

    roster.sort(key=lambda x: x.monthly_cost, reverse=True)
    avg_util = round(sum(util_values) / len(util_values), 4) if util_values else 0.0
    headcount = len(resources)
    bench_pct = round(bench_count / headcount, 4) if headcount else 0.0
    rev_per_person = round(total_rev / headcount, 2) if headcount else 0.0

    kpis = [
        KpiValue(label="Total Team Cost", value=round(total_cost, 2), unit="EUR"),
        KpiValue(label="Avg Utilization", value=avg_util, unit="PCT",
                 status="good" if avg_util >= settings.util_full_threshold else "warning"),
        KpiValue(label="Revenue / Person", value=rev_per_person, unit="EUR"),
        KpiValue(label="Bench", value=bench_pct, unit="PCT",
                 status="good" if bench_pct < 0.2 else "warning"),
    ]

    # Heatmap: utilization per resource per month.
    heatmap: list[HeatmapCell] = []
    for r in resources:
        r_allocs = allocs_by_res.get(r.id, [])
        for m in months:
            md = month_date(m)
            u = sum(
                a.days_per_month / settings.working_days_per_month
                for a in r_allocs
                if calc.allocation_active_in(a, md)
            )
            heatmap.append(HeatmapCell(resource_id=r.id, month=m, utilization=round(u, 4)))

    return TeamDashboard(kpis=kpis, roster=roster, heatmap=heatmap, months=months)


# ---------------------------------------------------------------------------
# Person dashboard
# ---------------------------------------------------------------------------
async def build_person(session: AsyncSession, resource_id: int) -> PersonDashboard | None:
    r = await session.get(Resource, resource_id, options=[selectinload(Resource.role)])
    if r is None:
        return None

    resources, allocations, financials, res_by_id = await _load_alloc_context(session)
    months = _contract_months(financials)
    month_rev = _contract_month_revenue(financials)
    alloc_cost_cm = _alloc_cost_by_contract_month(allocations, res_by_id, months)
    rate = calc.resource_rate(r)

    r_allocs = [a for a in allocations if a.resource_id == resource_id]

    from datetime import date

    def month_date(m: str) -> date:
        return date(int(m[:4]), int(m[5:7]), 1)

    # Per-contract latest snapshot rows.
    latest_month = _latest_actual_month(financials)
    contract_names = {c.id: c for c in (await session.scalars(select(Contract).options(selectinload(Contract.client)))).all()}
    rows: list[PersonContractRow] = []
    for a in r_allocs:
        c = contract_names.get(a.contract_id)
        mcost = round(a.days_per_month * rate, 2)
        mrev = 0.0
        if latest_month and calc.allocation_active_in(a, month_date(latest_month)):
            denom = alloc_cost_cm.get((a.contract_id, latest_month), 0.0)
            if denom:
                mrev = round(
                    month_rev.get((a.contract_id, latest_month), 0.0) * (mcost / denom), 2
                )
        rows.append(
            PersonContractRow(
                contract_id=a.contract_id,
                contract_name=c.name if c else a.contract_id,
                client_name=c.client.name if c and c.client else None,
                wbs=c.wbs_l1 if c else None,
                days_per_month=a.days_per_month,
                utilization=round(a.days_per_month / settings.working_days_per_month, 4),
                monthly_cost=mcost,
                monthly_revenue=mrev,
                start_date=a.start_date,
                end_date=a.end_date,
            )
        )

    # Monthly cost vs attributed revenue across the resource's active months.
    monthly: list[MonthlyPoint] = []
    total_cost_ytd = total_rev_ytd = total_days = 0.0
    util_vals: list[float] = []
    for m in months:
        md = month_date(m)
        mcost = mrev = mutil = mdays = 0.0
        for a in r_allocs:
            if calc.allocation_active_in(a, md):
                c_cost = a.days_per_month * rate
                mcost += c_cost
                mdays += a.days_per_month
                mutil += a.days_per_month / settings.working_days_per_month
                denom = alloc_cost_cm.get((a.contract_id, m), 0.0)
                if denom:
                    mrev += month_rev.get((a.contract_id, m), 0.0) * (c_cost / denom)
        if mcost or mrev:
            monthly.append(
                MonthlyPoint(
                    month=m,
                    revenues=round(mrev, 2),
                    costs=round(mcost, 2),
                    ci=round(mrev - mcost, 2),
                    ci_pct=round((mrev - mcost) / mrev, 4) if mrev else 0.0,
                    is_actual=True,
                )
            )
            util_vals.append(mutil)
        total_cost_ytd += mcost
        total_rev_ytd += mrev
        total_days += mdays

    current_util = util_vals[-1] if util_vals else 0.0
    avg_util = round(sum(util_vals) / len(util_vals), 4) if util_vals else 0.0

    kpis = [
        KpiValue(label="Current Utilization", value=round(current_util, 4), unit="PCT",
                 status=("good" if calc.util_status(current_util) == "full" else "warning")),
        KpiValue(label="Avg Utilization YTD", value=avg_util, unit="PCT"),
        KpiValue(label="Total Cost YTD", value=round(total_cost_ytd, 2), unit="EUR"),
        KpiValue(label="Total Revenue YTD", value=round(total_rev_ytd, 2), unit="EUR"),
        KpiValue(label="Margin Contribution", value=round(total_rev_ytd - total_cost_ytd, 2),
                 unit="EUR", status="good" if total_rev_ytd >= total_cost_ytd else "bad"),
        KpiValue(label="Days Worked YTD", value=round(total_days, 1), unit="NUM"),
    ]

    contract_mix = [
        {"name": row.contract_name, "value": row.monthly_cost} for row in rows if row.monthly_cost
    ]

    return PersonDashboard(
        resource=ResourceOut(
            **{
                **{k: getattr(r, k) for k in ResourceOut.model_fields if k != "role_name"},
                "role_name": r.role.name if r.role else None,
            }
        ),
        kpis=kpis,
        allocations=rows,
        monthly=monthly,
        contract_mix=contract_mix,
    )
