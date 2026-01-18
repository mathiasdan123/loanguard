"""
Production-ready FastAPI server for LoanGuard.
Includes authentication, database persistence, and email notifications.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Local imports
from .database import (
    get_db, init_db, User, Loan, Requirement, ComplianceEvent, NotificationLog,
    get_user_by_clerk_id, get_user_loans, get_loan_by_id, create_loan_from_profile
)
from .auth import get_current_user, get_optional_user, ClerkUser
from .email_service import email_service
from .pdf_extractor import LoanDocumentParser
from .extractor import RequirementExtractor, MockExtractor
from .formatters import HTMLFormatter


# Lifespan handler for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("👋 Shutting down")


# Initialize FastAPI
app = FastAPI(
    title="LoanGuard API",
    description="Loan compliance management platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS - configure for your frontend domain
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class LoanResponse(BaseModel):
    id: int
    loan_id: str
    property_name: str
    borrower_name: str
    lender_name: str
    original_loan_amount: float
    maturity_date: Optional[str]
    compliance_score: int
    requirements_count: int
    issues_count: int


class RequirementResponse(BaseModel):
    id: int
    requirement_id: str
    title: str
    category: str
    plain_language_summary: str
    severity: str
    status: str
    deadline_description: Optional[str]
    next_due_date: Optional[str]


class UpdateStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class NotificationPrefsRequest(BaseModel):
    email_notifications: bool
    weekly_summary: bool


# Helper functions
def get_or_create_user(db: Session, clerk_user: ClerkUser) -> User:
    """Get existing user or create new one from Clerk data"""
    user = get_user_by_clerk_id(db, clerk_user.clerk_id)
    
    if not user:
        user = User(
            clerk_id=clerk_user.clerk_id,
            email=clerk_user.email,
            name=clerk_user.name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Send welcome email
        email_service.send_welcome_email(
            to_email=user.email,
            user_name=user.name or "there",
            dashboard_url=os.environ.get("FRONTEND_URL", "http://localhost:3000")
        )
    
    return user


def check_and_send_notifications(db: Session, loan: Loan, user: User, background_tasks: BackgroundTasks):
    """Check for notification-worthy events and queue emails"""
    if not user.email_notifications:
        return
    
    today = datetime.utcnow().date()
    
    for req in loan.requirements:
        # Check for overdue
        if req.next_due_date and req.next_due_date.date() < today:
            days_overdue = (today - req.next_due_date.date()).days
            if days_overdue <= 1:  # Only notify once when it becomes overdue
                background_tasks.add_task(
                    email_service.send_overdue_alert,
                    to_email=user.email,
                    property_name=loan.property_name,
                    requirement_title=req.title,
                    days_overdue=days_overdue,
                    description=req.plain_language_summary or req.description,
                    document_reference=req.document_reference or "",
                    severity=req.severity
                )
        
        # Check for upcoming (7 days)
        elif req.next_due_date:
            days_until = (req.next_due_date.date() - today).days
            if days_until == 7 or days_until == 1:  # Notify at 7 days and 1 day
                background_tasks.add_task(
                    email_service.send_upcoming_deadline,
                    to_email=user.email,
                    property_name=loan.property_name,
                    requirement_title=req.title,
                    days_until=days_until,
                    due_date=req.next_due_date.strftime("%B %d, %Y"),
                    description=req.plain_language_summary or req.description
                )


# API Endpoints

@app.get("/")
async def root():
    """API info"""
    return {
        "name": "LoanGuard API",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# User endpoints
@app.get("/api/me")
async def get_current_user_info(
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user info"""
    user = get_or_create_user(db, clerk_user)
    loans = get_user_loans(db, user.id)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "email_notifications": user.email_notifications,
        "weekly_summary": user.weekly_summary,
        "loans_count": len(loans)
    }


