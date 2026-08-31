// API contract types (mirror backend app/schemas.py)

export interface Client {
  id: number;
  name: string;
  industry?: string | null;
}

export interface Contract {
  id: string;
  client_id: number;
  name: string;
  service_group?: string | null;
  wbs_l1?: string | null;
  wbs_l2?: string | null;
  description?: string | null;
  contract_type: string;
  fiscal_year?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  initial_budget?: number | null;
  status: string;
  client_name?: string | null;
}

export interface Opportunity {
  id: number;
  opp_id_mms?: string | null;
  contract_id?: string | null;
  name: string;
  description?: string | null;
  legal_entity?: string | null;
  fiscal_year?: string | null;
  close_date?: string | null;
  quarter?: string | null;
  pds_status?: string | null;
  acn_tool_status?: string | null;
  mms_status?: string | null;
  stage: string;
  estimated_value: number;
  probability: number;
  notes?: string | null;
}

export interface Role {
  id: number;
  name: string;
  default_rate?: number | null;
  seniority?: string | null;
}

export interface Resource {
  id: number;
  name: string;
  email?: string | null;
  role_id?: number | null;
  daily_rate: number;
  status: string;
  hire_date?: string | null;
  role_name?: string | null;
}

export interface Allocation {
  id: number;
  resource_id: number;
  contract_id: string;
  utilization: number;
  days_per_month: number;
  start_date?: string | null;
  end_date?: string | null;
  resource_name?: string | null;
  contract_name?: string | null;
  monthly_cost: number;
}

export interface KpiValue {
  label: string;
  value: number;
  unit: "EUR" | "PCT" | "NUM";
  delta?: number | null;
  status?: "good" | "warning" | "bad" | null;
}

export interface MonthlyPoint {
  month: string;
  revenues: number;
  costs: number;
  ci: number;
  ci_pct: number;
  is_actual: boolean;
}

export interface PipelineStage {
  quarter: string;
  stage: string;
  value: number;
  count: number;
}

export interface ContractKpiRow {
  id: string;
  name: string;
  client_name?: string | null;
  revenues: number;
  costs: number;
  ci: number;
  ci_pct: number;
  status: string;
}

export interface AccountDashboard {
  client_id?: number | null;
  client_name: string;
  contracts_count: number;
  opportunities_count: number;
  kpis: KpiValue[];
  monthly: MonthlyPoint[];
  pipeline: PipelineStage[];
  contracts: ContractKpiRow[];
}

export interface PeopleAllocationRow {
  resource_id: number;
  resource_name: string;
  role?: string | null;
  days_per_month: number;
  daily_rate: number;
  utilization: number;
  monthly_cost: number;
  monthly_revenue: number;
}

export interface ContractDashboard {
  contract: Contract;
  kpis: KpiValue[];
  monthly: MonthlyPoint[];
  cost_breakdown: Record<string, number>;
  people: PeopleAllocationRow[];
}

export interface TeamRosterRow {
  resource_id: number;
  name: string;
  role?: string | null;
  daily_rate: number;
  utilization: number;
  contracts_count: number;
  contracts: string[];
  monthly_cost: number;
  monthly_revenue: number;
  margin: number;
  status: "full" | "partial" | "bench";
}

export interface HeatmapCell {
  resource_id: number;
  month: string;
  utilization: number;
}

export interface TeamDashboard {
  kpis: KpiValue[];
  roster: TeamRosterRow[];
  heatmap: HeatmapCell[];
  months: string[];
}

export interface PersonContractRow {
  contract_id: string;
  contract_name: string;
  client_name?: string | null;
  wbs?: string | null;
  days_per_month: number;
  utilization: number;
  monthly_cost: number;
  monthly_revenue: number;
  start_date?: string | null;
  end_date?: string | null;
}

export interface PersonDashboard {
  resource: Resource;
  kpis: KpiValue[];
  allocations: PersonContractRow[];
  monthly: MonthlyPoint[];
  contract_mix: { name: string; value: number }[];
}

export interface Project {
  id: number;
  contract_id: string;
  name: string;
  wbs?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  budget?: number | null;
  is_external: boolean;
  status: string;
}

export interface DueDiligence {
  id: number;
  opportunity_id: number;
  milestone: string;
  step_order: number;
  status: string;
  is_mandatory: boolean;
  depends_on_step?: number | null;
  assigned_to?: string | null;
  due_date?: string | null;
  completed_date?: string | null;
  approver?: string | null;
  approval_date?: string | null;
  notes?: string | null;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  opportunity_id?: number | null;
  contract_id?: string | null;
  amount: number;
  invoice_date: string;
  payment_date?: string | null;
  status: string;
  notes?: string | null;
  created_at: string;
}

export interface OpportunityDetail extends Opportunity {
  due_diligences: DueDiligence[];
  invoices: Invoice[];
}

export interface TimeEntry {
  id: number;
  resource_id: number;
  resource_name: string;
  project_id?: number | null;
  period: string;
  hours: number;
  wbs: string;
  type: string;
  week_ending?: string | null;
}

export interface CostBalanceProposal {
  contract_id: string;
  contract_name: string;
  months: string[];
  current_revenues: number[];
  current_costs: number[];
  proposed_costs: number[];
  ci_current: number;
  ci_proposed: number;
  ci_pct_current: number;
  ci_pct_proposed: number;
  reason: string;
}
