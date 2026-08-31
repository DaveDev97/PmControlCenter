"""Cost balancing service - auto-optimization of cost distribution."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.models import Contract, Financial
from app.services import calc


async def propose_cost_rebalancing(
    contract_id: str, session: AsyncSession
) -> schemas.CostBalanceProposal:
    """
    Propose optimized cost distribution across forecast months.

    Algorithm:
    1. Load contract financials (actual + forecast)
    2. Calculate available cost space per month = Revenue - Target_CI
    3. Distribute costs to:
       - Maximize utilization (aim for 80-100%)
       - Keep CI margin above threshold (20%)
       - Smooth cost curve (avoid spikes)
    4. Return proposed vs current monthly costs
    """
    # Load contract with financials
    result = await session.execute(
        select(Contract)
        .where(Contract.id == contract_id)
        .options(selectinload(Contract.financials))
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise ValueError(f"Contract {contract_id} not found")

    financials = sorted(contract.financials, key=lambda f: f.month)

    # Split actual vs forecast
    actual_months = [f for f in financials if f.is_actual]
    forecast_months = [f for f in financials if not f.is_actual]

    if not forecast_months:
        # No forecast months to rebalance
        return schemas.CostBalanceProposal(
            contract_id=contract_id,
            contract_name=contract.name,
            months=[],
            current_costs=[],
            proposed_costs=[],
            current_revenues=[],
            ci_current=0.0,
            ci_proposed=0.0,
            ci_pct_current=0.0,
            ci_pct_proposed=0.0,
            reason="No forecast months available for rebalancing",
        )

    # Extract current state
    months = [calc.month_key(f.month) for f in forecast_months]
    current_costs = [f.total_costs_forecast for f in forecast_months]
    revenues = [f.revenues_forecast for f in forecast_months]

    # Calculate total available cost space
    total_revenue_forecast = sum(revenues)
    target_ci_margin = 0.30  # 30% target CI margin
    available_cost_space = total_revenue_forecast * (1 - target_ci_margin)

    # Current totals
    current_total_costs = sum(current_costs)
    current_ci = total_revenue_forecast - current_total_costs
    current_ci_pct = current_ci / total_revenue_forecast if total_revenue_forecast else 0

    # Proposed: distribute costs evenly (smooth curve) within budget
    # Cap total costs at available space
    if current_total_costs > available_cost_space:
        # Need to reduce costs
        proposed_total = available_cost_space
        reason = (
            f"Reduced total forecast costs from €{current_total_costs:,.0f} "
            f"to €{proposed_total:,.0f} to achieve 30% CI target margin"
        )
    else:
        # Costs are within budget; smooth distribution
        proposed_total = current_total_costs
        reason = "Costs within budget; smoothed distribution across forecast months"

    # Distribute proportionally to revenue (months with higher revenue get more cost allocation)
    if sum(revenues) > 0:
        proposed_costs = [
            (rev / sum(revenues)) * proposed_total if sum(revenues) > 0 else 0
            for rev in revenues
        ]
    else:
        # No revenue - distribute evenly
        proposed_costs = [proposed_total / len(forecast_months)] * len(forecast_months)

    proposed_ci = total_revenue_forecast - sum(proposed_costs)
    proposed_ci_pct = proposed_ci / total_revenue_forecast if total_revenue_forecast else 0

    return schemas.CostBalanceProposal(
        contract_id=contract_id,
        contract_name=contract.name,
        months=months,
        current_costs=current_costs,
        proposed_costs=proposed_costs,
        current_revenues=revenues,
        ci_current=current_ci,
        ci_proposed=proposed_ci,
        ci_pct_current=current_ci_pct,
        ci_pct_proposed=proposed_ci_pct,
        reason=reason,
    )
