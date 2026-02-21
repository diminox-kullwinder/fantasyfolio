"""
Email templates for FantasyFolio.

Provides functions to generate HTML and plain text emails for various purposes.
"""

from typing import Tuple


def verification_email(username: str, verification_url: str) -> Tuple[str, str]:
    """
    Generate verification email content.
    
    Args:
        username: User's username
        verification_url: Full URL with verification token
    
    Returns:
        Tuple of (html_body, text_body)
    """
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }}
            .content {{
                background: #f9fafb;
                padding: 30px;
                border-radius: 0 0 8px 8px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: #3b82f6;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #6b7280;
                font-size: 0.875rem;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Welcome to FantasyFolio!</h1>
        </div>
        <div class="content">
            <p>Hi {username},</p>
            <p>Thank you for signing up! Please verify your email address to complete your registration.</p>
            <p style="text-align: center;">
                <a href="{verification_url}" class="button">Verify Email Address</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="background: #e5e7eb; padding: 12px; border-radius: 4px; word-break: break-all; font-family: monospace; font-size: 0.875rem;">
                {verification_url}
            </p>
            <p style="color: #6b7280; font-size: 0.875rem; margin-top: 30px;">
                This verification link will expire in 24 hours.<br>
                If you didn't create an account, you can safely ignore this email.
            </p>
        </div>
        <div class="footer">
            <p>This email was sent by FantasyFolio</p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    Welcome to FantasyFolio!
    
    Hi {username},
    
    Thank you for signing up! Please verify your email address to complete your registration.
    
    Click the link below or copy it into your browser:
    {verification_url}
    
    This verification link will expire in 24 hours.
    If you didn't create an account, you can safely ignore this email.
    
    ---
    This email was sent by FantasyFolio
    """
    
    return (html_body, text_body)


def password_reset_email(username: str, reset_url: str) -> Tuple[str, str]:
    """
    Generate password reset email content.
    
    Args:
        username: User's username
        reset_url: Full URL with reset token
    
    Returns:
        Tuple of (html_body, text_body)
    """
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }}
            .content {{
                background: #f9fafb;
                padding: 30px;
                border-radius: 0 0 8px 8px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: #3b82f6;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                margin: 20px 0;
            }}
            .warning {{
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 12px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #6b7280;
                font-size: 0.875rem;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Password Reset Request</h1>
        </div>
        <div class="content">
            <p>Hi {username},</p>
            <p>We received a request to reset your password. Click the button below to create a new password:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="button">Reset Password</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="background: #e5e7eb; padding: 12px; border-radius: 4px; word-break: break-all; font-family: monospace; font-size: 0.875rem;">
                {reset_url}
            </p>
            <div class="warning">
                <strong>⚠️  Security Notice:</strong><br>
                This reset link will expire in 1 hour.<br>
                If you didn't request this reset, please ignore this email and your password will remain unchanged.
            </div>
        </div>
        <div class="footer">
            <p>This email was sent by FantasyFolio</p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    Password Reset Request
    
    Hi {username},
    
    We received a request to reset your password. Click the link below or copy it into your browser:
    {reset_url}
    
    ⚠️  Security Notice:
    This reset link will expire in 1 hour.
    If you didn't request this reset, please ignore this email and your password will remain unchanged.
    
    ---
    This email was sent by FantasyFolio
    """
    
    return (html_body, text_body)


def collection_share_invite_email(
    inviter_name: str,
    collection_name: str,
    collection_url: str,
    permissions: str = "view",
    expiry_date: str = None
) -> Tuple[str, str]:
    """
    Generate collection share invite email.
    
    Args:
        inviter_name: Name of user sharing the collection
        collection_name: Name of the collection
        collection_url: Full URL to access collection
        permissions: Access level (view, download, comment)
        expiry_date: Optional expiry date string
    
    Returns:
        Tuple of (html_body, text_body)
    """
    expiry_info = f"<p style='color: #6b7280; font-size: 0.875rem;'>This link will expire on {expiry_date}.</p>" if expiry_date else ""
    expiry_text = f"This link will expire on {expiry_date}." if expiry_date else ""
    
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }}
            .content {{
                background: #f9fafb;
                padding: 30px;
                border-radius: 0 0 8px 8px;
            }}
            .collection-info {{
                background: white;
                border: 2px solid #e5e7eb;
                border-radius: 6px;
                padding: 16px;
                margin: 20px 0;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: #3b82f6;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #6b7280;
                font-size: 0.875rem;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📁 Collection Shared With You</h1>
        </div>
        <div class="content">
            <p><strong>{inviter_name}</strong> has shared a collection with you on FantasyFolio!</p>
            <div class="collection-info">
                <p style="margin: 0; font-weight: 600; color: #111;">"{collection_name}"</p>
                <p style="margin: 8px 0 0 0; color: #6b7280; font-size: 0.875rem;">
                    Access level: {permissions.capitalize()}
                </p>
            </div>
            <p style="text-align: center;">
                <a href="{collection_url}" class="button">View Collection</a>
            </p>
            {expiry_info}
        </div>
        <div class="footer">
            <p>This email was sent by FantasyFolio</p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    Collection Shared With You
    
    {inviter_name} has shared a collection with you on FantasyFolio!
    
    Collection: "{collection_name}"
    Access level: {permissions.capitalize()}
    
    View the collection here:
    {collection_url}
    
    {expiry_text}
    
    ---
    This email was sent by FantasyFolio
    """
    
    return (html_body, text_body)
