"""
Notification service for loan compliance alerts.
Handles email notifications for deadlines, compliance issues, and status updates.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from .models import LoanProfile, LoanRequirement, ComplianceStatus, Severity


class NotificationType(str, Enum):
    DEADLINE_UPCOMING = "deadline_upcoming"
    DEADLINE_OVERDUE = "deadline_overdue"
    COVENANT_AT_RISK = "covenant_at_risk"
    COVENANT_BREACH = "covenant_breach"
    STATUS_CHANGE = "status_change"
    WEEKLY_SUMMARY = "weekly_summary"


@dataclass
class Notification:
    """Represents a notification to be sent"""
    type: NotificationType
    recipient_email: str
    subject: str
    loan_id: str
    requirement_id: Optional[str]
    priority: str  # high, medium, low
    data: dict
    
    
class NotificationService:
    """
    Service for generating and managing notifications.
    In production, this would integrate with email providers like SendGrid, SES, etc.
    """
    
    def __init__(self, sender_email: str = "alerts@loanguard.io"):
        self.sender_email = sender_email
        self.pending_notifications: list[Notification] = []
    
    def check_loan_for_alerts(self, profile: LoanProfile, recipient_email: str) -> list[Notification]:
        """Check a loan profile and generate any needed notifications"""
        notifications = []
        today = datetime.now().date()
        
        for req in profile.requirements:
            # Check for overdue items
            if req.status == ComplianceStatus.NON_COMPLIANT or req.deadline:
                if hasattr(req.deadline, 'specific_date') and req.deadline.specific_date:
                    try:
                        due_date = datetime.strptime(req.deadline.specific_date, "%Y-%m-%d").date()
                        days_until = (due_date - today).days
                        
                        if days_until < 0:
                            notifications.append(self._create_overdue_notification(
                                profile, req, recipient_email, abs(days_until)
                            ))
                        elif days_until <= 7:
                            notifications.append(self._create_upcoming_notification(
                                profile, req, recipient_email, days_until
                            ))
                        elif days_until <= 30 and req.severity == Severity.CRITICAL:
                            notifications.append(self._create_upcoming_notification(
                                profile, req, recipient_email, days_until
                            ))
                    except (ValueError, AttributeError):
                        pass
            
            # Check for covenant breaches
            if req.threshold and req.status in [ComplianceStatus.AT_RISK, ComplianceStatus.NON_COMPLIANT]:
                notifications.append(self._create_covenant_alert(
                    profile, req, recipient_email
                ))
        
        return notifications
    
    def _create_overdue_notification(self, profile: LoanProfile, req: LoanRequirement, 
                                      email: str, days_overdue: int) -> Notification:
        return Notification(
            type=NotificationType.DEADLINE_OVERDUE,
            recipient_email=email,
            subject=f"🔴 OVERDUE: {req.title} - {profile.property_name}",
            loan_id=profile.loan_id,
            requirement_id=req.id,
            priority="high",
            data={
                "property_name": profile.property_name,
                "requirement_title": req.title,
                "days_overdue": days_overdue,
                "description": req.plain_language_summary,
                "document_reference": req.document_reference,
                "severity": req.severity.value
            }
        )
    
    def _create_upcoming_notification(self, profile: LoanProfile, req: LoanRequirement,
                                       email: str, days_until: int) -> Notification:
        return Notification(
            type=NotificationType.DEADLINE_UPCOMING,
            recipient_email=email,
            subject=f"📅 Upcoming: {req.title} due in {days_until} days",
            loan_id=profile.loan_id,
            requirement_id=req.id,
            priority="medium" if days_until > 7 else "high",
            data={
                "property_name": profile.property_name,
                "requirement_title": req.title,
                "days_until": days_until,
                "description": req.plain_language_summary,
                "document_reference": req.document_reference
            }
        )
    
    def _create_covenant_alert(self, profile: LoanProfile, req: LoanRequirement,
                               email: str) -> Notification:
        is_breach = req.status == ComplianceStatus.NON_COMPLIANT
        return Notification(
            type=NotificationType.COVENANT_BREACH if is_breach else NotificationType.COVENANT_AT_RISK,
            recipient_email=email,
            subject=f"{'🔴 BREACH' if is_breach else '⚠️ AT RISK'}: {req.title} - {profile.property_name}",
            loan_id=profile.loan_id,
            requirement_id=req.id,
            priority="high",
            data={
                "property_name": profile.property_name,
                "requirement_title": req.title,
                "threshold": req.threshold.to_dict() if req.threshold else None,
                "description": req.plain_language_summary,
                "cure_period_days": req.cure_period_days
            }
        )
    
    def generate_weekly_summary(self, profiles: list[LoanProfile], email: str) -> Notification:
        """Generate a weekly summary email for all loans"""
        total_requirements = sum(len(p.requirements) for p in profiles)
        overdue = sum(len([r for r in p.requirements if r.status == ComplianceStatus.NON_COMPLIANT]) for p in profiles)
        at_risk = sum(len([r for r in p.requirements if r.status == ComplianceStatus.AT_RISK]) for p in profiles)
        compliant = sum(len([r for r in p.requirements if r.status == ComplianceStatus.COMPLIANT]) for p in profiles)
        
        return Notification(
            type=NotificationType.WEEKLY_SUMMARY,
            recipient_email=email,
            subject=f"📊 Weekly Compliance Summary - {len(profiles)} Loans",
            loan_id="ALL",
            requirement_id=None,
            priority="low",
            data={
                "total_loans": len(profiles),
                "total_requirements": total_requirements,
                "overdue_count": overdue,
                "at_risk_count": at_risk,
                "compliant_count": compliant,
                "compliance_rate": round(compliant / total_requirements * 100, 1) if total_requirements > 0 else 0,
                "loans_summary": [
                    {
                        "property_name": p.property_name,
                        "issues": len([r for r in p.requirements if r.status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.AT_RISK]])
                    }
                    for p in profiles
                ]
            }
        )
    
    def render_email_html(self, notification: Notification) -> str:
        """Render notification as HTML email"""
        if notification.type == NotificationType.DEADLINE_OVERDUE:
            return self._render_overdue_email(notification)
        elif notification.type == NotificationType.DEADLINE_UPCOMING:
            return self._render_upcoming_email(notification)
        elif notification.type in [NotificationType.COVENANT_BREACH, NotificationType.COVENANT_AT_RISK]:
            return self._render_covenant_email(notification)
        elif notification.type == NotificationType.WEEKLY_SUMMARY:
            return self._render_summary_email(notification)
        else:
            return self._render_generic_email(notification)
    
    def _render_overdue_email(self, notification: Notification) -> str:
        data = notification.data
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">🔴 Compliance Item Overdue</h1>
        <p style="margin: 0; opacity: 0.8;">{data['property_name']}</p>
    </div>
    
    <div style="background: #fef2f2; border: 1px solid #fecaca; padding: 24px; border-radius: 0 0 16px 16px;">
        <h2 style="margin: 0 0 16px 0; color: #dc2626; font-size: 20px;">{data['requirement_title']}</h2>
        
        <div style="background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
            <p style="margin: 0 0 12px 0;"><strong>Status:</strong> <span style="color: #dc2626; font-weight: 600;">{data['days_overdue']} days overdue</span></p>
            <p style="margin: 0 0 12px 0;"><strong>Severity:</strong> {data['severity'].title()}</p>
            <p style="margin: 0 0 12px 0;"><strong>Reference:</strong> {data['document_reference']}</p>
            <p style="margin: 0; color: #64748b;">{data['description']}</p>
        </div>
        
        <a href="#" style="display: inline-block; background: #dc2626; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
            Take Action →
        </a>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform • <a href="#" style="color: #94a3b8;">Manage notification preferences</a>
    </p>
</body>
</html>
"""

    def _render_upcoming_email(self, notification: Notification) -> str:
        data = notification.data
        urgency_color = "#f59e0b" if data['days_until'] <= 7 else "#3b82f6"
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">📅 Upcoming Deadline</h1>
        <p style="margin: 0; opacity: 0.8;">{data['property_name']}</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; padding: 24px; border-radius: 0 0 16px 16px;">
        <h2 style="margin: 0 0 16px 0; font-size: 20px;">{data['requirement_title']}</h2>
        
        <div style="background: #f8fafc; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 4px solid {urgency_color};">
            <p style="margin: 0 0 12px 0; font-size: 18px;"><strong style="color: {urgency_color};">Due in {data['days_until']} days</strong></p>
            <p style="margin: 0 0 12px 0;"><strong>Reference:</strong> {data['document_reference']}</p>
            <p style="margin: 0; color: #64748b;">{data['description']}</p>
        </div>
        
        <a href="#" style="display: inline-block; background: #0f172a; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
            View Details →
        </a>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform • <a href="#" style="color: #94a3b8;">Manage notification preferences</a>
    </p>
