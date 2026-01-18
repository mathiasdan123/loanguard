"""
Claude-powered loan requirement extraction.
Uses Claude API to intelligently extract and categorize loan requirements.
"""

import json
import os
import re
from typing import Optional

# httpx is optional - only needed for real API calls
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .models import (
    LoanProfile, LoanRequirement, RequirementCategory, Frequency,
    ComplianceStatus, Severity, Deadline, Threshold
)


# Extraction prompt template
EXTRACTION_PROMPT = """You are an expert commercial real estate loan analyst. Your task is to extract ALL operational requirements from this loan document that a borrower must comply with.

For each requirement, identify:
1. What the borrower must do
2. When/how often they must do it
3. What happens if they don't (severity)
4. Any specific thresholds or limits
5. The exact document reference (section/page)

Focus especially on:
- Financial reporting requirements (when to submit statements, budgets, rent rolls)
- Covenant compliance (DSCR, LTV, debt yield thresholds)
- Insurance requirements (types, amounts, deadlines)
- Reserve/escrow requirements (amounts, funding schedules)
- Property management requirements
- Leasing restrictions and approval requirements
- Capital improvement obligations
- Tax and insurance escrow requirements

IMPORTANT: Extract requirements that are OPERATIONAL - things the borrower must actually DO, not just legal boilerplate.

Here is the loan document text:

<document>
{document_text}
</document>

Please respond with a JSON object in this exact format:
{{
    "loan_info": {{
        "borrower_name": "extracted or null",
        "lender_name": "extracted or null", 
        "property_name": "extracted or null",
        "loan_amount": number or null,
        "origination_date": "YYYY-MM-DD or null",
        "maturity_date": "YYYY-MM-DD or null"
    }},
    "requirements": [
        {{
            "title": "Brief title for the requirement",
            "category": "one of: financial_reporting, covenant_compliance, insurance, reserve_funding, property_management, leasing, capital_improvements, tax_escrow, environmental, legal_entity, other",
            "description": "Detailed description of what must be done",
            "plain_language_summary": "Simple, plain English explanation a property owner would understand",
            "original_text": "The actual text from the document (abbreviated if very long)",
            "document_reference": "Section X.X, Page Y",
            "deadline": {{
                "description": "When this is due",
                "frequency": "one of: monthly, quarterly, semi_annual, annual, one_time, as_needed, upon_request",
                "days_after_period_end": number or null,
                "day_of_month": number or null
            }},
            "threshold": {{
                "metric": "e.g., DSCR, LTV",
                "operator": ">=, <=, >, <, ==, between",
                "value": number,
                "secondary_value": number or null,
                "unit": "%, $, x, etc."
            }} or null,
            "severity": "one of: critical, high, medium, low",
            "cure_period_days": number or null
        }}
    ]
}}

Extract ALL requirements you can find. Be thorough."""


