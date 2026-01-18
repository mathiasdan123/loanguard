"""
Database models for LoanGuard.
Uses SQLAlchemy with PostgreSQL for production persistence.
"""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, 
    DateTime, Text, ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from enum import Enum


# Database URL from environment
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://localhost:5432/loanguard"
)

# Handle Heroku/Railway postgres:// vs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enums
class RequirementCategory(str, Enum):
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


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AT_RISK = "at_risk"
    PENDING = "pending"
    UNKNOWN = "unknown"
    NOT_YET_DUE = "not_yet_due"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Frequency(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    ONE_TIME = "one_time"
    AS_NEEDED = "as_needed"
    UPON_REQUEST = "upon_request"


# Models
class User(Base):
    """User account for advisors/borrowers"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    clerk_id = Column(String(255), unique=True, index=True)  # Clerk user ID
    email = Column(String(255), unique=True, index=True)
    name = Column(String(255))
    company = Column(String(255), nullable=True)
    role = Column(String(50), default="advisor")  # advisor, borrower, admin
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    weekly_summary = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    loans = relationship("Loan", back_populates="owner")
    

class Loan(Base):
    """Loan profile"""
    __tablename__ = "loans"
    
    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(String(50), unique=True, index=True)  # User-friendly ID like "LOAN-001"
    
    # Basic info
    property_name = Column(String(255), nullable=False)
    property_address = Column(String(500), nullable=True)
    borrower_name = Column(String(255))
    lender_name = Column(String(255))
    
    # Financial
    original_loan_amount = Column(Float)
    current_balance = Column(Float, nullable=True)
    interest_rate = Column(Float, nullable=True)
    
    # Dates
    origination_date = Column(DateTime, nullable=True)
    maturity_date = Column(DateTime, nullable=True)
    
    # Computed
    compliance_score = Column(Integer, default=0)  # 0-100
    
    # Metadata
    source_documents = Column(JSON, default=list)
    extraction_date = Column(DateTime, default=datetime.utcnow)
    
    # Owner
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="loans")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    requirements = relationship("Requirement", back_populates="loan", cascade="all, delete-orphan")
    events = relationship("ComplianceEvent", back_populates="loan", cascade="all, delete-orphan")
    
    def calculate_compliance_score(self) -> int:
        """Calculate compliance score based on requirements"""
        if not self.requirements:
            return 100
        
        total = len(self.requirements)
        compliant = len([r for r in self.requirements if r.status == ComplianceStatus.COMPLIANT.value])
        at_risk = len([r for r in self.requirements if r.status == ComplianceStatus.AT_RISK.value])
        
        # Compliant = full points, at_risk = half points, others = 0
        score = (compliant + (at_risk * 0.5)) / total * 100
        return int(score)


class Requirement(Base):
    """A single compliance requirement"""
    __tablename__ = "requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    requirement_id = Column(String(50), index=True)  # Like "REQ-001"
    
    # Content
    title = Column(String(255), nullable=False)
    category = Column(String(50))
    description = Column(Text)
    plain_language_summary = Column(Text)
    original_text = Column(Text)
    document_reference = Column(String(255))
    
    # Deadline
    deadline_description = Column(String(255))
    deadline_frequency = Column(String(50))
    deadline_days_after_period = Column(Integer, nullable=True)
    deadline_day_of_month = Column(Integer, nullable=True)
    next_due_date = Column(DateTime, nullable=True)
    
    # Threshold (for covenants)
    threshold_metric = Column(String(100), nullable=True)
    threshold_operator = Column(String(10), nullable=True)
    threshold_value = Column(Float, nullable=True)
    threshold_unit = Column(String(20), nullable=True)
    current_value = Column(Float, nullable=True)  # Latest measured value
    
    # Status
    severity = Column(String(20), default="medium")
    status = Column(String(20), default="unknown")
    cure_period_days = Column(Integer, nullable=True)
    
    # Tracking
    last_checked = Column(DateTime, nullable=True)
    last_submitted = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Loan relationship
    loan_id = Column(Integer, ForeignKey("loans.id"))
    loan = relationship("Loan", back_populates="requirements")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceEvent(Base):
    """Tracks compliance submissions and changes"""
    __tablename__ = "compliance_events"
    
    id = Column(Integer, primary_key=True, index=True)
    
    requirement_id = Column(String(50))
    event_type = Column(String(50))  # submission, verification, breach, cure, status_change
    event_date = Column(DateTime, default=datetime.utcnow)
    description = Column(Text)
    
    # Who did it
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # What changed
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    
    # Documents
    documents = Column(JSON, default=list)
    
    # Loan relationship
    loan_id = Column(Integer, ForeignKey("loans.id"))
    loan = relationship("Loan", back_populates="events")
    
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationLog(Base):
    """Tracks sent notifications"""
    __tablename__ = "notification_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    notification_type = Column(String(50))
    subject = Column(String(255))
    recipient_email = Column(String(255))
    
    loan_id = Column(String(50), nullable=True)
    requirement_id = Column(String(50), nullable=True)
    
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="sent")  # sent, failed, bounced
    
    # For debugging
    sendgrid_message_id = Column(String(255), nullable=True)


# Database initialization
def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session - use as dependency in FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper functions
def get_user_by_clerk_id(db, clerk_id: str) -> Optional[User]:
    """Get user by Clerk ID"""
    return db.query(User).filter(User.clerk_id == clerk_id).first()


def get_user_loans(db, user_id: int):
    """Get all loans for a user"""
    return db.query(Loan).filter(Loan.owner_id == user_id).all()


def get_loan_by_id(db, loan_id: str, user_id: int) -> Optional[Loan]:
    """Get a specific loan (with ownership check)"""
    return db.query(Loan).filter(
        Loan.loan_id == loan_id,
        Loan.owner_id == user_id
    ).first()


def create_loan_from_profile(db, profile, user_id: int) -> Loan:
    """Create a loan from an extracted profile"""
    loan = Loan(
        loan_id=profile.loan_id,
        property_name=profile.property_name,
        borrower_name=profile.borrower_name,
        lender_name=profile.lender_name,
        original_loan_amount=profile.original_loan_amount,
        origination_date=datetime.fromisoformat(profile.origination_date) if profile.origination_date else None,
        maturity_date=datetime.fromisoformat(profile.maturity_date) if profile.maturity_date else None,
        owner_id=user_id
    )
    db.add(loan)
    db.flush()  # Get the loan ID
    
    # Add requirements
    for req in profile.requirements:
        db_req = Requirement(
            requirement_id=req.id,
            title=req.title,
            category=req.category.value if hasattr(req.category, 'value') else req.category,
            description=req.description,
            plain_language_summary=req.plain_language_summary,
            original_text=req.original_text,
            document_reference=req.document_reference,
            severity=req.severity.value if hasattr(req.severity, 'value') else req.severity,
            status=req.status.value if hasattr(req.status, 'value') else req.status,
            cure_period_days=req.cure_period_days,
            loan_id=loan.id
        )
        
        if req.deadline:
            db_req.deadline_description = req.deadline.description
            db_req.deadline_frequency = req.deadline.frequency.value if hasattr(req.deadline.frequency, 'value') else req.deadline.frequency
            db_req.deadline_days_after_period = req.deadline.days_after_period_end
            db_req.deadline_day_of_month = req.deadline.day_of_month
        
        if req.threshold:
            db_req.threshold_metric = req.threshold.metric
            db_req.threshold_operator = req.threshold.operator
            db_req.threshold_value = req.threshold.value
            db_req.threshold_unit = req.threshold.unit
        
        db.add(db_req)
    
    # Calculate and save compliance score
    db.flush()
    loan.compliance_score = loan.calculate_compliance_score()
    
    db.commit()
    db.refresh(loan)
    
    return loan
