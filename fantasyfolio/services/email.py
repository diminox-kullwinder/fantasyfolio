"""
Email Service for FantasyFolio.

Supports multiple providers: SMTP, SendGrid, AWS SES.
Configuration stored in settings table.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from pathlib import Path

from fantasyfolio.core.database import get_setting

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service with support for multiple providers.
    
    Configuration stored in settings table:
    - email_provider: 'smtp', 'sendgrid', or 'ses'
    - email_smtp_host: SMTP server hostname
    - email_smtp_port: SMTP port (587 for TLS, 465 for SSL)
    - email_smtp_user: SMTP username
    - email_smtp_password: SMTP password (encrypted in DB)
    - email_smtp_use_tls: 'true' or 'false'
    - email_from_address: From email address
    - email_from_name: From name
    - email_sendgrid_api_key: SendGrid API key (if using SendGrid)
    """
    
    def __init__(self):
        self.provider = get_setting('email_provider') or 'smtp'
        self.from_address = get_setting('email_from_address') or 'noreply@fantasyfolio.local'
        self.from_name = get_setting('email_from_name') or 'FantasyFolio'
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        if self.provider == 'smtp':
            host = get_setting('email_smtp_host')
            user = get_setting('email_smtp_user')
            password = get_setting('email_smtp_password')
            return bool(host and user and password)
        
        elif self.provider == 'sendgrid':
            api_key = get_setting('email_sendgrid_api_key')
            return bool(api_key)
        
        elif self.provider == 'ses':
            # AWS SES configuration
            region = get_setting('email_ses_region')
            access_key = get_setting('email_ses_access_key')
            secret_key = get_setting('email_ses_secret_key')
            return bool(region and access_key and secret_key)
        
        return False
    
    def send(
        self,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body (optional, generated from HTML if not provided)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.error("Email service is not configured")
            return False
        
        try:
            if self.provider == 'smtp':
                return self._send_smtp(to_address, subject, html_body, text_body)
            elif self.provider == 'sendgrid':
                return self._send_sendgrid(to_address, subject, html_body, text_body)
            elif self.provider == 'ses':
                return self._send_ses(to_address, subject, html_body, text_body)
            else:
                logger.error(f"Unknown email provider: {self.provider}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_address}: {e}")
            return False
    
    def _send_smtp(
        self,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: Optional[str]
    ) -> bool:
        """Send email via SMTP."""
        host = get_setting('email_smtp_host')
        port = int(get_setting('email_smtp_port') or '587')
        user = get_setting('email_smtp_user')
        password = get_setting('email_smtp_password')
        use_tls = get_setting('email_smtp_use_tls') != 'false'
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{self.from_name} <{self.from_address}>"
        msg['To'] = to_address
        
        # Add text and HTML parts
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send via SMTP
        if use_tls:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password)
                server.send_message(msg)
        
        logger.info(f"Email sent via SMTP to {to_address}")
        return True
    
    def _send_sendgrid(
        self,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: Optional[str]
    ) -> bool:
        """Send email via SendGrid API."""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
        except ImportError:
            logger.error("sendgrid package not installed (pip install sendgrid)")
            return False
        
        api_key = get_setting('email_sendgrid_api_key')
        
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        
        from_email = Email(self.from_address, self.from_name)
        to_email = To(to_address)
        content = Content("text/html", html_body)
        
        mail = Mail(from_email, to_email, subject, content)
        
        if text_body:
            mail.add_content(Content("text/plain", text_body))
        
        response = sg.client.mail.send.post(request_body=mail.get())
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email sent via SendGrid to {to_address}")
            return True
        else:
            logger.error(f"SendGrid error: {response.status_code} - {response.body}")
            return False
    
    def _send_ses(
        self,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: Optional[str]
    ) -> bool:
        """Send email via AWS SES."""
        try:
            import boto3
        except ImportError:
            logger.error("boto3 package not installed (pip install boto3)")
            return False
        
        region = get_setting('email_ses_region')
        access_key = get_setting('email_ses_access_key')
        secret_key = get_setting('email_ses_secret_key')
        
        client = boto3.client(
            'ses',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        destination = {'ToAddresses': [to_address]}
        message = {
            'Subject': {'Data': subject},
            'Body': {
                'Html': {'Data': html_body}
            }
        }
        
        if text_body:
            message['Body']['Text'] = {'Data': text_body}
        
        response = client.send_email(
            Source=f"{self.from_name} <{self.from_address}>",
            Destination=destination,
            Message=message
        )
        
        logger.info(f"Email sent via AWS SES to {to_address}: {response['MessageId']}")
        return True
    
    def send_test_email(self, to_address: str) -> bool:
        """Send a test email to verify configuration."""
        subject = "FantasyFolio Email Test"
        html_body = """
        <html>
        <body>
            <h2>Email Configuration Test</h2>
            <p>This is a test email from your FantasyFolio instance.</p>
            <p>If you received this, your email configuration is working correctly!</p>
            <p style="color: #666; font-size: 0.9em;">
                Provider: {provider}<br>
                From: {from_name} &lt;{from_address}&gt;
            </p>
        </body>
        </html>
        """.format(
            provider=self.provider,
            from_name=self.from_name,
            from_address=self.from_address
        )
        
        text_body = f"""
        Email Configuration Test
        
        This is a test email from your FantasyFolio instance.
        If you received this, your email configuration is working correctly!
        
        Provider: {self.provider}
        From: {self.from_name} <{self.from_address}>
        """
        
        return self.send(to_address, subject, html_body, text_body)


# Global email service instance
_email_service = None

def get_email_service() -> EmailService:
    """Get the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
