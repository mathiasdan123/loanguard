"""
Output formatters for loan compliance data.
Generates both human-readable and machine-parseable outputs.
"""

import json
from datetime import datetime
from typing import Optional

from .models import (
    LoanProfile, LoanRequirement, RequirementCategory, 
    ComplianceStatus, Severity, Frequency
)


class JSONFormatter:
    """
    Formats loan profiles as structured JSON for agent consumption.
    Designed to be easily queryable by AI agents.
    """
    
    def format(self, profile: LoanProfile, indent: int = 2) -> str:
        """Generate full JSON output"""
        return profile.to_json(indent=indent)
    
    def format_summary(self, profile: LoanProfile) -> str:
        """Generate a summary JSON for quick agent queries"""
        summary = {
            "loan_id": profile.loan_id,
            "property_name": profile.property_name,
            "borrower_name": profile.borrower_name,
            "lender_name": profile.lender_name,
            "compliance_summary": profile.compliance_summary(),
            "critical_requirements": [
                {
                    "id": r.id,
                    "title": r.title,
                    "status": r.status.value,
                    "deadline": r.deadline.description if r.deadline else None
                }
                for r in profile.requirements if r.severity == Severity.CRITICAL
            ],
            "upcoming_deadlines": self._get_deadline_summary(profile)
        }
        return json.dumps(summary, indent=2)
    
    def format_requirements_by_category(self, profile: LoanProfile) -> str:
        """Generate JSON organized by category"""
        by_category = {}
        for cat in RequirementCategory:
            reqs = profile.get_requirements_by_category(cat)
            if reqs:
                by_category[cat.value] = [
                    {
                        "id": r.id,
                        "title": r.title,
                        "plain_language_summary": r.plain_language_summary,
                        "deadline": r.deadline.to_dict() if r.deadline else None,
                        "threshold": r.threshold.to_dict() if r.threshold else None,
                        "status": r.status.value
                    }
                    for r in reqs
                ]
        return json.dumps(by_category, indent=2)
    
    def _get_deadline_summary(self, profile: LoanProfile) -> list:
        """Get list of requirements with deadlines"""
        deadlines = []
        for r in profile.requirements:
            if r.deadline:
                deadlines.append({
                    "requirement_id": r.id,
                    "title": r.title,
                    "frequency": r.deadline.frequency.value,
                    "description": r.deadline.description
                })
        return deadlines


