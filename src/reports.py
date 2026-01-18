"""
Professional PDF report generator for loan compliance reports.
Generates print-ready reports that advisors can share with clients.
"""

from datetime import datetime
from typing import Optional
import os

from .models import (
    LoanProfile, LoanRequirement, RequirementCategory,
    ComplianceStatus, Severity
)


class PDFReportGenerator:
    """
    Generates professional PDF reports using reportlab.
    Falls back to HTML if reportlab is not available.
    """
    
    def __init__(self):
        self.reportlab_available = False
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate
            self.reportlab_available = True
        except ImportError:
            pass
    
    def generate(self, profile: LoanProfile, output_path: str, 
                 include_original_text: bool = False) -> str:
        """
        Generate a PDF report for the loan profile.
        
        Args:
            profile: The loan profile to report on
            output_path: Where to save the PDF
            include_original_text: Whether to include original document text
            
        Returns:
            Path to the generated report
        """
        if self.reportlab_available:
            return self._generate_pdf(profile, output_path, include_original_text)
        else:
            # Fall back to HTML
            html_path = output_path.replace('.pdf', '.html')
            return self._generate_html_report(profile, html_path, include_original_text)
    
    def _generate_html_report(self, profile: LoanProfile, output_path: str,
                              include_original_text: bool) -> str:
        """Generate a print-ready HTML report"""
        summary = profile.compliance_summary()
        
        # Generate requirements sections
        requirements_html = ""
        for cat in RequirementCategory:
            reqs = profile.get_requirements_by_category(cat)
            if reqs:
                cat_title = cat.value.replace("_", " ").title()
                requirements_html += f"""
                <div class="category-section">
                    <h3>{cat_title}</h3>
                    {"".join(self._render_requirement_html(r, include_original_text) for r in reqs)}
                </div>
                """
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Compliance Report - {profile.property_name}</title>
    <style>
        @page {{
            size: letter;
            margin: 0.75in;
        }}
        
        @media print {{
            .no-print {{ display: none; }}
            .page-break {{ page-break-before: always; }}
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #1a1a1a;
            max-width: 8.5in;
            margin: 0 auto;
            padding: 0.5in;
        }}
        
        h1 {{
            font-size: 24pt;
            font-weight: normal;
            letter-spacing: -0.5px;
            margin-bottom: 0.25in;
            padding-bottom: 0.15in;
            border-bottom: 2px solid #1a1a1a;
        }}
        
        h2 {{
            font-size: 14pt;
            font-weight: bold;
            margin-top: 0.3in;
            margin-bottom: 0.15in;
            color: #333;
        }}
        
        h3 {{
            font-size: 12pt;
            font-weight: bold;
            margin-top: 0.25in;
            margin-bottom: 0.1in;
            color: #1a1a1a;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-family: -apple-system, sans-serif;
        }}
        
        .header-info {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.3in;
        }}
        
        .header-info div {{
            flex: 1;
        }}
        
        .label {{
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #666;
            font-family: -apple-system, sans-serif;
        }}
        
        .value {{
            font-size: 12pt;
            font-weight: 500;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.2in;
            margin: 0.3in 0;
            padding: 0.2in;
            background: #f5f5f5;
            border-radius: 4px;
        }}
        
        .summary-item {{
            text-align: center;
        }}
        
        .summary-value {{
            font-size: 28pt;
            font-weight: bold;
            line-height: 1;
        }}
        
        .summary-label {{
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #666;
            font-family: -apple-system, sans-serif;
        }}
        
        .critical {{ color: #c53030; }}
        .warning {{ color: #c05621; }}
        .success {{ color: #276749; }}
        
        .category-section {{
            margin-top: 0.3in;
        }}
        
        .requirement {{
            padding: 0.15in 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .requirement:last-child {{
            border-bottom: none;
        }}
        
        .req-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}
        
        .req-title {{
            font-weight: bold;
            font-size: 11pt;
        }}
        
        .status-badge {{
            font-size: 8pt;
            padding: 2px 8px;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-family: -apple-system, sans-serif;
            font-weight: 600;
        }}
        
        .status-compliant {{
            background: #c6f6d5;
            color: #276749;
        }}
        
        .status-at_risk {{
            background: #feebc8;
            color: #c05621;
        }}
        
        .status-non_compliant, .status-overdue {{
            background: #fed7d7;
            color: #c53030;
        }}
        
        .status-pending {{
            background: #bee3f8;
            color: #2b6cb0;
        }}
        
        .status-unknown {{
            background: #e2e8f0;
            color: #4a5568;
        }}
        
        .req-details {{
            margin-top: 0.1in;
            font-size: 10pt;
            color: #444;
        }}
        
        .req-meta {{
            display: flex;
            gap: 0.3in;
            margin-top: 0.05in;
            font-size: 9pt;
            color: #666;
        }}
        
        .plain-language {{
            margin-top: 0.1in;
            padding: 0.1in;
            background: #fafafa;
            border-left: 3px solid #ddd;
            font-style: italic;
        }}
        
        .original-text {{
            margin-top: 0.1in;
            padding: 0.1in;
            background: #f5f5f5;
            font-size: 9pt;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
        }}
        
        .footer {{
            margin-top: 0.5in;
            padding-top: 0.15in;
            border-top: 1px solid #ddd;
            font-size: 9pt;
            color: #666;
            text-align: center;
        }}
        
        .threshold-box {{
            display: inline-block;
            margin-top: 0.05in;
            padding: 0.05in 0.1in;
            background: #ebf8ff;
            border-radius: 3px;
            font-size: 10pt;
            font-family: -apple-system, sans-serif;
        }}
    </style>
</head>
<body>
    <h1>Loan Compliance Report</h1>
    
    <div class="header-info">
        <div>
            <div class="label">Property</div>
            <div class="value">{profile.property_name}</div>
        </div>
        <div>
            <div class="label">Borrower</div>
            <div class="value">{profile.borrower_name}</div>
        </div>
        <div>
            <div class="label">Lender</div>
            <div class="value">{profile.lender_name}</div>
        </div>
        <div>
            <div class="label">Loan Amount</div>
            <div class="value">${profile.original_loan_amount:,.0f}</div>
        </div>
    </div>
    
    <div class="header-info">
        <div>
            <div class="label">Loan ID</div>
            <div class="value">{profile.loan_id}</div>
        </div>
        <div>
            <div class="label">Maturity Date</div>
            <div class="value">{profile.maturity_date or 'N/A'}</div>
        </div>
        <div>
            <div class="label">Report Date</div>
            <div class="value">{datetime.now().strftime('%B %d, %Y')}</div>
        </div>
        <div></div>
    </div>
    
    <h2>Compliance Summary</h2>
    
    <div class="summary-grid">
        <div class="summary-item">
            <div class="summary-value">{summary['total_requirements']}</div>
            <div class="summary-label">Total Requirements</div>
        </div>
        <div class="summary-item">
            <div class="summary-value critical">{summary['critical_items']}</div>
            <div class="summary-label">Critical Items</div>
        </div>
        <div class="summary-item">
            <div class="summary-value warning">{summary['non_compliant_count'] + summary['at_risk_count']}</div>
            <div class="summary-label">Needs Attention</div>
        </div>
        <div class="summary-item">
            <div class="summary-value success">{summary['by_status'].get('compliant', 0)}</div>
            <div class="summary-label">Compliant</div>
        </div>
    </div>
    
    <h2>Requirements Detail</h2>
    
    {requirements_html}
    
    <div class="footer">
        <p>Generated by LoanGuard Compliance Platform • {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <p>This report is for informational purposes only. Please consult your loan documents for authoritative terms.</p>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        return output_path
    
    def _render_requirement_html(self, req: LoanRequirement, include_original: bool) -> str:
        """Render a single requirement as HTML"""
        status_class = f"status-{req.status.value}"
        status_label = req.status.value.replace('_', ' ').title()
        
        deadline_html = ""
        if req.deadline:
            deadline_html = f"<span><strong>Deadline:</strong> {req.deadline.description}</span>"
        
        threshold_html = ""
        if req.threshold:
            threshold_html = f"""
            <div class="threshold-box">
                📊 {req.threshold.human_readable()}
            </div>
            """
        
        original_html = ""
        if include_original and req.original_text:
            original_html = f"""
            <div class="original-text">{req.original_text}</div>
            """
        
        severity_label = req.severity.value.title()
        
        return f"""
        <div class="requirement">
            <div class="req-header">
                <div class="req-title">{req.title}</div>
                <span class="status-badge {status_class}">{status_label}</span>
            </div>
            <div class="req-meta">
                <span><strong>Severity:</strong> {severity_label}</span>
                <span><strong>Reference:</strong> {req.document_reference}</span>
                {deadline_html}
            </div>
            {threshold_html}
            <div class="plain-language">
                {req.plain_language_summary}
            </div>
            {original_html}
        </div>
        """
    
    def _generate_pdf(self, profile: LoanProfile, output_path: str,
                      include_original_text: bool) -> str:
        """Generate actual PDF using reportlab"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, HRFlowable
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        styles.add(ParagraphStyle(
            name='MainTitle',
            fontSize=24,
            leading=28,
            spaceAfter=20,
            fontName='Helvetica-Bold'
        ))
        
        styles.add(ParagraphStyle(
            name='SectionTitle',
            fontSize=14,
            leading=18,
            spaceBefore=20,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        ))
        
        styles.add(ParagraphStyle(
            name='CategoryTitle',
            fontSize=11,
            leading=14,
            spaceBefore=15,
            spaceAfter=8,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#333333')
        ))
        
        styles.add(ParagraphStyle(
            name='PlainLanguage',
            fontSize=10,
            leading=14,
            leftIndent=10,
            textColor=colors.HexColor('#444444'),
            fontName='Helvetica-Oblique'
        ))
        
        story = []
        
        # Title
        story.append(Paragraph("Loan Compliance Report", styles['MainTitle']))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.black))
        story.append(Spacer(1, 0.2*inch))
        
        # Header info table
        header_data = [
            ['Property:', profile.property_name, 'Borrower:', profile.borrower_name],
            ['Lender:', profile.lender_name, 'Loan Amount:', f"${profile.original_loan_amount:,.0f}"],
            ['Loan ID:', profile.loan_id, 'Report Date:', datetime.now().strftime('%B %d, %Y')]
        ]
        
        header_table = Table(header_data, colWidths=[1*inch, 2.25*inch, 1*inch, 2.25*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Summary section
        story.append(Paragraph("Compliance Summary", styles['SectionTitle']))
        
        summary = profile.compliance_summary()
        summary_data = [[
            str(summary['total_requirements']),
            str(summary['critical_items']),
            str(summary['non_compliant_count'] + summary['at_risk_count']),
            str(summary['by_status'].get('compliant', 0))
        ], [
            'Total Requirements',
            'Critical Items',
            'Needs Attention',
            'Compliant'
        ]]
        
        summary_table = Table(summary_data, colWidths=[1.625*inch]*4)
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 24),
            ('FONTSIZE', (0, 1), (-1, 1), 9),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#c53030')),
            ('TEXTCOLOR', (2, 0), (2, 0), colors.HexColor('#c05621')),
            ('TEXTCOLOR', (3, 0), (3, 0), colors.HexColor('#276749')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TOPPADDING', (0, 0), (-1, 0), 15),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 15),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Requirements by category
        story.append(Paragraph("Requirements Detail", styles['SectionTitle']))
        
        for cat in RequirementCategory:
            reqs = profile.get_requirements_by_category(cat)
            if reqs:
                cat_title = cat.value.replace("_", " ").title()
                story.append(Paragraph(cat_title, styles['CategoryTitle']))
                
                for req in reqs:
                    # Requirement title and status
                    status_text = req.status.value.replace('_', ' ').title()
                    story.append(Paragraph(
                        f"<b>{req.title}</b> — <i>{status_text}</i>",
                        styles['Normal']
                    ))
                    
                    # Meta info
                    meta_parts = [f"Severity: {req.severity.value.title()}"]
                    if req.document_reference:
                        meta_parts.append(f"Ref: {req.document_reference}")
                    if req.deadline:
                        meta_parts.append(f"Deadline: {req.deadline.description}")
                    
                    story.append(Paragraph(
                        " • ".join(meta_parts),
                        ParagraphStyle('Meta', fontSize=9, textColor=colors.HexColor('#666666'))
                    ))
                    
                    # Plain language summary
                    story.append(Paragraph(req.plain_language_summary, styles['PlainLanguage']))
                    story.append(Spacer(1, 0.15*inch))
        
        # Footer
        story.append(Spacer(1, 0.3*inch))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dddddd')))
        story.append(Paragraph(
            f"Generated by LoanGuard Compliance Platform • {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ParagraphStyle('Footer', fontSize=9, textColor=colors.HexColor('#666666'), alignment=TA_CENTER)
        ))
        
        doc.build(story)
        return output_path


class ExecutiveSummaryGenerator:
    """Generates one-page executive summaries for quick review"""
    
    def generate(self, profiles: list[LoanProfile], output_path: str) -> str:
        """Generate a portfolio-level executive summary"""
        total_loans = len(profiles)
        total_requirements = sum(len(p.requirements) for p in profiles)
        total_loan_amount = sum(p.original_loan_amount for p in profiles)
        
        issues_by_loan = []
        for p in profiles:
            overdue = len([r for r in p.requirements if r.status == ComplianceStatus.NON_COMPLIANT])
            at_risk = len([r for r in p.requirements if r.status == ComplianceStatus.AT_RISK])
            issues_by_loan.append({
                'property': p.property_name,
                'loan_amount': p.original_loan_amount,
                'overdue': overdue,
                'at_risk': at_risk,
                'total_issues': overdue + at_risk
            })
        
        issues_by_loan.sort(key=lambda x: x['total_issues'], reverse=True)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Portfolio Executive Summary</title>
    <style>
        body {{ 
            font-family: -apple-system, sans-serif; 
            max-width: 8.5in; 
            margin: 0 auto; 
            padding: 0.5in;
            font-size: 11pt;
        }}
        h1 {{ font-size: 20pt; margin-bottom: 0.2in; }}
        .stats {{ display: flex; gap: 0.3in; margin: 0.3in 0; }}
        .stat {{ flex: 1; text-align: center; padding: 0.2in; background: #f5f5f5; border-radius: 8px; }}
        .stat-value {{ font-size: 28pt; font-weight: bold; }}
        .stat-label {{ font-size: 9pt; text-transform: uppercase; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 0.2in; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f9f9f9; font-size: 9pt; text-transform: uppercase; }}
        .critical {{ color: #c53030; font-weight: bold; }}
        .warning {{ color: #c05621; }}
    </style>
</head>
<body>
    <h1>Portfolio Compliance Summary</h1>
    <p style="color: #666;">Generated {datetime.now().strftime('%B %d, %Y')}</p>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{total_loans}</div>
            <div class="stat-label">Active Loans</div>
        </div>
        <div class="stat">
            <div class="stat-value">${total_loan_amount/1000000:.1f}M</div>
            <div class="stat-label">Total Exposure</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_requirements}</div>
            <div class="stat-label">Requirements</div>
        </div>
        <div class="stat">
            <div class="stat-value critical">{sum(l['total_issues'] for l in issues_by_loan)}</div>
            <div class="stat-label">Total Issues</div>
        </div>
    </div>
    
    <h2 style="font-size: 14pt; margin-top: 0.3in;">Loans Requiring Attention</h2>
    <table>
        <tr>
            <th>Property</th>
            <th>Loan Amount</th>
            <th>Overdue</th>
            <th>At Risk</th>
        </tr>
        {"".join(f'''
        <tr>
            <td>{l['property']}</td>
            <td>${l['loan_amount']:,.0f}</td>
            <td class="critical">{l['overdue'] if l['overdue'] > 0 else '—'}</td>
            <td class="warning">{l['at_risk'] if l['at_risk'] > 0 else '—'}</td>
        </tr>
        ''' for l in issues_by_loan[:10])}
    </table>
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        return output_path
