"""Account Overview API endpoint."""
from fastapi import APIRouter
from app.services.account_overview import build_overview

router = APIRouter(prefix="/api/account-overview", tags=["account-overview"])


@router.get("")
def get_account_overview(fy: str = "FY27", contract: str = "all"):
    """
    Aggregated financial KPIs for the Account Overview section.

    - ``fy``: fiscal year label, e.g. ``FY26`` or ``FY27``
    - ``contract``: ``all`` or a specific contract ID (e.g. ``9940435940``)
    """
    return build_overview(fy_label=fy, contract_filter=contract)