class MarkdownFormatter:
    """
    Formats loan profiles as readable Markdown documents.
    Designed for human review and documentation.
    """
    
    def format(self, profile: LoanProfile) -> str:
        """Generate full Markdown report"""
        lines = [
            f"# Loan Compliance Checklist",
            f"",
            f"**Loan ID:** {profile.loan_id}",
            f"**Property:** {profile.property_name}",
            f"**Borrower:** {profile.borrower_name}",
            f"**Lender:** {profile.lender_name}",
            f"**Original Loan Amount:** ${profile.original_loan_amount:,.2f}",
            f"",
            f"**Origination Date:** {profile.origination_date or 'N/A'}",
            f"**Maturity Date:** {profile.maturity_date or 'N/A'}",
            f"",
            f"**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"---",
            f"",
            f"## Compliance Summary",
            f"",
        ]
        
        summary = profile.compliance_summary()
        lines.extend([
            f"- **Total Requirements:** {summary['total_requirements']}",
            f"- **Critical Items:** {summary['critical_items']}",
            f"- **Non-Compliant:** {summary['non_compliant_count']}",
            f"- **At Risk:** {summary['at_risk_count']}",
            f"",
            f"---",
            f""
        ])
        
        # Group by category
        for cat in RequirementCategory:
            reqs = profile.get_requirements_by_category(cat)
            if reqs:
                cat_title = cat.value.replace("_", " ").title()
                lines.append(f"## {cat_title}")
                lines.append("")
                
                for req in reqs:
                    lines.extend(self._format_requirement(req))
                    lines.append("")
        
        return "\n".join(lines)
    
    def _format_requirement(self, req: LoanRequirement) -> list:
        """Format a single requirement"""
        severity_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢"
        }
        
        status_emoji = {
            ComplianceStatus.COMPLIANT: "✅",
            ComplianceStatus.NON_COMPLIANT: "❌",
            ComplianceStatus.AT_RISK: "⚠️",
            ComplianceStatus.PENDING: "⏳",
            ComplianceStatus.UNKNOWN: "❓",
            ComplianceStatus.NOT_YET_DUE: "📅"
        }
        
        lines = [
            f"### {severity_emoji.get(req.severity, '')} {req.title}",
            f"",
            f"**Status:** {status_emoji.get(req.status, '')} {req.status.value.replace('_', ' ').title()}",
            f"**Severity:** {req.severity.value.title()}",
            f"**Reference:** {req.document_reference}",
            f""
        ]
        
        if req.deadline:
            lines.append(f"**Deadline:** {req.deadline.description} ({req.deadline.frequency.value.replace('_', ' ')})")
            lines.append("")
        
        if req.threshold:
            lines.append(f"**Threshold:** {req.threshold.human_readable()}")
            lines.append("")
        
        if req.cure_period_days:
            lines.append(f"**Cure Period:** {req.cure_period_days} days")
            lines.append("")
        
        lines.extend([
            f"**What You Need to Do:**",
            f"> {req.plain_language_summary}",
            f"",
            f"<details>",
            f"<summary>Original Document Text</summary>",
            f"",
            f"```",
            f"{req.original_text}",
            f"```",
            f"</details>",
            f""
        ])
        
        return lines
    
    def format_checklist(self, profile: LoanProfile) -> str:
        """Generate a simple checklist format"""
        lines = [
            f"# {profile.property_name} - Compliance Checklist",
            f"",
            f"Borrower: {profile.borrower_name}",
            f"",
        ]
        
        for cat in RequirementCategory:
            reqs = profile.get_requirements_by_category(cat)
            if reqs:
                cat_title = cat.value.replace("_", " ").title()
                lines.append(f"## {cat_title}")
                lines.append("")
                
                for req in reqs:
                    checkbox = "[ ]" if req.status != ComplianceStatus.COMPLIANT else "[x]"
                    lines.append(f"- {checkbox} **{req.title}**")
                    lines.append(f"  - {req.plain_language_summary}")
                    if req.deadline:
                        lines.append(f"  - ⏰ {req.deadline.description}")
                    lines.append("")
        
        return "\n".join(lines)


