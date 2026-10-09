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


def _fy_date_range(fy: str) -> tuple[date, date]:
    """Accenture FY date range: FY2027 = 1 Sep 2026 – 31 Aug 2027."""
    year = int(fy)
    from datetime import date
    return date(year - 1, 9, 1), date(year, 8, 31)


def _fy_label(fy: str) -> str:
    """Convert year string '2027' → opportunity fiscal_year label 'FY27'."""
    return f"FY{fy[2:]}"


def _filter_financials(
    financials: list[Financial],
    from_month: str | None = None,
    to_month: str | None = None,
    fy: str | None = None,
) -> list[Financial]:
    """Filter financials by date range or Accenture fiscal year (Sep–Aug)."""
    if not (from_month or to_month or fy):
        return financials

    from datetime import date

    fy_start: date | None = None
    fy_end: date | None = None
    if fy:
        fy_start, fy_end = _fy_date_range(fy)

    filtered = []
    for f in financials:
        month_str = f.month.strftime("%Y-%m")

        # Accenture FY filter (Sep–Aug)
        if fy_start and fy_end:
            if not (fy_start <= f.month <= fy_end):
                continue

        # Date range filter
        if from_month and month_str < from_month:
            continue
        if to_month and month_str > to_month:
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
    from datetime import date

    today = date.today()

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

    # FY date range for costs-to-date and opportunity Sales filter.
    fy_start: date | None = None
    fy_end: date | None = None
    if fy:
        fy_start, fy_end = _fy_date_range(fy)

    # Aggregate monthly across contracts.
    monthly_map: dict[str, dict] = {}
    tot_rev = tot_cost = 0.0
    costi_a_oggi = 0.0  # actual costs incurred up to today within FY
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
        # Costs actually incurred: only months up to today
        costi_a_oggi += sum(
            f.total_costs_actual for f in filtered_financials if f.month <= today
        )
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

    # Pipeline by quarter + stage + Sales KPI (booked opps in the selected FY).
    oq = select(Opportunity)
    if client_id is not None:
        contract_ids = [c.id for c in contracts]
        oq = oq.where(Opportunity.contract_id.in_(contract_ids))
    opps = (await session.scalars(oq)).all()

    # Sales = total estimated_value of booked opportunities in the selected FY.
    # Booked = stage CloseWon/3B or mms_status_code 3B/close-won.
    BOOKED_STAGES = {"CloseWon", "3B"}
    BOOKED_MMS = {"3B", "close-won", "CloseWon"}
    fy_label = _fy_label(fy) if fy else None
    sales = 0.0
    pipe_map: dict[tuple[str, str], list[float]] = defaultdict(list)
    for o in opps:
        is_booked = (o.stage in BOOKED_STAGES) or (o.mms_status_code in BOOKED_MMS)
        if is_booked:
            # Match FY by stored fiscal_year label or by close_date within FY range
            opp_in_fy = (
                (fy_label and o.fiscal_year == fy_label)
                or (fy_start and fy_end and o.close_date and fy_start <= o.close_date <= fy_end)
                or (not fy)  # no FY filter → count all booked
            )
            if opp_in_fy:
                sales += o.estimated_value or 0.0
        pipe_map[(o.quarter or "N/A", o.stage or "Lead")].append(o.estimated_value or 0.0)
    pipeline = [
        PipelineStage(quarter=q, stage=s, value=round(sum(v), 2), count=len(v))
        for (q, s), v in sorted(pipe_map.items())
    ]

    kpis = [
        KpiValue(label="Sales", value=round(sales, 2), unit="EUR"),
        KpiValue(label="Revenue", value=round(tot_rev, 2), unit="EUR"),
        KpiValue(label="Costi sostenuti", value=round(costi_a_oggi, 2), unit="EUR"),
        KpiValue(
            label="CI%",
            value=round(ci_pct, 4),
            unit="PCT",
            status=calc.ci_status(ci_pct),
        ),
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

    from app.services.team_allocation import status_by_name

    alloc_status = status_by_name()
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
        # Status and utilization come from the person's own %Charg and the hours
        # booked in "Costi vs Forecast" this month (see team_allocation), not from
        # the synthetic allocations, which produced false "bench" results.
        alloc = alloc_status.get(r.name)
        if alloc is not None:
            util = (alloc["hours"] or 0) / alloc["month_hours"] if alloc.get("month_hours") else 0.0
            status = {"ok": "full", "bench": "bench", "over": "bad"}.get(alloc["status"], "partial")
        else:
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
    known = [s for s in alloc_status.values() if s["status"] != "nd"]
    ok_pct = round(sum(1 for s in known if s["status"] == "ok") / len(known), 4) if known else 0.0
    rev_per_person = round(total_rev / headcount, 2) if headcount else 0.0

    kpis = [
        KpiValue(label="Total Team Cost", value=round(total_cost, 2), unit="EUR"),
        # Share of people allocated as planned by their own %Charg (see team_allocation);
        # an average utilization would flag people who are partly on "Other" projects.
        KpiValue(label="Allocate correttamente", value=ok_pct, unit="PCT",
                 status="good" if ok_pct >= 0.9 else "warning"),
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
