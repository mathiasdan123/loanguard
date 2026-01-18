# Loan Compliance Agent 🏢📋

**Extract, understand, and track loan document requirements — designed for humans AND AI agents.**

## The Problem

Commercial real estate borrowers sign loan documents full of operational requirements they don't fully understand. These documents often run 200+ pages of legalese, with critical obligations buried in cross-references. When borrowers get into trouble, they're often non-compliant on things they didn't even know existed.

> "Loan workouts don't fail because of math or a party's intransigence. They fail because operations lag documents, and no one on the team knows how to close that gap."

## The Solution

This tool:

1. **Parses loan documents** (PDFs) and extracts operational requirements
2. **Translates legalese** into plain-language checklists
3. **Tracks compliance status** — what's due when, what's at risk
4. **Exposes an API** so AI agents can query: "What are my reporting deadlines this quarter?"

## Quick Start

### Installation

```bash
cd loan-compliance-agent
pip install -r requirements.txt
```

### Generate a Demo Report

```bash
# No API key needed - uses sample data
python -m src.cli demo -o demo_report.html
open demo_report.html
```

### Analyze a Real Loan Document

```bash
# Requires ANTHROPIC_API_KEY for AI-powered extraction
export ANTHROPIC_API_KEY="your-key-here"
python -m src.cli analyze loan_document.pdf -o compliance_report.html
```

### Start the API Server

```bash
python -m src.cli serve --port 8000

# API documentation available at:
# http://localhost:8000/docs
```

## For AI Agents

The API is designed to be agent-friendly. Here's how an agent might use it:

### Query Deadlines

```bash
curl http://localhost:8000/loans/DEMO-001/deadlines

# Response:
{
  "loan_id": "DEMO-001",
  "total_with_deadlines": 7,
  "deadlines": [
    {
      "requirement_id": "REQ-006",
      "title": "Monthly Rent Roll",
      "deadline": {
        "description": "By the 15th of each month",
        "frequency": "monthly"
      },
      "severity": "medium"
    },
    ...
  ]
}
```

### Check Covenant Compliance

```bash
curl "http://localhost:8000/loans/DEMO-001/requirements?category=covenant_compliance"

# Response includes thresholds in plain language:
{
  "requirements": [
    {
      "id": "REQ-003",
      "title": "DSCR Covenant",
      "plain_language_summary": "Your property's net operating income divided by your loan payments must be at least 1.25x",
      "threshold": {
        "metric": "DSCR",
        "operator": ">=",
        "value": 1.25,
        "unit": "x"
      }
    }
  ]
}
```

### Ask Natural Language Questions

```bash
curl -X POST "http://localhost:8000/loans/DEMO-001/ask?question=What%20are%20my%20insurance%20requirements"

# Returns relevant requirements with plain-language summaries
```

## Output Formats

### JSON (for agents)
```bash
python -m src.cli analyze loan.pdf -o requirements.json
```

Structured, queryable data with:
- Requirement IDs for tracking
- Category classifications
- Machine-readable deadlines
- Threshold values for automated checks

### HTML (for humans)
```bash
python -m src.cli analyze loan.pdf -o report.html
```

Beautiful, printable report with:
- Visual severity indicators
- Collapsible original document text
- Summary statistics
- Grouped by category

### Markdown (for documentation)
```bash
python -m src.cli analyze loan.pdf -o checklist.md
```

Copy-paste friendly checklist format.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/loans/upload` | POST | Upload a loan document for analysis |
| `/loans/demo` | POST | Create demo loan with sample data |
| `/loans` | GET | List all analyzed loans |
| `/loans/{id}` | GET | Get full loan profile |
| `/loans/{id}/requirements` | GET | Query requirements (with filters) |
| `/loans/{id}/summary` | GET | Get compliance summary |
| `/loans/{id}/deadlines` | GET | Get all deadline items |
| `/loans/{id}/report` | GET | Generate HTML report |
| `/loans/{id}/ask` | POST | Natural language query |

### Filtering Requirements

```bash
# By category
GET /loans/DEMO-001/requirements?category=financial_reporting

# By severity
GET /loans/DEMO-001/requirements?severity=critical

# By status
GET /loans/DEMO-001/requirements?status=non_compliant

# Search
GET /loans/DEMO-001/requirements?search=insurance
```

## Categories

The tool categorizes requirements into:

- **Financial Reporting** - Statements, budgets, rent rolls
- **Covenant Compliance** - DSCR, LTV, debt yield
- **Insurance** - Property, liability, flood
- **Reserve Funding** - Replacement, TI, LC reserves
- **Property Management** - Manager requirements
- **Leasing** - Lease approval, tenant restrictions
- **Capital Improvements** - CapEx requirements
- **Tax/Escrow** - Tax and insurance escrows
- **Environmental** - Environmental compliance
- **Legal Entity** - SPE requirements, ownership

## Architecture

```
loan-compliance-agent/
├── src/
│   ├── models.py        # Data models (LoanProfile, Requirement, etc.)
│   ├── pdf_extractor.py # PDF text extraction
│   ├── extractor.py     # Claude-powered requirement extraction
│   ├── formatters.py    # Output formatters (JSON, MD, HTML)
│   ├── api.py           # FastAPI server
│   └── cli.py           # Command-line interface
├── requirements.txt
└── README.md
```

## How It Works

1. **PDF Extraction**: Uses `pdfplumber` to extract text and tables from loan documents while preserving structure.

2. **AI Analysis**: Sends extracted text to Claude with a specialized prompt that identifies operational requirements, deadlines, thresholds, and severity levels.

3. **Structured Output**: Converts Claude's analysis into structured data models that can be queried programmatically.

4. **Multi-Format Output**: Generates both human-readable reports and machine-parseable JSON.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For real analysis | Claude API key for document extraction |

## Use Cases

### For Borrowers
- Understand what you actually agreed to
- Track upcoming deadlines
- Know what's at risk before it's too late

### For Advisors
- Quickly assess client compliance
- Generate reports for workouts
- Identify issues before lenders do

### For AI Agents
- Query loan terms programmatically
- Build automated compliance monitoring
- Integrate with property management systems

## Future Enhancements

- [ ] Database persistence (SQLite/PostgreSQL)
- [ ] Calendar integration for deadline reminders
- [ ] Multi-document analysis (amendments, side letters)
- [ ] Compliance scoring
- [ ] Historical tracking
- [ ] Email alerts for upcoming deadlines
- [ ] Integration with property management software

## License

MIT

---

*Built with the belief that borrowers shouldn't need a law degree to understand their obligations.*
