"""
Data models for loan compliance tracking.
These models are designed to be both human-readable and agent-parseable.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from typing import Optional
import json


class RequirementCategory(str, Enum):
    """Categories of loan requirements"""
    FINANCIAL_REPORTING = "financial_reporting"
    COVENANT_COMPLIANCE = "covenant_compliance"
    INSURANCE = "insurance"
    RESERVE_FUNDING = "reserve_funding"
    PROPERTY_MANAGEMENT = "property_management"
    LEASING = "leasing"
    CAPITAL_IMPROVEMENTS = "capital_improvements"
    TAX_ESCROW = "tax_escrow"
    ENVIRONMENTAL = "environmental"
    LEGAL_ENTITY = "legal_entity"
    OTHER = "other"


class Frequency(str, Enum):
    """Reporting/compliance frequencies"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    ONE_TIME = "one_time"
    AS_NEEDED = "as_needed"
    UPON_REQUEST = "upon_request"


class ComplianceStatus(str, Enum):
    """Status of compliance with a requirement"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AT_RISK = "at_risk"
    PENDING = "pending"
    UNKNOWN = "unknown"
    NOT_YET_DUE = "not_yet_due"


class Severity(str, Enum):
    """Severity level if requirement is breached"""
    CRITICAL = "critical"  # Could trigger default
    HIGH = "high"          # Material breach, cure period likely
    MEDIUM = "medium"      # Administrative issue
    LOW = "low"            # Minor, unlikely to cause issues


@dataclass
class Deadline:
    """Represents a deadline or due date"""
    description: str
    days_after_period_end: Optional[int] = None  # e.g., "45 days after quarter end"
    specific_date: Optional[str] = None  # For one-time items
    day_of_month: Optional[int] = None  # e.g., "1st of each month"
    frequency: Frequency = Frequency.AS_NEEDED
    
    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "days_after_period_end": self.days_after_period_end,
            "specific_date": self.specific_date,
            "day_of_month": self.day_of_month,
            "frequency": self.frequency.value
        }


@dataclass
class Threshold:
    """Represents a covenant threshold or limit"""
    metric: str
    operator: str  # >=, <=, >, <, ==, between
    value: float
    secondary_value: Optional[float] = None  # For "between" operator
    unit: Optional[str] = None  # e.g., "%", "$", "x"
    
    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "operator": self.operator,
            "value": self.value,
            "secondary_value": self.secondary_value,
            "unit": self.unit
        }
    
    def human_readable(self) -> str:
        unit = self.unit or ""
        if self.operator == "between":
            return f"{self.metric} must be between {self.value}{unit} and {self.secondary_value}{unit}"
        elif self.operator == ">=":
            return f"{self.metric} must be at least {self.value}{unit}"
        elif self.operator == "<=":
            return f"{self.metric} must not exceed {self.value}{unit}"
        elif self.operator == ">":
            return f"{self.metric} must be greater than {self.value}{unit}"
        elif self.operator == "<":
            return f"{self.metric} must be less than {self.value}{unit}"
        else:
            return f"{self.metric} {self.operator} {self.value}{unit}"


@dataclass
class LoanRequirement:
    """A single operational requirement from a loan document"""
    id: str
    title: str
    category: RequirementCategory
    description: str
    plain_language_summary: str
    original_text: str  # The actual text from the document
    document_reference: str  # Section/page reference
    
    # Timing
    deadline: Optional[Deadline] = None
    
    # For covenant requirements
    threshold: Optional[Threshold] = None
    
    # Metadata
    severity: Severity = Severity.MEDIUM
    cure_period_days: Optional[int] = None
    
    # Current status (for tracking)
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    last_checked: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "description": self.description,
            "plain_language_summary": self.plain_language_summary,
            "original_text": self.original_text,
            "document_reference": self.document_reference,
            "deadline": self.deadline.to_dict() if self.deadline else None,
            "threshold": self.threshold.to_dict() if self.threshold else None,
            "severity": self.severity.value,
            "cure_period_days": self.cure_period_days,
            "status": self.status.value,
            "last_checked": self.last_checked,
            "notes": self.notes
        }


@dataclass
class ComplianceEvent:
    """Tracks a compliance submission or check"""
    requirement_id: str
    event_date: str
    event_type: str  # "submission", "verification", "breach", "cure"
    description: str
    submitted_by: Optional[str] = None
    documents: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "event_date": self.event_date,
            "event_type": self.event_type,
            "description": self.description,
            "submitted_by": self.submitted_by,
            "documents": self.documents
        }


@dataclass
class LoanProfile:
    """Complete profile of a loan's compliance requirements"""
    loan_id: str
    loan_name: str
    property_name: str
    borrower_name: str
    lender_name: str
    original_loan_amount: float
    current_balance: Optional[float] = None
    origination_date: Optional[str] = None
    maturity_date: Optional[str] = None
    
    requirements: list = field(default_factory=list)  # List[LoanRequirement]
    events: list = field(default_factory=list)  # List[ComplianceEvent]
    
    # Document metadata
    source_documents: list = field(default_factory=list)
    extraction_date: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "loan_id": self.loan_id,
            "loan_name": self.loan_name,
            "property_name": self.property_name,
            "borrower_name": self.borrower_name,
            "lender_name": self.lender_name,
            "original_loan_amount": self.original_loan_amount,
            "current_balance": self.current_balance,
            "origination_date": self.origination_date,
            "maturity_date": self.maturity_date,
            "requirements": [r.to_dict() for r in self.requirements],
            "events": [e.to_dict() for e in self.events],
            "source_documents": self.source_documents,
            "extraction_date": self.extraction_date
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def get_requirements_by_category(self, category: RequirementCategory) -> list:
        return [r for r in self.requirements if r.category == category]
    
    def get_upcoming_deadlines(self, within_days: int = 30) -> list:
        """Get requirements with deadlines in the next N days"""
        # This would need actual date calculation logic
        return [r for r in self.requirements if r.deadline is not None]
    
    def get_non_compliant(self) -> list:
        return [r for r in self.requirements if r.status == ComplianceStatus.NON_COMPLIANT]
    
    def get_at_risk(self) -> list:
        return [r for r in self.requirements if r.status == ComplianceStatus.AT_RISK]
    
    def compliance_summary(self) -> dict:
        """Generate a summary of compliance status"""
        status_counts = {}
        for status in ComplianceStatus:
            status_counts[status.value] = len([r for r in self.requirements if r.status == status])
        
        category_counts = {}
        for cat in RequirementCategory:
            category_counts[cat.value] = len([r for r in self.requirements if r.category == cat])
        
        return {
            "total_requirements": len(self.requirements),
            "by_status": status_counts,
            "by_category": category_counts,
            "critical_items": len([r for r in self.requirements if r.severity == Severity.CRITICAL]),
            "non_compliant_count": status_counts.get(ComplianceStatus.NON_COMPLIANT.value, 0),
            "at_risk_count": status_counts.get(ComplianceStatus.AT_RISK.value, 0)
        }