</body>
</html>
"""

    def _render_covenant_email(self, notification: Notification) -> str:
        data = notification.data
        is_breach = notification.type == NotificationType.COVENANT_BREACH
        header_color = "#dc2626" if is_breach else "#f59e0b"
        header_bg = "#fef2f2" if is_breach else "#fffbeb"
        
        threshold_html = ""
        if data.get('threshold'):
            th = data['threshold']
            threshold_html = f"""
            <div style="background: {header_bg}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <p style="margin: 0;"><strong>{th['metric']}:</strong> Required {th['operator']} {th['value']}{th.get('unit', '')}</p>
            </div>
            """
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">{'🔴 Covenant Breach' if is_breach else '⚠️ Covenant At Risk'}</h1>
        <p style="margin: 0; opacity: 0.8;">{data['property_name']}</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; padding: 24px; border-radius: 0 0 16px 16px;">
        <h2 style="margin: 0 0 16px 0; color: {header_color}; font-size: 20px;">{data['requirement_title']}</h2>
        
        {threshold_html}
        
        <div style="background: #f8fafc; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
            <p style="margin: 0 0 12px 0;">{data['description']}</p>
            {f"<p style='margin: 0;'><strong>Cure Period:</strong> {data['cure_period_days']} days</p>" if data.get('cure_period_days') else ""}
        </div>
        
        <a href="#" style="display: inline-block; background: {header_color}; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
            Review & Respond →
        </a>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform • <a href="#" style="color: #94a3b8;">Manage notification preferences</a>
    </p>
</body>
</html>
"""

    def _render_summary_email(self, notification: Notification) -> str:
        data = notification.data
        
        loans_html = ""
        for loan in data.get('loans_summary', []):
            issue_badge = f"<span style='color: #dc2626;'>{loan['issues']} issues</span>" if loan['issues'] > 0 else "<span style='color: #10b981;'>✓ OK</span>"
            loans_html += f"<tr><td style='padding: 12px; border-bottom: 1px solid #e2e8f0;'>{loan['property_name']}</td><td style='padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right;'>{issue_badge}</td></tr>"
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 32px; border-radius: 16px 16px 0 0;">
        <h1 style="margin: 0 0 8px 0; font-size: 24px;">📊 Weekly Compliance Summary</h1>
        <p style="margin: 0; opacity: 0.8;">{datetime.now().strftime('%B %d, %Y')}</p>
    </div>
    
    <div style="background: white; border: 1px solid #e2e8f0; padding: 24px; border-radius: 0 0 16px 16px;">
        <!-- Stats Grid -->
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px;">
            <div style="background: #f8fafc; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 32px; font-weight: 700; color: #0f172a;">{data['total_loans']}</div>
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">Active Loans</div>
            </div>
            <div style="background: #f8fafc; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 32px; font-weight: 700; color: #10b981;">{data['compliance_rate']}%</div>
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">Compliance Rate</div>
            </div>
            <div style="background: #fef2f2; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 32px; font-weight: 700; color: #dc2626;">{data['overdue_count']}</div>
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">Overdue</div>
            </div>
            <div style="background: #fffbeb; padding: 16px; border-radius: 12px; text-align: center;">
                <div style="font-size: 32px; font-weight: 700; color: #f59e0b;">{data['at_risk_count']}</div>
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">At Risk</div>
            </div>
        </div>
        
        <!-- Loans Table -->
        <h3 style="margin: 0 0 16px 0; font-size: 16px;">Loan Status</h3>
        <table style="width: 100%; border-collapse: collapse;">
            {loans_html}
        </table>
        
        <div style="margin-top: 24px; text-align: center;">
            <a href="#" style="display: inline-block; background: #0f172a; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                View Full Dashboard →
            </a>
        </div>
    </div>
    
    <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
        LoanGuard Compliance Platform • <a href="#" style="color: #94a3b8;">Manage notification preferences</a>
    </p>
</body>
</html>
"""

    def _render_generic_email(self, notification: Notification) -> str:
        return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>{notification.subject}</h1>
    <p>Loan: {notification.loan_id}</p>
    <pre>{notification.data}</pre>
</body>
</html>
"""
