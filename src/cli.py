#!/usr/bin/env python3
"""
Command-line interface for the Loan Compliance Agent.

Usage:
    # Analyze a loan document
    python -m src.cli analyze loan_document.pdf --output report.html
    
    # Generate demo data
    python -m src.cli demo --output demo_report.html
    
    # Start the API server
    python -m src.cli serve --port 8000
    
    # Query a specific requirement
    python -m src.cli query DEMO-001 --category financial_reporting
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .models import LoanProfile, RequirementCategory
from .pdf_extractor import LoanDocumentParser
from .extractor import RequirementExtractor, MockExtractor
from .formatters import JSONFormatter, MarkdownFormatter, HTMLFormatter


def cmd_analyze(args):
    """Analyze a loan document and generate compliance report"""
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)
    
    print(f"📄 Analyzing: {args.input}")
    
    # Extract text from PDF
    parser = LoanDocumentParser()
    print("   Extracting text from PDF...")
    document_text = parser.extract_for_analysis(args.input)
    
    # Extract requirements
    print("   Extracting requirements...")
    if args.mock or not os.environ.get("ANTHROPIC_API_KEY"):
        if not args.mock:
            print("   ⚠️  No ANTHROPIC_API_KEY found, using mock extractor")
        extractor = MockExtractor()
    else:
        extractor = RequirementExtractor()
    
    loan_id = args.loan_id or f"LOAN-{Path(args.input).stem}"
    profile = extractor.extract_requirements(document_text, loan_id)
    
    print(f"   ✅ Found {len(profile.requirements)} requirements")
    
    # Generate output
    output_path = args.output or f"{loan_id}_report.html"
    
    if output_path.endswith('.json'):
        formatter = JSONFormatter()
        content = formatter.format(profile)
    elif output_path.endswith('.md'):
        formatter = MarkdownFormatter()
        content = formatter.format(profile)
    else:
        formatter = HTMLFormatter()
        content = formatter.format(profile)
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    print(f"   📝 Report saved to: {output_path}")
    
    # Print summary
    summary = profile.compliance_summary()
    print(f"\n📊 Summary:")
    print(f"   Total Requirements: {summary['total_requirements']}")
    print(f"   Critical Items: {summary['critical_items']}")
    print(f"   By Category:")
    for cat, count in summary['by_category'].items():
        if count > 0:
            print(f"      - {cat.replace('_', ' ').title()}: {count}")


def cmd_demo(args):
    """Generate a demo report with sample data"""
    print("🎭 Generating demo loan profile...")
    
    extractor = MockExtractor()
    profile = extractor.extract_requirements("", "DEMO-001")
    
    output_path = args.output or "demo_report.html"
    
    if output_path.endswith('.json'):
        formatter = JSONFormatter()
        content = formatter.format(profile)
    elif output_path.endswith('.md'):
        formatter = MarkdownFormatter()
        content = formatter.format(profile)
    else:
        formatter = HTMLFormatter()
        content = formatter.format(profile)
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Demo report saved to: {output_path}")
    print(f"   Property: {profile.property_name}")
    print(f"   Requirements: {len(profile.requirements)}")


def cmd_serve(args):
    """Start the API server"""
    print(f"🚀 Starting Loan Compliance Agent API on port {args.port}...")
    print(f"   Documentation: http://localhost:{args.port}/docs")
    print(f"   OpenAPI spec: http://localhost:{args.port}/openapi.json")
    
    from .api import start_server
    start_server(host=args.host, port=args.port)


def cmd_query(args):
    """Query requirements from a saved loan profile"""
    # For CLI queries, we'd need to load from a saved file
    # This is a simplified version - in production you'd use a database
    
    print("📋 Query functionality requires the API server to be running.")
    print("   Start the server with: python -m src.cli serve")
    print(f"   Then query: curl http://localhost:8000/loans/{args.loan_id}/requirements")
    
    if args.category:
        print(f"   With category filter: ?category={args.category}")


def cmd_checklist(args):
    """Generate a simple checklist from a loan document"""
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)
    
    print(f"📄 Generating checklist from: {args.input}")
    
    # Extract and analyze
    parser = LoanDocumentParser()
    document_text = parser.extract_for_analysis(args.input)
    
    if args.mock or not os.environ.get("ANTHROPIC_API_KEY"):
        extractor = MockExtractor()
    else:
        extractor = RequirementExtractor()
    
    loan_id = f"LOAN-{Path(args.input).stem}"
    profile = extractor.extract_requirements(document_text, loan_id)
    
    # Generate checklist
    formatter = MarkdownFormatter()
    checklist = formatter.format_checklist(profile)
    
    output_path = args.output or f"{loan_id}_checklist.md"
    with open(output_path, 'w') as f:
        f.write(checklist)
    
    print(f"✅ Checklist saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Loan Compliance Agent - Extract and manage loan document requirements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a loan document
  python -m src.cli analyze loan.pdf -o report.html
  
  # Generate demo data for testing
  python -m src.cli demo -o demo.html
  
  # Start the API server
  python -m src.cli serve --port 8000
  
  # Generate a simple checklist
  python -m src.cli checklist loan.pdf -o checklist.md

Environment Variables:
  ANTHROPIC_API_KEY  - Required for real document analysis
                       (uses mock data if not set)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a loan document")
    analyze_parser.add_argument("input", help="Path to PDF loan document")
    analyze_parser.add_argument("-o", "--output", help="Output file path (.html, .md, or .json)")
    analyze_parser.add_argument("--loan-id", help="Custom loan ID")
    analyze_parser.add_argument("--mock", action="store_true", help="Use mock extractor (no API)")
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Generate demo report")
    demo_parser.add_argument("-o", "--output", help="Output file path", default="demo_report.html")
    demo_parser.set_defaults(func=cmd_demo)
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    serve_parser.set_defaults(func=cmd_serve)
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query loan requirements")
    query_parser.add_argument("loan_id", help="Loan ID to query")
    query_parser.add_argument("--category", help="Filter by category")
    query_parser.set_defaults(func=cmd_query)
    
    # Checklist command
    checklist_parser = subparsers.add_parser("checklist", help="Generate compliance checklist")
    checklist_parser.add_argument("input", help="Path to PDF loan document")
    checklist_parser.add_argument("-o", "--output", help="Output file path")
    checklist_parser.add_argument("--mock", action="store_true", help="Use mock extractor")
    checklist_parser.set_defaults(func=cmd_checklist)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