class RequirementExtractor:
    """Uses Claude to extract requirements from loan documents"""
    
    def __init__(self, api_key: Optional[str] = None):
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx library required for API calls. Install with: pip install httpx")
        
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key parameter required")
        
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-sonnet-4-20250514"
    
    def extract_requirements(self, document_text: str, loan_id: str = "LOAN-001") -> LoanProfile:
        """
        Extract requirements from document text using Claude.
        
        Args:
            document_text: The full text of the loan document
            loan_id: Identifier for this loan
            
        Returns:
            LoanProfile with extracted requirements
        """
        # Truncate if too long (Claude has context limits)
        max_chars = 150000  # Leave room for prompt and response
        if len(document_text) > max_chars:
            # Take beginning and end, which usually have key terms
            half = max_chars // 2
            document_text = document_text[:half] + "\n\n[...document truncated...]\n\n" + document_text[-half:]
        
        prompt = EXTRACTION_PROMPT.format(document_text=document_text)
        
        response = self._call_claude(prompt)
        
        # Parse the JSON response
        parsed = self._parse_response(response)
        
        # Convert to our data models
        return self._build_loan_profile(parsed, loan_id)
    
    def _call_claude(self, prompt: str) -> str:
        """Make API call to Claude"""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse Claude's JSON response"""
        # Try to find JSON in the response
        # Sometimes Claude wraps it in markdown code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("Could not find JSON in Claude's response")
        
        return json.loads(json_str)
    
    def _build_loan_profile(self, parsed: dict, loan_id: str) -> LoanProfile:
        """Convert parsed JSON to LoanProfile"""
        loan_info = parsed.get("loan_info", {})
        
        profile = LoanProfile(
            loan_id=loan_id,
            loan_name=f"Loan {loan_id}",
            property_name=loan_info.get("property_name") or "Unknown Property",
            borrower_name=loan_info.get("borrower_name") or "Unknown Borrower",
            lender_name=loan_info.get("lender_name") or "Unknown Lender",
            original_loan_amount=loan_info.get("loan_amount") or 0,
            origination_date=loan_info.get("origination_date"),
            maturity_date=loan_info.get("maturity_date")
        )
        
        # Convert requirements
        for i, req_data in enumerate(parsed.get("requirements", [])):
            req = self._build_requirement(req_data, i + 1)
            profile.requirements.append(req)
        
        return profile
    
    def _build_requirement(self, data: dict, index: int) -> LoanRequirement:
        """Convert a requirement dict to LoanRequirement"""
        # Parse category
        category_str = data.get("category", "other").lower().replace(" ", "_")
        try:
            category = RequirementCategory(category_str)
        except ValueError:
            category = RequirementCategory.OTHER
        
        # Parse deadline
        deadline = None
        if data.get("deadline"):
            dl = data["deadline"]
            freq_str = dl.get("frequency", "as_needed").lower().replace(" ", "_")
            try:
                frequency = Frequency(freq_str)
            except ValueError:
                frequency = Frequency.AS_NEEDED
            
            deadline = Deadline(
                description=dl.get("description", ""),
                days_after_period_end=dl.get("days_after_period_end"),
                day_of_month=dl.get("day_of_month"),
                frequency=frequency
            )
        
        # Parse threshold
        threshold = None
        if data.get("threshold"):
            th = data["threshold"]
            threshold = Threshold(
                metric=th.get("metric", ""),
                operator=th.get("operator", ">="),
                value=th.get("value", 0),
                secondary_value=th.get("secondary_value"),
                unit=th.get("unit")
            )
        
        # Parse severity
        severity_str = data.get("severity", "medium").lower()
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.MEDIUM
        
        return LoanRequirement(
            id=f"REQ-{index:03d}",
            title=data.get("title", f"Requirement {index}"),
            category=category,
            description=data.get("description", ""),
            plain_language_summary=data.get("plain_language_summary", ""),
            original_text=data.get("original_text", "")[:500],  # Limit length
            document_reference=data.get("document_reference", ""),
            deadline=deadline,
            threshold=threshold,
            severity=severity,
            cure_period_days=data.get("cure_period_days"),
            status=ComplianceStatus.UNKNOWN
        )


