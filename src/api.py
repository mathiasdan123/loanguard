"""
FastAPI server for the Loan Compliance Agent.
Provides a REST API for agents and applications to query loan compliance data.
"""

import os
import json
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

from .models import LoanProfile, ComplianceStatus, RequirementCategory
from .pdf_extractor import PDFExtractor, LoanDocumentParser
from .extractor import RequirementExtractor, MockExtractor
from .formatters import JSONFormatter, MarkdownFormatter, HTMLFormatter


# Initialize FastAPI app
app = FastAPI(
    title="Loan Compliance Agent API",
    description="""
    API for extracting and querying loan compliance requirements.
    
    Designed for:
    - AI agents to query loan compliance status
    - Advisors to generate compliance reports
    - Borrowers to understand their obligations
    
    ## Features
    - Upload loan documents (PDF) for analysis
    - Query requirements by category, severity, or status
    - Get plain-language explanations of complex requirements
    - Track compliance deadlines
    """,
    version="1.0.0"
)

# In-memory storage for demo (would use a database in production)
loan_profiles: dict[str, LoanProfile] = {}


# Request/Response models
class LoanUploadResponse(BaseModel):
    loan_id: str
    property_name: str
    total_requirements: int
    message: str


class RequirementResponse(BaseModel):
    id: str
    title: str
    category: str
    plain_language_summary: str
    deadline: Optional[dict]
    threshold: Optional[dict]
    severity: str
    status: str


class ComplianceSummaryResponse(BaseModel):
    loan_id: str
    property_name: str
    total_requirements: int
    critical_items: int
    non_compliant_count: int
    at_risk_count: int
    by_category: dict
    by_status: dict


class UpdateStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


# API Endpoints

@app.get("/")
async def root():
    """API root - returns basic info"""
    return {
        "name": "Loan Compliance Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /loans/upload": "Upload a loan document for analysis",
            "GET /loans": "List all analyzed loans",
            "GET /loans/{loan_id}": "Get full loan profile",
            "GET /loans/{loan_id}/requirements": "Query requirements",
            "GET /loans/{loan_id}/summary": "Get compliance summary",
            "GET /loans/{loan_id}/report": "Generate HTML report"
        }
    }


