"""Due Diligence Standard Templates

Template di Due Diligence sequenziali per contratti IT/Security secondo best practice.
"""

# Template Standard per Contratti IT Security
DD_TEMPLATE_SECURITY = [
    {
        "step_order": 1,
        "milestone": "Preliminary Assessment",
        "description": "Valutazione preliminare opportunità e scope",
        "is_mandatory": True,
        "typical_duration_days": 5,
        "assigned_role": "PM",
        "deliverables": ["Scope document", "Initial risk assessment"],
    },
    {
        "step_order": 2,
        "milestone": "Client NDA",
        "description": "Non-Disclosure Agreement firmato dal cliente",
        "is_mandatory": True,
        "depends_on_step": 1,
        "typical_duration_days": 3,
        "assigned_role": "Legal",
        "deliverables": ["Signed NDA"],
    },
    {
        "step_order": 3,
        "milestone": "Technical Assessment",
        "description": "Assessment tecnico delle capability richieste",
        "is_mandatory": True,
        "depends_on_step": 2,
        "typical_duration_days": 7,
        "assigned_role": "Tech Lead",
        "deliverables": ["Technical feasibility report", "Resource requirements"],
    },
    {
        "step_order": 4,
        "milestone": "Resource Availability Check",
        "description": "Verifica disponibilità risorse con skill richieste",
        "is_mandatory": True,
        "depends_on_step": 3,
        "typical_duration_days": 3,
        "assigned_role": "Resource Manager",
        "deliverables": ["Resource allocation plan", "Skill gap analysis"],
    },
    {
        "step_order": 5,
        "milestone": "Cost Estimation",
        "description": "Stima costi dettagliata (payroll, non-payroll, capex)",
        "is_mandatory": True,
        "depends_on_step": 4,
        "typical_duration_days": 5,
        "assigned_role": "Finance",
        "deliverables": ["Detailed cost breakdown", "ROI analysis"],
    },
    {
        "step_order": 6,
        "milestone": "Pricing & Margin Review",
        "description": "Definizione pricing e verifica margini (target CCI 35%)",
        "is_mandatory": True,
        "depends_on_step": 5,
        "typical_duration_days": 3,
        "assigned_role": "Commercial",
        "deliverables": ["Pricing model", "Margin analysis"],
    },
    {
        "step_order": 7,
        "milestone": "Risk Assessment",
        "description": "Identificazione e mitigazione rischi contrattuali e operativi",
        "is_mandatory": True,
        "depends_on_step": 6,
        "typical_duration_days": 5,
        "assigned_role": "Risk Manager",
        "deliverables": ["Risk register", "Mitigation plan"],
    },
    {
        "step_order": 8,
        "milestone": "Compliance Check",
        "description": "Verifica compliance normativa (GDPR, ISO27001, etc.)",
        "is_mandatory": True,
        "depends_on_step": 7,
        "typical_duration_days": 7,
        "assigned_role": "Compliance Officer",
        "deliverables": ["Compliance checklist", "Gap analysis"],
    },
    {
        "step_order": 9,
        "milestone": "Security Clearance",
        "description": "Background check risorse e security clearance se richiesto",
        "is_mandatory": False,  # Only for certain clients
        "depends_on_step": 4,
        "typical_duration_days": 14,
        "assigned_role": "Security",
        "deliverables": ["Clearance certificates"],
    },
    {
        "step_order": 10,
        "milestone": "PDS Preparation",
        "description": "Preparazione Project Definition Sheet",
        "is_mandatory": True,
        "depends_on_step": 8,
        "typical_duration_days": 5,
        "assigned_role": "PM",
        "deliverables": ["PDS document"],
    },
    {
        "step_order": 11,
        "milestone": "PDS Approval CVS",
        "description": "Approvazione PDS da CVS (Client Value Stream)",
        "is_mandatory": True,
        "depends_on_step": 10,
        "typical_duration_days": 7,
        "assigned_role": "CVS Lead",
        "deliverables": ["Approved PDS"],
    },
    {
        "step_order": 12,
        "milestone": "ACN Tool Submission",
        "description": "Inserimento opportunity in Accenture Tool",
        "is_mandatory": True,
        "depends_on_step": 11,
        "typical_duration_days": 2,
        "assigned_role": "Sales",
        "deliverables": ["ACN Tool ID", "Opportunity record"],
    },
    {
        "step_order": 13,
        "milestone": "MMS Status Update",
        "description": "Aggiornamento status in MMS (0 → 1 → 3B → Close-Won)",
        "is_mandatory": True,
        "depends_on_step": 12,
        "typical_duration_days": 1,
        "assigned_role": "Sales Ops",
        "deliverables": ["MMS status code"],
    },
    {
        "step_order": 14,
        "milestone": "Contract Drafting",
        "description": "Redazione bozza contratto (MSA, SOW, SLA)",
        "is_mandatory": True,
        "depends_on_step": 13,
        "typical_duration_days": 10,
        "assigned_role": "Legal",
        "deliverables": ["Contract draft", "Terms & Conditions"],
    },
    {
        "step_order": 15,
        "milestone": "Legal Review",
        "description": "Review legale contratto da team legal interno",
        "is_mandatory": True,
        "depends_on_step": 14,
        "typical_duration_days": 7,
        "assigned_role": "Legal Counsel",
        "deliverables": ["Legal approval", "Risk notes"],
    },
    {
        "step_order": 16,
        "milestone": "Client Negotiation",
        "description": "Negoziazione termini contrattuali con cliente",
        "is_mandatory": True,
        "depends_on_step": 15,
        "typical_duration_days": 14,
        "assigned_role": "Account Lead",
        "deliverables": ["Negotiated terms", "Meeting minutes"],
    },
    {
        "step_order": 17,
        "milestone": "Final Approval",
        "description": "Approvazione finale da management (MD/Partner level)",
        "is_mandatory": True,
        "depends_on_step": 16,
        "typical_duration_days": 5,
        "assigned_role": "MD/Partner",
        "deliverables": ["Signed approval"],
    },
    {
        "step_order": 18,
        "milestone": "Contract Signature",
        "description": "Firma contratto da entrambe le parti",
        "is_mandatory": True,
        "depends_on_step": 17,
        "typical_duration_days": 7,
        "assigned_role": "Legal",
        "deliverables": ["Signed contract"],
    },
    {
        "step_order": 19,
        "milestone": "ODA Creation",
        "description": "Creazione ODA (Ordine Di Acquisto) nel sistema",
        "is_mandatory": True,
        "depends_on_step": 18,
        "typical_duration_days": 3,
        "assigned_role": "Finance",
        "deliverables": ["ODA ID"],
    },
    {
        "step_order": 20,
        "milestone": "CCP Assignment",
        "description": "Assegnazione CCP (codice progetto 5 cifre)",
        "is_mandatory": True,
        "depends_on_step": 19,
        "typical_duration_days": 2,
        "assigned_role": "Finance",
        "deliverables": ["CCP code"],
    },
    {
        "step_order": 21,
        "milestone": "Kickoff Preparation",
        "description": "Preparazione kickoff meeting e onboarding plan",
        "is_mandatory": True,
        "depends_on_step": 20,
        "typical_duration_days": 5,
        "assigned_role": "PM",
        "deliverables": ["Kickoff deck", "Onboarding plan"],
    },
    {
        "step_order": 22,
        "milestone": "Project Kickoff",
        "description": "Kickoff meeting con cliente e team interno",
        "is_mandatory": True,
        "depends_on_step": 21,
        "typical_duration_days": 1,
        "assigned_role": "PM",
        "deliverables": ["Kickoff minutes", "Action items"],
    },
]

