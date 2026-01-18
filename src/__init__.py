"""
Loan Compliance Agent

A tool for extracting and managing loan document compliance requirements.
Designed for borrowers, advisors, and AI agents to understand and track
operational obligations in commercial real estate loans.
"""

from .models import (
    LoanProfile,
    LoanRequirement,
    RequirementCategory,
    ComplianceStatus,
    Severity,
    Frequency,
    Deadline,
    Threshold,
    ComplianceEvent
)

from .pdf_extractor import PDFExtractor, LoanDocumentParser, ExtractedDocument
from .extractor import RequirementExtractor, MockExtractor
from .formatters import JSONFormatter, MarkdownFormatter, HTMLFormatter

__version__ = "1.0.0"
__all__ = [
    # Models
    "LoanProfile",
    "LoanRequirement", 
    "RequirementCategory",
    "ComplianceStatus",
    "Severity",
    "Frequency",
    "Deadline",
    "Threshold",
    "ComplianceEvent",
    
    # Extractors
    "PDFExtractor",
    "LoanDocumentParser",
    "ExtractedDocument",
    "RequirementExtractor",
    "MockExtractor",
    
    # Formatters
    "JSONFormatter",
    "MarkdownFormatter", 
    "HTMLFormatter"
]