@app.post("/loans/upload", response_model=LoanUploadResponse)
async def upload_loan_document(
    file: UploadFile = File(...),
    loan_id: Optional[str] = None,
    use_mock: bool = Query(False, description="Use mock extractor (no API key needed)")
):
    """
    Upload a loan document for analysis.
    
    The document will be parsed and requirements extracted using Claude.
    
    - **file**: PDF file of the loan document
    - **loan_id**: Optional custom loan ID (auto-generated if not provided)
    - **use_mock**: If true, uses mock data instead of calling Claude API
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Generate loan ID if not provided
    if not loan_id:
        loan_id = f"LOAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Save uploaded file temporarily
    temp_path = f"/tmp/{file.filename}"
    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)
    
    try:
        # Extract text from PDF
        parser = LoanDocumentParser()
        document_text = parser.extract_for_analysis(temp_path)
        
        # Extract requirements
        if use_mock:
            extractor = MockExtractor()
        else:
            try:
                extractor = RequirementExtractor()
            except ValueError:
                # No API key, fall back to mock
                extractor = MockExtractor()
        
        profile = extractor.extract_requirements(document_text, loan_id)
        
        # Store in memory
        loan_profiles[loan_id] = profile
        
        return LoanUploadResponse(
            loan_id=loan_id,
            property_name=profile.property_name,
            total_requirements=len(profile.requirements),
            message=f"Successfully extracted {len(profile.requirements)} requirements"
        )
    
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/loans/demo")
async def create_demo_loan():
    """
    Create a demo loan with sample requirements.
    Useful for testing without uploading a document.
    """
    extractor = MockExtractor()
    profile = extractor.extract_requirements("", "DEMO-001")
    loan_profiles["DEMO-001"] = profile
    
    return {
        "loan_id": "DEMO-001",
        "message": "Demo loan created with sample requirements",
        "total_requirements": len(profile.requirements)
    }


@app.get("/loans")
async def list_loans():
    """List all analyzed loans"""
    return {
        "loans": [
            {
                "loan_id": lid,
                "property_name": profile.property_name,
                "borrower_name": profile.borrower_name,
                "total_requirements": len(profile.requirements)
            }
            for lid, profile in loan_profiles.items()
        ]
    }


@app.get("/loans/{loan_id}")
async def get_loan(loan_id: str, format: str = Query("json", enum=["json", "markdown"])):
    """
    Get full loan profile.
    
    - **format**: Output format (json or markdown)
    """
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    
    if format == "markdown":
        formatter = MarkdownFormatter()
        return {"content": formatter.format(profile), "format": "markdown"}
    
    return profile.to_dict()


@app.get("/loans/{loan_id}/requirements")
async def get_requirements(
    loan_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title/description")
):
    """
    Query loan requirements with filters.
    
    This endpoint is designed for agent queries like:
    - "What are my reporting requirements?"
    - "Show me all critical items"
    - "What's non-compliant?"
    """
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    requirements = profile.requirements
    
    # Apply filters
    if category:
        try:
            cat_enum = RequirementCategory(category)
            requirements = [r for r in requirements if r.category == cat_enum]
        except ValueError:
            pass
    
    if severity:
        requirements = [r for r in requirements if r.severity.value == severity]
    
    if status:
        requirements = [r for r in requirements if r.status.value == status]
    
    if search:
        search_lower = search.lower()
        requirements = [
            r for r in requirements 
            if search_lower in r.title.lower() 
            or search_lower in r.description.lower()
            or search_lower in r.plain_language_summary.lower()
        ]
    
    return {
        "loan_id": loan_id,
        "total_matched": len(requirements),
        "requirements": [
            {
                "id": r.id,
                "title": r.title,
                "category": r.category.value,
                "plain_language_summary": r.plain_language_summary,
                "deadline": r.deadline.to_dict() if r.deadline else None,
                "threshold": r.threshold.to_dict() if r.threshold else None,
                "severity": r.severity.value,
                "status": r.status.value,
                "document_reference": r.document_reference
            }
            for r in requirements
        ]
    }


@app.get("/loans/{loan_id}/requirements/{requirement_id}")
async def get_requirement_detail(loan_id: str, requirement_id: str):
    """Get detailed information about a specific requirement"""
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    
    for req in profile.requirements:
        if req.id == requirement_id:
            return req.to_dict()
    
    raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")


@app.put("/loans/{loan_id}/requirements/{requirement_id}/status")
async def update_requirement_status(
    loan_id: str, 
    requirement_id: str, 
    update: UpdateStatusRequest
):
    """Update the compliance status of a requirement"""
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    
    for req in profile.requirements:
        if req.id == requirement_id:
            try:
                req.status = ComplianceStatus(update.status)
                req.last_checked = datetime.now().isoformat()
                if update.notes:
                    req.notes = update.notes
                return {"message": "Status updated", "requirement": req.to_dict()}
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid status. Must be one of: {[s.value for s in ComplianceStatus]}"
                )
    
    raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")


@app.get("/loans/{loan_id}/summary", response_model=ComplianceSummaryResponse)
async def get_compliance_summary(loan_id: str):
    """
    Get a compliance summary for the loan.
    
    Useful for quick status checks by agents:
    - "Am I compliant with my loan?"
    - "How many items need attention?"
    """
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    summary = profile.compliance_summary()
    
    return ComplianceSummaryResponse(
        loan_id=loan_id,
        property_name=profile.property_name,
        total_requirements=summary["total_requirements"],
        critical_items=summary["critical_items"],
        non_compliant_count=summary["non_compliant_count"],
        at_risk_count=summary["at_risk_count"],
        by_category=summary["by_category"],
        by_status=summary["by_status"]
    )


@app.get("/loans/{loan_id}/deadlines")
async def get_deadlines(
    loan_id: str,
    frequency: Optional[str] = Query(None, description="Filter by frequency")
):
    """
    Get all requirements with deadlines.
    
    Useful for questions like:
    - "What's due this month?"
    - "What are my quarterly obligations?"
    """
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    
    deadlines = []
    for req in profile.requirements:
        if req.deadline:
            if frequency and req.deadline.frequency.value != frequency:
                continue
            deadlines.append({
                "requirement_id": req.id,
                "title": req.title,
                "category": req.category.value,
                "deadline": req.deadline.to_dict(),
                "severity": req.severity.value,
                "plain_language": req.plain_language_summary
            })
    
    # Sort by frequency for easier reading
    frequency_order = ["monthly", "quarterly", "semi_annual", "annual", "one_time", "as_needed", "upon_request"]
    deadlines.sort(key=lambda x: frequency_order.index(x["deadline"]["frequency"]) if x["deadline"]["frequency"] in frequency_order else 99)
    
    return {
        "loan_id": loan_id,
        "total_with_deadlines": len(deadlines),
        "deadlines": deadlines
    }


@app.get("/loans/{loan_id}/report", response_class=HTMLResponse)
async def get_html_report(loan_id: str):
    """Generate a formatted HTML compliance report"""
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    formatter = HTMLFormatter()
    
    return formatter.format(profile)


@app.get("/loans/{loan_id}/checklist")
async def get_checklist(loan_id: str):
    """
    Get requirements as a simple checklist.
    
    Returns markdown-formatted checklist for easy copy/paste.
    """
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    formatter = MarkdownFormatter()
    
    return {"checklist": formatter.format_checklist(profile)}


# Agent-friendly query endpoint
@app.post("/loans/{loan_id}/ask")
async def ask_about_loan(loan_id: str, question: str = Query(..., description="Natural language question")):
    """
    Answer natural language questions about the loan.
    
    Example questions:
    - "What are my reporting deadlines?"
    - "What happens if my DSCR drops below the threshold?"
    - "Do I need lender approval to sign a new lease?"
    
    Note: This endpoint provides structured data. For full natural language
    responses, the calling agent should interpret this data.
    """
    if loan_id not in loan_profiles:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found")
    
    profile = loan_profiles[loan_id]
    question_lower = question.lower()
    
    # Simple keyword-based routing (an agent would do more sophisticated NLU)
    relevant_requirements = []
    
    # Detect question type and filter accordingly
    if any(word in question_lower for word in ["deadline", "due", "when", "submit"]):
        relevant_requirements = [r for r in profile.requirements if r.deadline]
    
    elif any(word in question_lower for word in ["dscr", "covenant", "ratio", "threshold"]):
        relevant_requirements = [
            r for r in profile.requirements 
            if r.category == RequirementCategory.COVENANT_COMPLIANCE or r.threshold
        ]
    
    elif any(word in question_lower for word in ["insurance"]):
        relevant_requirements = [
            r for r in profile.requirements 
            if r.category == RequirementCategory.INSURANCE
        ]
    
    elif any(word in question_lower for word in ["lease", "tenant"]):
        relevant_requirements = [
            r for r in profile.requirements 
            if r.category == RequirementCategory.LEASING
        ]
    
    elif any(word in question_lower for word in ["report", "financial", "statement"]):
        relevant_requirements = [
            r for r in profile.requirements 
            if r.category == RequirementCategory.FINANCIAL_REPORTING
        ]
    
    elif any(word in question_lower for word in ["reserve", "escrow"]):
        relevant_requirements = [
            r for r in profile.requirements 
            if r.category in [RequirementCategory.RESERVE_FUNDING, RequirementCategory.TAX_ESCROW]
        ]
    
    else:
        # Return all requirements if no specific category detected
        relevant_requirements = profile.requirements
    
    return {
        "question": question,
        "loan_id": loan_id,
        "relevant_requirements": [
            {
                "id": r.id,
                "title": r.title,
                "plain_language_summary": r.plain_language_summary,
                "deadline": r.deadline.description if r.deadline else None,
                "threshold": r.threshold.human_readable() if r.threshold else None,
                "severity": r.severity.value
            }
            for r in relevant_requirements
        ],
        "total_found": len(relevant_requirements)
    }


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the API server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