# Template Fast-Track (opportunità urgenti)
DD_TEMPLATE_FAST_TRACK = [
    {"step_order": 1, "milestone": "Preliminary Assessment", "is_mandatory": True},
    {"step_order": 2, "milestone": "Client NDA", "is_mandatory": True, "depends_on_step": 1},
    {"step_order": 3, "milestone": "Technical & Cost Assessment", "is_mandatory": True, "depends_on_step": 2},
    {"step_order": 4, "milestone": "PDS Preparation & Approval", "is_mandatory": True, "depends_on_step": 3},
    {"step_order": 5, "milestone": "ACN Tool & MMS", "is_mandatory": True, "depends_on_step": 4},
    {"step_order": 6, "milestone": "Contract Draft & Legal Review", "is_mandatory": True, "depends_on_step": 5},
    {"step_order": 7, "milestone": "Contract Signature", "is_mandatory": True, "depends_on_step": 6},
    {"step_order": 8, "milestone": "ODA & CCP", "is_mandatory": True, "depends_on_step": 7},
    {"step_order": 9, "milestone": "Project Kickoff", "is_mandatory": True, "depends_on_step": 8},
]

# Template Extension/Change Order (contratti esistenti)
DD_TEMPLATE_EXTENSION = [
    {"step_order": 1, "milestone": "Change Request Analysis", "is_mandatory": True},
    {"step_order": 2, "milestone": "Impact Assessment", "is_mandatory": True, "depends_on_step": 1},
    {"step_order": 3, "milestone": "Pricing & Approval", "is_mandatory": True, "depends_on_step": 2},
    {"step_order": 4, "milestone": "Contract Amendment", "is_mandatory": True, "depends_on_step": 3},
    {"step_order": 5, "milestone": "Signature & Activation", "is_mandatory": True, "depends_on_step": 4},
]


def get_template_by_type(template_type: str) -> list[dict]:
    """Retrieve DD template by type."""
    templates = {
        "standard": DD_TEMPLATE_SECURITY,
        "fast-track": DD_TEMPLATE_FAST_TRACK,
        "extension": DD_TEMPLATE_EXTENSION,
    }
    return templates.get(template_type, DD_TEMPLATE_SECURITY)


def calculate_total_duration(template: list[dict]) -> int:
    """Calculate total expected duration in days for a template."""
    return sum(step.get("typical_duration_days", 0) for step in template)


def get_critical_path(template: list[dict]) -> list[dict]:
    """Get only mandatory steps from template."""
    return [step for step in template if step.get("is_mandatory", True)]