class HTMLFormatter:
    """
    Formats loan profiles as styled HTML documents.
    For web display or PDF generation.
    """
    
    def format(self, profile: LoanProfile) -> str:
        """Generate full HTML report"""
        summary = profile.compliance_summary()
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Loan Compliance Report - {profile.property_name}</title>
    <style>
        :root {{
            --critical: #dc2626;
            --high: #ea580c;
            --medium: #ca8a04;
            --low: #16a34a;
            --compliant: #16a34a;
            --non-compliant: #dc2626;
            --at-risk: #ea580c;
            --pending: #6b7280;
            --unknown: #9ca3af;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            background: #f9fafb;
        }}
        
        h1 {{
            font-size: 2rem;
            margin-bottom: 1rem;
            color: #111827;
        }}
        
        h2 {{
            font-size: 1.5rem;
            margin: 2rem 0 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        .header {{
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }}
        
        .loan-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        
        .loan-info dt {{
            font-size: 0.875rem;
            color: #6b7280;
        }}
        
        .loan-info dd {{
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        
        .card {{
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .card-value {{
            font-size: 2rem;
            font-weight: 700;
        }}
        
        .card-label {{
            font-size: 0.875rem;
            color: #6b7280;
        }}
        
        .card.critical .card-value {{ color: var(--critical); }}
        .card.at-risk .card-value {{ color: var(--at-risk); }}
        
        .requirement {{
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid #e5e7eb;
        }}
        
        .requirement.critical {{ border-left-color: var(--critical); }}
        .requirement.high {{ border-left-color: var(--high); }}
        .requirement.medium {{ border-left-color: var(--medium); }}
        .requirement.low {{ border-left-color: var(--low); }}
        
        .requirement-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }}
        
        .requirement-title {{
            font-size: 1.125rem;
            font-weight: 600;
        }}
        
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .badge.critical {{ background: #fef2f2; color: var(--critical); }}
        .badge.high {{ background: #fff7ed; color: var(--high); }}
        .badge.medium {{ background: #fefce8; color: var(--medium); }}
        .badge.low {{ background: #f0fdf4; color: var(--low); }}
        
        .plain-language {{
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 6px;
            margin: 1rem 0;
            font-size: 0.95rem;
        }}
        
        .meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            font-size: 0.875rem;
            color: #6b7280;
        }}
        
        .meta-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .threshold {{
            background: #eff6ff;
            padding: 0.75rem 1rem;
            border-radius: 6px;
            margin-top: 1rem;
            font-weight: 500;
            color: #1e40af;
        }}
        
        .original-text {{
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #e5e7eb;
        }}
        
        .original-text summary {{
            cursor: pointer;
            font-size: 0.875rem;
            color: #6b7280;
        }}
        
        .original-text pre {{
            margin-top: 0.5rem;
            padding: 1rem;
            background: #f9fafb;
            border-radius: 6px;
            font-size: 0.8rem;
            white-space: pre-wrap;
            overflow-x: auto;
        }}
        
        @media print {{
            body {{ background: white; padding: 1rem; }}
            .card, .requirement {{ box-shadow: none; border: 1px solid #e5e7eb; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Loan Compliance Report</h1>
        <dl class="loan-info">
            <div>
                <dt>Property</dt>
                <dd>{profile.property_name}</dd>
            </div>
            <div>
                <dt>Borrower</dt>
                <dd>{profile.borrower_name}</dd>
            </div>
            <div>
                <dt>Lender</dt>
                <dd>{profile.lender_name}</dd>
            </div>
            <div>
                <dt>Loan Amount</dt>
                <dd>${profile.original_loan_amount:,.2f}</dd>
            </div>
            <div>
                <dt>Maturity Date</dt>
                <dd>{profile.maturity_date or 'N/A'}</dd>
            </div>
            <div>
                <dt>Report Date</dt>
                <dd>{datetime.now().strftime('%B %d, %Y')}</dd>
            </div>
        </dl>
    </div>
    
    <div class="summary-cards">
        <div class="card">
            <div class="card-value">{summary['total_requirements']}</div>
            <div class="card-label">Total Requirements</div>
        </div>
        <div class="card critical">
            <div class="card-value">{summary['critical_items']}</div>
            <div class="card-label">Critical Items</div>
        </div>
        <div class="card at-risk">
            <div class="card-value">{summary['non_compliant_count']}</div>
            <div class="card-label">Non-Compliant</div>
        </div>
        <div class="card">
            <div class="card-value">{summary['at_risk_count']}</div>
            <div class="card-label">At Risk</div>
        </div>
    </div>
"""
        
        # Add requirements by category
        for cat in RequirementCategory:
            reqs = profile.get_requirements_by_category(cat)
            if reqs:
                cat_title = cat.value.replace("_", " ").title()
                html += f'\n    <h2>{cat_title}</h2>\n'
                
                for req in reqs:
                    html += self._format_requirement_html(req)
        
        html += """
</body>
</html>"""
        
        return html
    
    def _format_requirement_html(self, req: LoanRequirement) -> str:
        """Format a single requirement as HTML"""
        deadline_html = ""
        if req.deadline:
            deadline_html = f"""
            <div class="meta-item">
                <span>⏰</span>
                <span>{req.deadline.description} ({req.deadline.frequency.value.replace('_', ' ')})</span>
            </div>"""
        
        threshold_html = ""
        if req.threshold:
            threshold_html = f"""
        <div class="threshold">
            📊 {req.threshold.human_readable()}
        </div>"""
        
        cure_html = ""
        if req.cure_period_days:
            cure_html = f"""
            <div class="meta-item">
                <span>🔧</span>
                <span>Cure Period: {req.cure_period_days} days</span>
            </div>"""
        
        return f"""
    <div class="requirement {req.severity.value}">
        <div class="requirement-header">
            <div class="requirement-title">{req.title}</div>
            <span class="badge {req.severity.value}">{req.severity.value}</span>
        </div>
        
        <div class="plain-language">
            💡 {req.plain_language_summary}
        </div>
        
        <div class="meta">{deadline_html}{cure_html}
            <div class="meta-item">
                <span>📄</span>
                <span>{req.document_reference}</span>
            </div>
        </div>
        {threshold_html}
        
        <details class="original-text">
            <summary>View original document text</summary>
            <pre>{req.original_text}</pre>
        </details>
    </div>
"""