class MockExtractor:
    """
    Mock extractor for testing without API calls.
    Returns sample requirements based on common loan terms.
    """
    
    def extract_requirements(self, document_text: str, loan_id: str = "LOAN-001") -> LoanProfile:
        """Return sample requirements for testing"""
        profile = LoanProfile(
            loan_id=loan_id,
            loan_name=f"Sample Loan {loan_id}",
            property_name="123 Main Street Office Building",
            borrower_name="Sample Borrower LLC",
            lender_name="Sample Bank, N.A.",
            original_loan_amount=10000000,
            origination_date="2024-01-15",
            maturity_date="2029-01-15"
        )
        
        # Add sample requirements
        profile.requirements = [
            LoanRequirement(
                id="REQ-001",
                title="Quarterly Financial Statements",
                category=RequirementCategory.FINANCIAL_REPORTING,
                description="Borrower must deliver quarterly unaudited financial statements",
                plain_language_summary="Send your quarterly financial statements to the lender within 45 days after each quarter ends",
                original_text="Borrower shall deliver to Lender within forty-five (45) days after the end of each fiscal quarter...",
                document_reference="Section 5.1.1",
                deadline=Deadline(
                    description="45 days after quarter end",
                    days_after_period_end=45,
                    frequency=Frequency.QUARTERLY
                ),
                severity=Severity.HIGH
            ),
            LoanRequirement(
                id="REQ-002",
                title="Annual Audited Financials",
                category=RequirementCategory.FINANCIAL_REPORTING,
                description="Borrower must deliver annual audited financial statements",
                plain_language_summary="Have a CPA audit your financials and send the report within 120 days after year end",
                original_text="Borrower shall deliver to Lender within one hundred twenty (120) days after the end of each fiscal year, audited financial statements...",
                document_reference="Section 5.1.2",
                deadline=Deadline(
                    description="120 days after fiscal year end",
                    days_after_period_end=120,
                    frequency=Frequency.ANNUAL
                ),
                severity=Severity.CRITICAL
            ),
            LoanRequirement(
                id="REQ-003",
                title="DSCR Covenant",
                category=RequirementCategory.COVENANT_COMPLIANCE,
                description="Maintain minimum Debt Service Coverage Ratio",
                plain_language_summary="Your property's net operating income divided by your loan payments must be at least 1.25x",
                original_text="Borrower shall maintain a Debt Service Coverage Ratio of not less than 1.25:1.00...",
                document_reference="Section 6.2",
                deadline=Deadline(
                    description="Tested quarterly",
                    frequency=Frequency.QUARTERLY
                ),
                threshold=Threshold(
                    metric="DSCR",
                    operator=">=",
                    value=1.25,
                    unit="x"
                ),
                severity=Severity.CRITICAL,
                cure_period_days=30
            ),
            LoanRequirement(
                id="REQ-004",
                title="Property Insurance",
                category=RequirementCategory.INSURANCE,
                description="Maintain property insurance with specified coverage",
                plain_language_summary="Keep your property insured for full replacement cost. Send proof to lender before each renewal.",
                original_text="Borrower shall maintain property insurance in an amount not less than the full replacement cost...",
                document_reference="Section 4.1",
                deadline=Deadline(
                    description="30 days before policy expiration",
                    frequency=Frequency.ANNUAL
                ),
                severity=Severity.CRITICAL
            ),
            LoanRequirement(
                id="REQ-005",
                title="Replacement Reserve Deposits",
                category=RequirementCategory.RESERVE_FUNDING,
                description="Monthly deposits to replacement reserve",
                plain_language_summary="Deposit $2,500 monthly into your replacement reserve account",
                original_text="Borrower shall deposit with Lender on each Payment Date the sum of $2,500...",
                document_reference="Section 7.3",
                deadline=Deadline(
                    description="Monthly with mortgage payment",
                    day_of_month=1,
                    frequency=Frequency.MONTHLY
                ),
                threshold=Threshold(
                    metric="Monthly Deposit",
                    operator=">=",
                    value=2500,
                    unit="$"
                ),
                severity=Severity.MEDIUM
            ),
            LoanRequirement(
                id="REQ-006",
                title="Monthly Rent Roll",
                category=RequirementCategory.FINANCIAL_REPORTING,
                description="Submit monthly rent roll",
                plain_language_summary="Send a current rent roll showing all tenants, lease terms, and rental rates by the 15th of each month",
                original_text="Borrower shall deliver to Lender by the fifteenth (15th) day of each calendar month a current rent roll...",
                document_reference="Section 5.1.4",
                deadline=Deadline(
                    description="By the 15th of each month",
                    day_of_month=15,
                    frequency=Frequency.MONTHLY
                ),
                severity=Severity.MEDIUM
            ),
            LoanRequirement(
                id="REQ-007",
                title="Major Lease Approval",
                category=RequirementCategory.LEASING,
                description="Lender approval required for major leases",
                plain_language_summary="Get lender approval before signing any lease over 10,000 SF or with a tenant getting more than 3 months free rent",
                original_text="Borrower shall not enter into any lease for more than 10,000 square feet or containing concessions in excess of three (3) months free rent without Lender's prior written consent...",
                document_reference="Section 8.2",
                deadline=Deadline(
                    description="Prior to lease execution",
                    frequency=Frequency.AS_NEEDED
                ),
                severity=Severity.HIGH
            ),
            LoanRequirement(
                id="REQ-008",
                title="Annual Operating Budget",
                category=RequirementCategory.FINANCIAL_REPORTING,
                description="Submit annual operating budget",
                plain_language_summary="Submit next year's operating budget for lender approval by November 15th each year",
                original_text="Not later than November 15 of each year, Borrower shall submit to Lender for approval the proposed annual operating budget...",
                document_reference="Section 5.1.5",
                deadline=Deadline(
                    description="November 15 annually",
                    frequency=Frequency.ANNUAL
                ),
                severity=Severity.MEDIUM
            )
        ]
        
        return profile
