"""Pydantic schemas (API boundary contracts)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Client ----------
class ClientBase(BaseModel):
    name: str
    industry: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientOut(ORMModel, ClientBase):
    id: int


# ---------- Contract ----------
class ContractBase(BaseModel):
    id: str
    client_id: int
    name: str
    service_group: str | None = None
    wbs_l1: str | None = None
    wbs_l2: str | None = None
    description: str | None = None
    contract_type: str = "T&M"
    fiscal_year: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    initial_budget: float | None = None
    status: str = "active"


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    name: str | None = None
    service_group: str | None = None
    wbs_l1: str | None = None
    wbs_l2: str | None = None
    description: str | None = None
    contract_type: str | None = None
    fiscal_year: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    initial_budget: float | None = None
    status: str | None = None


class ContractOut(ORMModel, ContractBase):
    client_name: str | None = None


# ---------- Opportunity ----------
class OpportunityBase(BaseModel):
    opp_id_mms: str | None = None
    contract_id: str | None = None
    name: str
    description: str | None = None
    legal_entity: str | None = None
    fiscal_year: str | None = None
    close_date: date | None = None
    quarter: str | None = None
    pds_status: str | None = None
    acn_tool_status: str | None = None
    mms_status: str | None = None
    stage: str = "Lead"
    estimated_value: float = 0.0
    probability: float = 0.0
    notes: str | None = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    opp_id_mms: str | None = None
    contract_id: str | None = None
    name: str | None = None
    description: str | None = None
    legal_entity: str | None = None
    fiscal_year: str | None = None
    close_date: date | None = None
    quarter: str | None = None
    pds_status: str | None = None
    acn_tool_status: str | None = None
    mms_status: str | None = None
    stage: str | None = None
    estimated_value: float | None = None
    probability: float | None = None
    notes: str | None = None


class OpportunityOut(ORMModel, OpportunityBase):
    id: int


# ---------- Role ----------
class RoleOut(ORMModel):
    id: int
    name: str
    default_rate: float | None = None
    seniority: str | None = None


# ---------- Resource ----------
class ResourceBase(BaseModel):
    name: str
    email: str | None = None
    role_id: int | None = None
    daily_rate: float = 0.0
    loaded_cost_hourly: float | None = None
    chargeability: float = 0.80
    chargeability_notes: str | None = None
    status: str = "active"
    hire_date: date | None = None


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role_id: int | None = None
    daily_rate: float | None = None
    loaded_cost_hourly: float | None = None
    chargeability: float | None = None
    chargeability_notes: str | None = None
    status: str | None = None
    hire_date: date | None = None


class ResourceOut(ORMModel, ResourceBase):
    id: int
    role_name: str | None = None


# ---------- Allocation ----------
class AllocationBase(BaseModel):
    resource_id: int
    contract_id: str
    utilization: float = 1.0
    days_per_month: float = 0.0
    start_date: date | None = None
    end_date: date | None = None


class AllocationCreate(AllocationBase):
    pass


class AllocationUpdate(BaseModel):
    utilization: float | None = None
    days_per_month: float | None = None
    start_date: date | None = None
    end_date: date | None = None


class AllocationOut(ORMModel, AllocationBase):
    id: int
    resource_name: str | None = None
    contract_name: str | None = None
    monthly_cost: float = 0.0


# ---------- Dashboard payloads ----------
class MonthlyPoint(BaseModel):
    month: str  # ISO yyyy-mm
    revenues: float = 0.0
    costs: float = 0.0
    ci: float = 0.0
    ci_pct: float = 0.0
    is_actual: bool = True


class KpiValue(BaseModel):
    label: str
    value: float
    unit: str = "EUR"  # EUR | PCT | NUM
    delta: float | None = None
    status: str | None = None  # good | warning | bad


class PipelineStage(BaseModel):
    quarter: str
    stage: str
    value: float
    count: int


class AccountDashboard(BaseModel):
    client_id: int | None = None
    client_name: str
    contracts_count: int
    opportunities_count: int
    kpis: list[KpiValue]
    monthly: list[MonthlyPoint]
    pipeline: list[PipelineStage]
    contracts: list[ContractKpiRow]


class ContractKpiRow(BaseModel):
    id: str
    name: str
    client_name: str | None = None
    revenues: float
    costs: float
    ci: float
    ci_pct: float
    status: str


class PeopleAllocationRow(BaseModel):
    resource_id: int
    resource_name: str
    role: str | None = None
    days_per_month: float
    daily_rate: float
    utilization: float
    monthly_cost: float
    monthly_revenue: float


class ContractDashboard(BaseModel):
    contract: ContractOut
    kpis: list[KpiValue]
    monthly: list[MonthlyPoint]
    cost_breakdown: dict[str, float]
    people: list[PeopleAllocationRow]


class TeamRosterRow(BaseModel):
    resource_id: int
    name: str
    role: str | None = None
    daily_rate: float
    utilization: float
    contracts_count: int
    contracts: list[str]
    monthly_cost: float
    monthly_revenue: float
    margin: float
    status: str  # full | partial | bench


class HeatmapCell(BaseModel):
    resource_id: int
    month: str
    utilization: float


class TeamDashboard(BaseModel):
    kpis: list[KpiValue]
    roster: list[TeamRosterRow]
    heatmap: list[HeatmapCell]
    months: list[str]


class PersonContractRow(BaseModel):
    contract_id: str
    contract_name: str
    client_name: str | None = None
    wbs: str | None = None
    days_per_month: float
    utilization: float
    monthly_cost: float
    monthly_revenue: float
    start_date: date | None = None
    end_date: date | None = None


class PersonDashboard(BaseModel):
    resource: ResourceOut
    kpis: list[KpiValue]
    allocations: list[PersonContractRow]
    monthly: list[MonthlyPoint]  # cost vs revenue per month (revenues=attributed, costs=person cost)
    contract_mix: list[dict]  # [{name, value}]


class ImportResult(BaseModel):
    ok: bool
    message: str
    clients: int = 0
    contracts: int = 0
    resources: int = 0
    allocations: int = 0
    financials: int = 0
    opportunities: int = 0


# ---------- Project ----------
class ProjectBase(BaseModel):
    contract_id: str
    name: str
    wbs: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    is_external: bool = False


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    wbs: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    is_external: bool | None = None
    status: str | None = None


class ProjectOut(ORMModel, ProjectBase):
    id: int
    status: str


# ---------- Due Diligence ----------
class DueDiligenceBase(BaseModel):
    opportunity_id: int
    milestone: str
    step_order: int = 0
    status: str = "pending"
    is_mandatory: bool = True
    depends_on_step: int | None = None
    assigned_to: str | None = None
    due_date: date | None = None
    completed_date: date | None = None
    approver: str | None = None
    approval_date: date | None = None
    notes: str | None = None


class DueDiligenceCreate(DueDiligenceBase):
    pass


class DueDiligenceUpdate(BaseModel):
    status: str | None = None
    assigned_to: str | None = None
    completed_date: date | None = None
    approver: str | None = None
    approval_date: date | None = None
    notes: str | None = None
    notes: str | None = None


class DueDiligenceOut(ORMModel, DueDiligenceBase):
    id: int


# ---------- Time Entry ----------
class TimeEntryBase(BaseModel):
    resource_id: int
    project_id: int | None = None
    period: str
    hours: float
    wbs: str
    type: str
    week_ending: date | None = None


class TimeEntryCreate(TimeEntryBase):
    pass


class TimeEntryOut(ORMModel, TimeEntryBase):
    id: int
    resource_name: str = ""  # Populated by service


# ---------- Invoice Schemas ----------
class InvoiceBase(BaseModel):
    invoice_number: str
    opportunity_id: int | None = None
    contract_id: str | None = None
    amount: float
    invoice_date: date
    payment_date: date | None = None
    status: str = "emessa"  # emessa, pagata, in_attesa
    notes: str | None = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    amount: float | None = None
    payment_date: date | None = None
    status: str | None = None
    notes: str | None = None


class InvoiceOut(ORMModel, InvoiceBase):
    id: int
    created_at: datetime


# ---------- Extended Dashboard Schemas ----------
class OpportunityDetail(ORMModel):
    """Extended opportunity with due diligence and invoicing tracking"""

    id: int
    opp_id_mms: str | None
    contract_id: str | None
    name: str
    description: str | None
    legal_entity: str | None
    fiscal_year: str | None
    close_date: date | None
    quarter: str | None

    # PDS & MMS tracking
    pds_status: str | None
    acn_tool_status: str | None
    mms_status: str | None
    mms_status_code: str | None
    mmr_code: str | None

    # ODA & CCP tracking
    oda_id: str | None
    ccp_number: str | None
    referente: str | None

    # Invoicing
    total_invoiced: float
    total_to_invoice: float

    stage: str
    estimated_value: float
    probability: float
    notes: str | None
    due_diligences: list[DueDiligenceOut] = []
    invoices: list[InvoiceOut] = []


class ProjectAllocationRow(BaseModel):
    """For Person/Team dashboards showing project-level allocation"""

    project_id: int | None
    project_name: str | None
    contract_id: str
    contract_name: str
    start_date: str | None
    end_date: str | None
    days_per_month: float
    utilization: float
    monthly_cost: float
    monthly_revenue: float


class CostBalanceProposal(BaseModel):
    """Cost optimization proposal for a contract"""

    contract_id: str
    contract_name: str
    months: list[str]  # ["2026-09", "2026-10", ...]
    current_costs: list[float]
    proposed_costs: list[float]
    current_revenues: list[float]
    ci_current: float
    ci_proposed: float
    ci_pct_current: float
    ci_pct_proposed: float
    reason: str


class TimeReportRequest(BaseModel):
    """Request params for time report generation"""

    period: str  # "2Q", "1Q", etc.
    resource_ids: list[int] | None = None