@app.put("/api/me/notifications")
async def update_notification_prefs(
    prefs: NotificationPrefsRequest,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification preferences"""
    user = get_or_create_user(db, clerk_user)
    user.email_notifications = prefs.email_notifications
    user.weekly_summary = prefs.weekly_summary
    db.commit()
    
    return {"message": "Preferences updated"}


# Loan endpoints
@app.get("/api/loans")
async def list_loans(
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all loans for the current user"""
    user = get_or_create_user(db, clerk_user)
    loans = get_user_loans(db, user.id)
    
    return {
        "loans": [
            {
                "id": loan.id,
                "loan_id": loan.loan_id,
                "property_name": loan.property_name,
                "borrower_name": loan.borrower_name,
                "lender_name": loan.lender_name,
                "original_loan_amount": loan.original_loan_amount,
                "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
                "compliance_score": loan.compliance_score,
                "requirements_count": len(loan.requirements),
                "issues_count": len([r for r in loan.requirements if r.status in ['non_compliant', 'at_risk', 'overdue']])
            }
            for loan in loans
        ],
        "total": len(loans)
    }


@app.post("/api/loans/upload")
async def upload_loan_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    loan_id: Optional[str] = None,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and analyze a loan document"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    user = get_or_create_user(db, clerk_user)
    
    # Generate loan ID if not provided
    if not loan_id:
        existing_count = len(get_user_loans(db, user.id))
        loan_id = f"LOAN-{existing_count + 1:03d}"
    
    # Check for duplicate
    existing = db.query(Loan).filter(Loan.loan_id == loan_id, Loan.owner_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Loan {loan_id} already exists")
    
    # Save uploaded file temporarily
    temp_path = f"/tmp/{file.filename}"
    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)
    
    try:
        # Extract text
        parser = LoanDocumentParser()
        document_text = parser.extract_for_analysis(temp_path)
        
        # Extract requirements
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            extractor = RequirementExtractor(api_key)
        else:
            extractor = MockExtractor()
        
        profile = extractor.extract_requirements(document_text, loan_id)
        
        # Save to database
        loan = create_loan_from_profile(db, profile, user.id)
        
        return {
            "loan_id": loan.loan_id,
            "property_name": loan.property_name,
            "requirements_count": len(loan.requirements),
            "compliance_score": loan.compliance_score,
            "message": f"Successfully analyzed document and extracted {len(loan.requirements)} requirements"
        }
    
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/loans/demo")
async def create_demo_loan(
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a demo loan with sample data"""
    user = get_or_create_user(db, clerk_user)
    
    # Check if user already has demo loan
    existing = db.query(Loan).filter(Loan.loan_id == "DEMO-001", Loan.owner_id == user.id).first()
    if existing:
        return {
            "loan_id": existing.loan_id,
            "message": "Demo loan already exists",
            "requirements_count": len(existing.requirements)
        }
    
    # Create demo
    extractor = MockExtractor()
    profile = extractor.extract_requirements("", "DEMO-001")
    loan = create_loan_from_profile(db, profile, user.id)
    
    return {
        "loan_id": loan.loan_id,
        "property_name": loan.property_name,
        "requirements_count": len(loan.requirements),
        "message": "Demo loan created with sample requirements"
    }


@app.get("/api/loans/{loan_id}")
async def get_loan(
    loan_id: str,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full loan details"""
    user = get_or_create_user(db, clerk_user)
    loan = get_loan_by_id(db, loan_id, user.id)
    
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    return {
        "id": loan.id,
        "loan_id": loan.loan_id,
        "property_name": loan.property_name,
        "property_address": loan.property_address,
        "borrower_name": loan.borrower_name,
        "lender_name": loan.lender_name,
        "original_loan_amount": loan.original_loan_amount,
        "current_balance": loan.current_balance,
        "interest_rate": loan.interest_rate,
        "origination_date": loan.origination_date.isoformat() if loan.origination_date else None,
        "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
        "compliance_score": loan.compliance_score,
        "requirements": [
            {
                "id": r.id,
                "requirement_id": r.requirement_id,
                "title": r.title,
                "category": r.category,
                "description": r.description,
                "plain_language_summary": r.plain_language_summary,
                "original_text": r.original_text,
                "document_reference": r.document_reference,
                "severity": r.severity,
                "status": r.status,
                "deadline_description": r.deadline_description,
                "deadline_frequency": r.deadline_frequency,
                "next_due_date": r.next_due_date.isoformat() if r.next_due_date else None,
                "threshold_metric": r.threshold_metric,
                "threshold_value": r.threshold_value,
                "threshold_unit": r.threshold_unit,
                "current_value": r.current_value,
                "cure_period_days": r.cure_period_days,
                "notes": r.notes
            }
            for r in loan.requirements
        ]
    }


@app.get("/api/loans/{loan_id}/requirements")
async def get_loan_requirements(
    loan_id: str,
    category: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get loan requirements with optional filters"""
    user = get_or_create_user(db, clerk_user)
    loan = get_loan_by_id(db, loan_id, user.id)
    
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    requirements = loan.requirements
    
    # Apply filters
    if category:
        requirements = [r for r in requirements if r.category == category]
    if status:
        requirements = [r for r in requirements if r.status == status]
    if severity:
        requirements = [r for r in requirements if r.severity == severity]
    
    return {
        "loan_id": loan_id,
        "total": len(requirements),
        "requirements": [
            {
                "id": r.id,
                "requirement_id": r.requirement_id,
                "title": r.title,
                "category": r.category,
                "plain_language_summary": r.plain_language_summary,
                "severity": r.severity,
                "status": r.status,
                "deadline_description": r.deadline_description,
                "next_due_date": r.next_due_date.isoformat() if r.next_due_date else None
            }
            for r in requirements
        ]
    }


@app.put("/api/loans/{loan_id}/requirements/{requirement_id}/status")
async def update_requirement_status(
    loan_id: str,
    requirement_id: str,
    update: UpdateStatusRequest,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the status of a requirement"""
    user = get_or_create_user(db, clerk_user)
    loan = get_loan_by_id(db, loan_id, user.id)
    
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    requirement = None
    for r in loan.requirements:
        if r.requirement_id == requirement_id:
            requirement = r
            break
    
    if not requirement:
        raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")
    
    valid_statuses = ['compliant', 'non_compliant', 'at_risk', 'pending', 'unknown']
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Record the change
    old_status = requirement.status
    
    # Create event
    event = ComplianceEvent(
        requirement_id=requirement_id,
        event_type="status_change",
        description=f"Status changed from {old_status} to {update.status}",
        old_status=old_status,
        new_status=update.status,
        user_id=user.id,
        loan_id=loan.id
    )
    db.add(event)
    
    # Update requirement
    requirement.status = update.status
    requirement.last_checked = datetime.utcnow()
    if update.notes:
        requirement.notes = update.notes
    
    # Recalculate compliance score
    loan.compliance_score = loan.calculate_compliance_score()
    
    db.commit()
    
    return {
        "message": "Status updated",
        "requirement_id": requirement_id,
        "old_status": old_status,
        "new_status": update.status,
        "compliance_score": loan.compliance_score
    }


@app.delete("/api/loans/{loan_id}")
async def delete_loan(
    loan_id: str,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a loan"""
    user = get_or_create_user(db, clerk_user)
    loan = get_loan_by_id(db, loan_id, user.id)
    
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    db.delete(loan)
    db.commit()
    
    return {"message": f"Loan {loan_id} deleted"}


# Dashboard summary
@app.get("/api/dashboard")
async def get_dashboard_summary(
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard summary for the current user"""
    user = get_or_create_user(db, clerk_user)
    loans = get_user_loans(db, user.id)
    
    total_loans = len(loans)
    total_exposure = sum(l.original_loan_amount or 0 for l in loans)
    
    all_requirements = []
    for loan in loans:
        all_requirements.extend(loan.requirements)
    
    overdue = len([r for r in all_requirements if r.status == 'non_compliant'])
    at_risk = len([r for r in all_requirements if r.status == 'at_risk'])
    compliant = len([r for r in all_requirements if r.status == 'compliant'])
    
    avg_score = sum(l.compliance_score for l in loans) / total_loans if total_loans > 0 else 0
    
    return {
        "user_name": user.name or user.email,
        "total_loans": total_loans,
        "total_exposure": total_exposure,
        "average_compliance_score": round(avg_score),
        "overdue_count": overdue,
        "at_risk_count": at_risk,
        "compliant_count": compliant,
        "loans": [
            {
                "loan_id": l.loan_id,
                "property_name": l.property_name,
                "compliance_score": l.compliance_score,
                "issues": len([r for r in l.requirements if r.status in ['non_compliant', 'at_risk']])
            }
            for l in sorted(loans, key=lambda x: x.compliance_score)
        ]
    }


# Report generation
@app.get("/api/loans/{loan_id}/report")
async def generate_loan_report(
    loan_id: str,
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate HTML compliance report"""
    user = get_or_create_user(db, clerk_user)
    loan = get_loan_by_id(db, loan_id, user.id)
    
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    # Convert to profile format for formatter
    from .models import LoanProfile, LoanRequirement as LRModel, RequirementCategory, Severity, ComplianceStatus, Deadline, Threshold, Frequency
    
    profile = LoanProfile(
        loan_id=loan.loan_id,
        loan_name=loan.property_name,
        property_name=loan.property_name,
        borrower_name=loan.borrower_name,
        lender_name=loan.lender_name,
        original_loan_amount=loan.original_loan_amount,
        maturity_date=loan.maturity_date.isoformat() if loan.maturity_date else None
    )
    
    for r in loan.requirements:
        deadline = None
        if r.deadline_description:
            deadline = Deadline(
                description=r.deadline_description,
                frequency=Frequency(r.deadline_frequency) if r.deadline_frequency else Frequency.AS_NEEDED
            )
        
        threshold = None
        if r.threshold_metric:
            threshold = Threshold(
                metric=r.threshold_metric,
                operator=r.threshold_operator or ">=",
                value=r.threshold_value or 0,
                unit=r.threshold_unit
            )
        
        req = LRModel(
            id=r.requirement_id,
            title=r.title,
            category=RequirementCategory(r.category) if r.category else RequirementCategory.OTHER,
            description=r.description or "",
            plain_language_summary=r.plain_language_summary or "",
            original_text=r.original_text or "",
            document_reference=r.document_reference or "",
            deadline=deadline,
            threshold=threshold,
            severity=Severity(r.severity) if r.severity else Severity.MEDIUM,
            status=ComplianceStatus(r.status) if r.status else ComplianceStatus.UNKNOWN
        )
        profile.requirements.append(req)
    
    formatter = HTMLFormatter()
    html = formatter.format(profile)
    
    return HTMLResponse(content=html)


# Webhook for Clerk events
@app.post("/api/webhooks/clerk")
async def clerk_webhook(request):
    """Handle Clerk webhook events"""
    # In production, verify the webhook signature
    payload = await request.json()
    event_type = payload.get("type")
    
    if event_type == "user.created":
        # Could send welcome email here
        pass
    elif event_type == "user.deleted":
        # Could clean up user data here
        pass
    
    return {"received": True}


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the API server"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
