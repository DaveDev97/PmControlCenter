"""SQLAlchemy ORM models for the PM Control Center."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contracts: Mapped[list[Contract]] = relationship(back_populates="client")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "9940435940"
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    service_group: Mapped[str | None] = mapped_column(String, nullable=True)
    wbs_l1: Mapped[str | None] = mapped_column(String, nullable=True)
    wbs_l2: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_type: Mapped[str] = mapped_column(String, default="T&M")  # T&M, Fixed Price, Capped T&M
    fiscal_year: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")  # active, closed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client: Mapped[Client] = relationship(back_populates="contracts")
    financials: Mapped[list[Financial]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list[Opportunity]] = relationship(back_populates="contract")
    projects: Mapped[list["Project"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    opp_id_mms: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    contract_id: Mapped[str | None] = mapped_column(
        ForeignKey("contracts.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    legal_entity: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g., "BNL S.p.A."
    fiscal_year: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g., "2026"
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quarter: Mapped[str | None] = mapped_column(String, nullable=True)  # Q1..Q4

    # PDS & MMS tracking (from doc operativo)
    pds_status: Mapped[str | None] = mapped_column(String, nullable=True)  # inviata/approvata/da_inviare
    acn_tool_status: Mapped[str | None] = mapped_column(String, nullable=True)
    mms_status: Mapped[str | None] = mapped_column(String, nullable=True)
    mms_status_code: Mapped[str | None] = mapped_column(String, nullable=True)  # 0, 1, 3B, close-won
    mmr_code: Mapped[str | None] = mapped_column(String, nullable=True)  # Request code at booking

    # ODA & CCP tracking (from doc operativo)
    oda_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Numero ordine
    ccp_number: Mapped[str | None] = mapped_column(String, nullable=True)  # SOW 5-digit code
    referente: Mapped[str | None] = mapped_column(String, nullable=True)  # Project referente

    # Invoicing (from doc operativo)
    total_invoiced: Mapped[float] = mapped_column(Float, default=0.0)  # Importo fatturato
    total_to_invoice: Mapped[float] = mapped_column(Float, default=0.0)  # Importo da fatturare

    # Workflow stage: Lead, Qualified, Proposal, CloseWon, CloseLost
    stage: Mapped[str] = mapped_column(String, default="Lead")
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0)
    probability: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contract: Mapped[Contract | None] = relationship(back_populates="opportunities")
    due_diligences: Mapped[list["DueDiligence"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    default_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    seniority: Mapped[str | None] = mapped_column(String, nullable=True)

    resources: Mapped[list[Resource]] = relationship(back_populates="role")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    daily_rate: Mapped[float] = mapped_column(Float, default=0.0)  # Selling rate
    loaded_cost_hourly: Mapped[float | None] = mapped_column(Float, nullable=True)  # Full cost/hour from MME
    chargeability: Mapped[float] = mapped_column(Float, default=0.80)  # % billable (default 80%)
    chargeability_notes: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "80% BNL, 20% Mooney"
    status: Mapped[str] = mapped_column(String, default="active")  # active, inactive
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role: Mapped[Role | None] = relationship(back_populates="resources")
    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )  # Allocation can be to contract OR specific project
    utilization: Mapped[float] = mapped_column(Float, default=1.0)  # 0..1 productivity factor
    days_per_month: Mapped[float] = mapped_column(Float, default=0.0)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    resource: Mapped[Resource] = relationship(back_populates="allocations")
    contract: Mapped[Contract] = relationship(back_populates="allocations")
    project: Mapped["Project | None"] = relationship(back_populates="allocations")


class Financial(Base):
    __tablename__ = "financials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    month: Mapped[date] = mapped_column(Date, index=True)  # first day of the month
    fiscal_quarter: Mapped[str | None] = mapped_column(String, nullable=True)
    is_actual: Mapped[bool] = mapped_column(Boolean, default=True)

    billings_actual: Mapped[float] = mapped_column(Float, default=0.0)
    billings_forecast: Mapped[float] = mapped_column(Float, default=0.0)
    revenues_actual: Mapped[float] = mapped_column(Float, default=0.0)
    revenues_forecast: Mapped[float] = mapped_column(Float, default=0.0)
    payroll_costs_actual: Mapped[float] = mapped_column(Float, default=0.0)
    payroll_costs_forecast: Mapped[float] = mapped_column(Float, default=0.0)
    non_payroll_costs_actual: Mapped[float] = mapped_column(Float, default=0.0)
    non_payroll_costs_forecast: Mapped[float] = mapped_column(Float, default=0.0)
    capital_charges_actual: Mapped[float] = mapped_column(Float, default=0.0)
    capital_charges_forecast: Mapped[float] = mapped_column(Float, default=0.0)

    contract: Mapped[Contract] = relationship(back_populates="financials")

    # --- convenience computed properties ---
    @property
    def total_costs_actual(self) -> float:
        return (
            self.payroll_costs_actual
            + self.non_payroll_costs_actual
            + self.capital_charges_actual
        )

    @property
    def total_costs_forecast(self) -> float:
        return (
            self.payroll_costs_forecast
            + self.non_payroll_costs_forecast
            + self.capital_charges_forecast
        )

    @property
    def ci_actual(self) -> float:
        return self.revenues_actual - self.total_costs_actual


class Project(Base):
    """Projects within contracts - hierarchy: Contract → Projects → Allocations"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    wbs: Mapped[str | None] = mapped_column(String, nullable=True)  # Project-specific WBS
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_external: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Flag for external engagements
    status: Mapped[str] = mapped_column(String, default="active")  # active, closed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contract: Mapped[Contract] = relationship(back_populates="projects")
    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    time_entries: Mapped[list["TimeEntry"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class DueDiligence(Base):
    """Due diligence tracking for opportunities"""

    __tablename__ = "due_diligence"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    milestone: Mapped[str] = mapped_column(String)  # "PDS", "ACN Tool", "MMS", "Legal Review", etc.
    step_order: Mapped[int] = mapped_column(Integer, default=0)  # Sequence order (1, 2, 3...)
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # "pending", "in_progress", "completed", "blocked", "skipped"
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)  # Required vs optional step
    depends_on_step: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Sequential dependency
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True)  # Responsible person
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    approver: Mapped[str | None] = mapped_column(String, nullable=True)  # Who approved
    approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    opportunity: Mapped[Opportunity] = relationship(back_populates="due_diligences")


class TimeEntry(Base):
    """Time tracking for resources on projects"""

    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    period: Mapped[str] = mapped_column(String, index=True)  # "2Q", "1Q", etc.
    hours: Mapped[float] = mapped_column(Float, default=0.0)
    wbs: Mapped[str] = mapped_column(String)  # "B7PMH001", "Meeting Time", "Permesso", etc.
    type: Mapped[str] = mapped_column(String)  # "Chargeable", "Not Chargeable"
    week_ending: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    resource: Mapped[Resource] = relationship()
    project: Mapped[Project | None] = relationship(back_populates="time_entries")


class Invoice(Base):
    """Invoicing tracking per documento operativo."""
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"), nullable=True, index=True)
    contract_id: Mapped[str | None] = mapped_column(ForeignKey("contracts.id"), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    invoice_date: Mapped[date] = mapped_column(Date)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, default="emessa")  # emessa, pagata, in_attesa
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    opportunity: Mapped[Opportunity | None] = relationship(back_populates="invoices")
    contract: Mapped[Contract | None] = relationship(back_populates="invoices")
