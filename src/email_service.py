"""
Email service using SendGrid for production notifications.
Handles all outbound email communications.
"""

import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


# SendGrid setup
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "alerts@loanguard.io")
FROM_NAME = os.environ.get("FROM_NAME", "LoanGuard")


@dataclass
class EmailResult:
    """Result of an email send attempt"""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailService:
    """
    Production email service using SendGrid.
    Falls back to console logging in development.
    """
    
    def __init__(self):
        self.sendgrid_available = False
        self.sg_client = None
        
        if SENDGRID_API_KEY:
            try:
                from sendgrid import SendGridAPIClient
                self.sg_client = SendGridAPIClient(SENDGRID_API_KEY)
                self.sendgrid_available = True
            except ImportError:
                print("SendGrid not installed. Run: pip install sendgrid")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> EmailResult:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body
            text_content: Plain text fallback (optional)
            
        Returns:
            EmailResult with success status and message ID
        """
        if not self.sendgrid_available:
            # Development mode - log to console
            print(f"\n{'='*50}")
            print(f"EMAIL (dev mode - not sent)")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"{'='*50}\n")
            return EmailResult(success=True, message_id="dev-mode")
        
        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            message = Mail(
                from_email=Email(FROM_EMAIL, FROM_NAME),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            if text_content:
                message.add_content(Content("text/plain", text_content))
            
            response = self.sg_client.send(message)
            
            # Get message ID from headers
            message_id = response.headers.get("X-Message-Id", "")
            
            return EmailResult(
                success=response.status_code in [200, 201, 202],
                message_id=message_id
            )
            
        except Exception as e:
            return EmailResult(success=False, error=str(e))
    
    def send_overdue_alert(
        self,
        to_email: str,
        property_name: str,
        requirement_title: str,
        days_overdue: int,
        description: str,
        document_reference: str,
        severity: str,
        dashboard_url: str = "#"
    ) -> EmailResult:
        """Send an overdue item alert"""
        
        subject = f"🔴 OVERDUE: {requirement_title} - {property_name}"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <img src="https://loanguard.io/logo-white.png" alt="LoanGuard" style="height: 32px; margin-bottom: 16px;" onerror="this.style.display='none'">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">🔴 Compliance Item Overdue</h1>
        <p style="margin: 0; opacity: 0.8;">{property_name}</p>
    </div>
    
    <div style="background: #fef2f2; border: 1px solid #fecaca; border-top: none; padding: 24px; border-radius: 0 0 16px 16px;">
        <h2 style="margin: 0 0 16px 0; color: #dc2626; font-size: 20px;">{requirement_title}</h2>
        
        <div style="background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
            <p style="margin: 0 0 12px 0;">
                <strong>Status:</strong> 
                <span style="color: #dc2626; font-weight: 600;">{days_overdue} days overdue</span>
            </p>
            <p style="margin: 0 0 12px 0;"><strong>Severity:</strong> {severity.title()}</p>
            <p style="margin: 0 0 12px 0;"><strong>Reference:</strong> {document_reference}</p>
            <p style="margin: 0; color: #64748b;">{description}</p>
        </div>
        
        <a href="{dashboard_url}" style="display: inline-block; background: #dc2626; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
            Take Action →
        </a>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform<br>
        <a href="#" style="color: #94a3b8;">Manage notification preferences</a> • 
        <a href="#" style="color: #94a3b8;">Unsubscribe</a>
    </p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, html)
    
    def send_upcoming_deadline(
        self,
        to_email: str,
        property_name: str,
        requirement_title: str,
        days_until: int,
        due_date: str,
        description: str,
        dashboard_url: str = "#"
    ) -> EmailResult:
        """Send an upcoming deadline reminder"""
        
        urgency = "high" if days_until <= 7 else "medium"
        urgency_color = "#f59e0b" if urgency == "high" else "#3b82f6"
        
        subject = f"📅 Upcoming: {requirement_title} due in {days_until} days"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">📅 Upcoming Deadline</h1>
        <p style="margin: 0; opacity: 0.8;">{property_name}</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; border-top: none; padding: 24px; border-radius: 0 0 16px 16px;">
        <h2 style="margin: 0 0 16px 0; font-size: 20px;">{requirement_title}</h2>
        
        <div style="background: #f8fafc; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 4px solid {urgency_color};">
            <p style="margin: 0 0 8px 0; font-size: 18px;">
                <strong style="color: {urgency_color};">Due in {days_until} days</strong>
            </p>
            <p style="margin: 0 0 8px 0;"><strong>Due Date:</strong> {due_date}</p>
            <p style="margin: 0; color: #64748b;">{description}</p>
        </div>
        
        <a href="{dashboard_url}" style="display: inline-block; background: #0f172a; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600;">
            View Details →
        </a>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform<br>
        <a href="#" style="color: #94a3b8;">Manage notification preferences</a>
    </p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, html)
    
    def send_covenant_alert(
        self,
        to_email: str,
        property_name: str,
        requirement_title: str,
        is_breach: bool,
        metric: str,
        required_value: float,
        current_value: Optional[float],
        unit: str,
        cure_period_days: Optional[int],
        dashboard_url: str = "#"
    ) -> EmailResult:
        """Send a covenant breach or at-risk alert"""
        
        status = "BREACH" if is_breach else "AT RISK"
        emoji = "🔴" if is_breach else "⚠️"
        color = "#dc2626" if is_breach else "#f59e0b"
        bg_color = "#fef2f2" if is_breach else "#fffbeb"
        
        subject = f"{emoji} {status}: {requirement_title} - {property_name}"
        
        current_text = f"{current_value}{unit}" if current_value else "Not reported"
        cure_text = f"<p style='margin: 0;'><strong>Cure Period:</strong> {cure_period_days} days</p>" if cure_period_days else ""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">{emoji} Covenant {status.title()}</h1>
        <p style="margin: 0; opacity: 0.8;">{property_name}</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; border-top: none; padding: 24px; border-radius: 0 0 16px 16px;">
        <h2 style="margin: 0 0 16px 0; color: {color}; font-size: 20px;">{requirement_title}</h2>
        
        <div style="background: {bg_color}; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                <div>
                    <div style="font-size: 12px; color: #666; text-transform: uppercase;">Required</div>
                    <div style="font-size: 24px; font-weight: bold;">{required_value}{unit}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 12px; color: #666; text-transform: uppercase;">Current</div>
                    <div style="font-size: 24px; font-weight: bold; color: {color};">{current_text}</div>
                </div>
            </div>
            {cure_text}
        </div>
        
        <a href="{dashboard_url}" style="display: inline-block; background: {color}; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600;">
            Review & Respond →
        </a>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform
    </p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, html)
    
    def send_weekly_summary(
        self,
        to_email: str,
        user_name: str,
        total_loans: int,
        total_exposure: float,
        compliance_rate: float,
        overdue_count: int,
        at_risk_count: int,
        loans_summary: list,  # List of dicts with property_name and issues
        dashboard_url: str = "#"
    ) -> EmailResult:
        """Send weekly compliance summary"""
        
        subject = f"📊 Weekly Compliance Summary - {total_loans} Loans"
        
        loans_html = ""
        for loan in loans_summary[:10]:
            issue_badge = f"<span style='color: #dc2626; font-weight: 600;'>{loan['issues']} issues</span>" if loan['issues'] > 0 else "<span style='color: #10b981;'>✓ OK</span>"
            loans_html += f"""
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">{loan['property_name']}</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">{issue_badge}</td>
            </tr>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">📊 Weekly Compliance Summary</h1>
        <p style="margin: 0; opacity: 0.8;">{datetime.now().strftime('%B %d, %Y')}</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; border-top: none; padding: 24px; border-radius: 0 0 16px 16px;">
        <p style="margin: 0 0 20px 0;">Hi {user_name},</p>
        <p style="margin: 0 0 24px 0;">Here's your weekly compliance overview:</p>
        
        <!-- Stats Grid -->
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 24px;">
            <div style="background: #f8fafc; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 28px; font-weight: 700; color: #0f172a;">{total_loans}</div>
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Active Loans</div>
            </div>
            <div style="background: #f8fafc; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 28px; font-weight: 700; color: #10b981;">{compliance_rate:.0f}%</div>
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Compliance Rate</div>
            </div>
            <div style="background: #fef2f2; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 28px; font-weight: 700; color: #dc2626;">{overdue_count}</div>
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Overdue</div>
            </div>
            <div style="background: #fffbeb; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 28px; font-weight: 700; color: #f59e0b;">{at_risk_count}</div>
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">At Risk</div>
            </div>
        </div>
        
        <!-- Loans Table -->
        <h3 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600;">Loan Status</h3>
        <table style="width: 100%; border-collapse: collapse;">
            {loans_html}
        </table>
        
        <div style="margin-top: 24px; text-align: center;">
            <a href="{dashboard_url}" style="display: inline-block; background: #0f172a; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                View Full Dashboard →
            </a>
        </div>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform<br>
        <a href="#" style="color: #94a3b8;">Manage notification preferences</a>
    </p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, html)
    
    def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        dashboard_url: str = "#"
    ) -> EmailResult:
        """Send welcome email to new users"""
        
        subject = "Welcome to LoanGuard! 🛡️"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 40px 32px; border-radius: 16px 16px 0 0; text-align: center;">
        <div style="font-size: 48px; margin-bottom: 16px;">🛡️</div>
        <h1 style="margin: 0 0 8px 0; font-size: 28px;">Welcome to LoanGuard</h1>
        <p style="margin: 0; opacity: 0.8;">Your loan compliance co-pilot</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; border-top: none; padding: 32px; border-radius: 0 0 16px 16px;">
        <p style="margin: 0 0 20px 0; font-size: 18px;">Hi {user_name}! 👋</p>
        
        <p style="margin: 0 0 20px 0;">
            You're all set to start managing your loan compliance. Here's what you can do:
        </p>
        
        <div style="margin: 24px 0;">
            <div style="display: flex; align-items: flex-start; margin-bottom: 16px;">
                <span style="font-size: 24px; margin-right: 12px;">📄</span>
                <div>
                    <strong>Upload loan documents</strong><br>
                    <span style="color: #64748b;">We'll extract all compliance requirements automatically</span>
                </div>
            </div>
            <div style="display: flex; align-items: flex-start; margin-bottom: 16px;">
                <span style="font-size: 24px; margin-right: 12px;">📊</span>
                <div>
                    <strong>Track compliance</strong><br>
                    <span style="color: #64748b;">See what's due, what's at risk, and your overall score</span>
                </div>
            </div>
            <div style="display: flex; align-items: flex-start;">
                <span style="font-size: 24px; margin-right: 12px;">🔔</span>
                <div>
                    <strong>Get notified</strong><br>
                    <span style="color: #64748b;">We'll alert you before deadlines and when issues arise</span>
                </div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 32px;">
            <a href="{dashboard_url}" style="display: inline-block; background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                Go to Dashboard →
            </a>
        </div>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        Questions? Reply to this email or reach out at support@loanguard.io
    </p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, html)


# Singleton instance
email_service = EmailService()
