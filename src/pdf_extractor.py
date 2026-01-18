"""
PDF text extraction module.
Handles extracting text from loan documents with structure preservation.
"""

import os
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class ExtractedPage:
    """Represents extracted content from a single page"""
    page_number: int
    text: str
    tables: list  # List of table data
    

@dataclass
class ExtractedDocument:
    """Represents all extracted content from a PDF"""
    filename: str
    total_pages: int
    pages: list  # List[ExtractedPage]
    full_text: str
    metadata: dict
    
    def get_text_around_keyword(self, keyword: str, context_chars: int = 500) -> list:
        """Find all occurrences of a keyword and return surrounding context"""
        results = []
        text_lower = self.full_text.lower()
        keyword_lower = keyword.lower()
        
        start = 0
        while True:
            pos = text_lower.find(keyword_lower, start)
            if pos == -1:
                break
            
            context_start = max(0, pos - context_chars)
            context_end = min(len(self.full_text), pos + len(keyword) + context_chars)
            
            results.append({
                "keyword": keyword,
                "position": pos,
                "context": self.full_text[context_start:context_end]
            })
            
            start = pos + 1
        
        return results
    
    def find_sections(self) -> list:
        """Attempt to identify document sections based on common patterns"""
        section_patterns = [
            r'(?:ARTICLE|SECTION|Article|Section)\s+([IVXLCDM\d]+)[.:]?\s*([A-Z][A-Za-z\s]+)',
            r'(\d+\.\d+)\s+([A-Z][A-Za-z\s]+)',
            r'^([A-Z][A-Z\s]+)$',  # All caps headers
        ]
        
        sections = []
        for pattern in section_patterns:
            matches = re.finditer(pattern, self.full_text, re.MULTILINE)
            for match in matches:
                sections.append({
                    "match": match.group(0),
                    "position": match.start(),
                    "groups": match.groups()
                })
        
        return sorted(sections, key=lambda x: x["position"])


class PDFExtractor:
    """Extracts text and structure from PDF loan documents"""
    
    def __init__(self):
        self.pdfplumber_available = False
        self.pypdf_available = False
        
        try:
            import pdfplumber
            self.pdfplumber_available = True
        except ImportError:
            pass
        
        try:
            from pypdf import PdfReader
            self.pypdf_available = True
        except ImportError:
            pass
    
    def extract(self, pdf_path: str) -> ExtractedDocument:
        """Extract text from a PDF file"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Prefer pdfplumber for better table extraction
        if self.pdfplumber_available:
            return self._extract_with_pdfplumber(pdf_path)
        elif self.pypdf_available:
            return self._extract_with_pypdf(pdf_path)
        else:
            raise RuntimeError("No PDF library available. Install pdfplumber or pypdf.")
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> ExtractedDocument:
        """Extract using pdfplumber (better for tables)"""
        import pdfplumber
        
        pages = []
        full_text_parts = []
        
        with pdfplumber.open(pdf_path) as pdf:
            metadata = pdf.metadata or {}
            total_pages = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                
                pages.append(ExtractedPage(
                    page_number=i + 1,
                    text=text,
                    tables=tables
                ))
                
                full_text_parts.append(f"\n--- Page {i + 1} ---\n{text}")
        
        return ExtractedDocument(
            filename=os.path.basename(pdf_path),
            total_pages=total_pages,
            pages=pages,
            full_text="\n".join(full_text_parts),
            metadata=dict(metadata)
        )
    
    def _extract_with_pypdf(self, pdf_path: str) -> ExtractedDocument:
        """Extract using pypdf (fallback)"""
        from pypdf import PdfReader
        
        reader = PdfReader(pdf_path)
        pages = []
        full_text_parts = []
        
        metadata = {}
        if reader.metadata:
            metadata = {
                "title": reader.metadata.title,
                "author": reader.metadata.author,
                "subject": reader.metadata.subject,
                "creator": reader.metadata.creator
            }
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            
            pages.append(ExtractedPage(
                page_number=i + 1,
                text=text,
                tables=[]  # pypdf doesn't extract tables
            ))
            
            full_text_parts.append(f"\n--- Page {i + 1} ---\n{text}")
        
        return ExtractedDocument(
            filename=os.path.basename(pdf_path),
            total_pages=len(reader.pages),
            pages=pages,
            full_text="\n".join(full_text_parts),
            metadata=metadata
        )


class LoanDocumentParser:
    """
    Specialized parser for loan documents.
    Identifies common sections and structures in CRE loan agreements.
    """
    
    # Common section keywords in loan documents
    SECTION_KEYWORDS = {
        "financial_reporting": [
            "financial statements", "financial reporting", "annual budget",
            "operating statements", "rent roll", "occupancy report",
            "quarterly report", "monthly report", "annual report"
        ],
        "covenants": [
            "debt service coverage", "DSCR", "loan to value", "LTV",
            "debt yield", "coverage ratio", "financial covenant",
            "covenant", "minimum", "maximum", "shall maintain", "shall not exceed"
        ],
        "insurance": [
            "insurance", "property insurance", "liability insurance",
            "flood insurance", "earthquake insurance", "policy",
            "certificate of insurance", "additional insured"
        ],
        "reserves": [
            "reserve", "escrow", "tax escrow", "insurance escrow",
            "replacement reserve", "capital reserve", "tenant improvement",
            "TI reserve", "leasing commission", "LC reserve"
        ],
        "property_management": [
            "property manager", "management agreement", "property management",
            "manager", "managing agent"
        ],
        "leasing": [
            "leasing", "tenant", "lease approval", "major lease",
            "lease consent", "sublease", "assignment"
        ],
        "defaults": [
            "event of default", "default", "acceleration", "cure period",
            "notice of default", "material breach"
        ],
        "transfers": [
            "transfer", "assumption", "sale", "conveyance",
            "change of control", "prohibited transfer"
        ]
    }
    
    def __init__(self):
        self.extractor = PDFExtractor()
    
    def parse(self, pdf_path: str) -> dict:
        """Parse a loan document and identify key sections"""
        doc = self.extractor.extract(pdf_path)
        
        # Find relevant sections for each category
        categorized_sections = {}
        for category, keywords in self.SECTION_KEYWORDS.items():
            categorized_sections[category] = []
            for keyword in keywords:
                matches = doc.get_text_around_keyword(keyword, context_chars=1000)
                for match in matches:
                    categorized_sections[category].append({
                        "keyword": keyword,
                        "context": match["context"],
                        "position": match["position"]
                    })
        
        # Remove duplicates (same position)
        for category in categorized_sections:
            seen_positions = set()
            unique = []
            for item in categorized_sections[category]:
                if item["position"] not in seen_positions:
                    seen_positions.add(item["position"])
                    unique.append(item)
            categorized_sections[category] = unique
        
        return {
            "document": doc,
            "sections": categorized_sections,
            "metadata": doc.metadata
        }
    
    def extract_for_analysis(self, pdf_path: str) -> str:
        """
        Extract text optimized for LLM analysis.
        Returns a structured text representation.
        """
        parsed = self.parse(pdf_path)
        doc = parsed["document"]
        
        output_parts = [
            f"# Loan Document: {doc.filename}",
            f"Total Pages: {doc.total_pages}",
            "",
            "## Full Document Text",
            "",
            doc.full_text
        ]
        
        return "\n".join(output_parts)
