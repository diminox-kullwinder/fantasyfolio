# FantasyFolio Services

Business logic services for FantasyFolio.

## Email Service

Multi-provider email service with support for SMTP, SendGrid, and AWS SES.

### Configuration

Email settings are stored in the `settings` database table:

**Common:**
- `email_provider` - 'smtp', 'sendgrid', or 'ses'
- `email_from_address` - From email address
- `email_from_name` - From display name

**SMTP:**
- `email_smtp_host` - SMTP server hostname
- `email_smtp_port` - Port (587 for TLS, 465 for SSL)
- `email_smtp_user` - Username
- `email_smtp_password` - Password
- `email_smtp_use_tls` - 'true' or 'false'

**SendGrid:**
- `email_sendgrid_api_key` - SendGrid API key

**AWS SES:**
- `email_ses_region` - AWS region
- `email_ses_access_key` - IAM access key
- `email_ses_secret_key` - IAM secret key

### Usage

```python
from fantasyfolio.services.email import get_email_service
from fantasyfolio.services.email_templates import verification_email

# Get the email service
email_service = get_email_service()

# Check if configured
if not email_service.is_configured():
    print("Email service not configured")
    return

# Generate email content from template
html_body, text_body = verification_email(
    username="john_doe",
    verification_url="https://example.com/verify?token=abc123"
)

# Send email
success = email_service.send(
    to_address="user@example.com",
    subject="Verify Your Email",
    html_body=html_body,
    text_body=text_body
)

if success:
    print("Email sent successfully")
else:
    print("Failed to send email - check logs")
```

### Templates

Available in `email_templates.py`:

1. **verification_email(username, verification_url)** - Account verification
2. **password_reset_email(username, reset_url)** - Password reset
3. **collection_share_invite_email(inviter_name, collection_name, collection_url, permissions, expiry_date)** - Collection sharing

All templates return `(html_body, text_body)` tuples.

### Admin UI

Configuration available in: **Settings → 📧 Email**

Features:
- Provider selection with auto-switching forms
- Quick setup buttons (Gmail, Office 365, SendGrid)
- Test email functionality
- Status indicators

### API Endpoints

- `GET /api/email/config` - Get current configuration (no passwords)
- `POST /api/email/config` - Update configuration
- `GET /api/email/status` - Check if configured
- `POST /api/email/test` - Send test email

### Testing

```bash
# Check status
curl -sk https://localhost:8008/api/email/status | python3 -m json.tool

# Send test email
curl -sk https://localhost:8008/api/email/test \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"to_address": "your-email@example.com"}' \
  | python3 -m json.tool
```

### Provider Setup

**Gmail:**
1. Enable 2-Step Verification: https://myaccount.google.com/security
2. Create App Password: https://myaccount.google.com/apppasswords
3. Use App Password (not regular password)
4. Host: `smtp.gmail.com`, Port: `587`, TLS: Yes

**SendGrid:**
1. Sign up: https://signup.sendgrid.com/
2. Create API key: https://app.sendgrid.com/settings/api_keys
3. Option A: Use SendGrid provider with API key
4. Option B: Use SMTP with `smtp.sendgrid.net:587`, username `apikey`, password = API key

**Office 365:**
- Host: `smtp.office365.com`, Port: `587`, TLS: Yes

**AWS SES:**
1. Create IAM user with SES permissions
2. Get access key + secret key
3. Verify sender email in SES console
4. Configure region (e.g., `us-east-1`)

### Security Notes

**TODO:** Encrypt passwords and API keys in database
- Currently stored as plain text in settings table
- Consider using Fernet (symmetric encryption) or secrets manager
- Key should be in environment variable, not in code

### Dependencies

Built-in (no install needed):
- `smtplib` - SMTP support

Optional (install if needed):
- `sendgrid` - For SendGrid API (not required for SendGrid SMTP)
- `boto3` - For AWS SES

```bash
# Optional installs
pip install sendgrid  # For SendGrid API support
pip install boto3     # For AWS SES support
```

### Troubleshooting

**"Email service not configured"**
- Check settings in database: `SELECT * FROM settings WHERE key LIKE 'email_%';`
- Verify all required fields are set for your provider

**"Failed to send email"**
- Check server logs for detailed error
- Verify credentials are correct
- For Gmail: Ensure 2FA is enabled and using App Password
- For SMTP: Test with telnet: `telnet smtp.gmail.com 587`

**"Connection refused"**
- Firewall blocking port 587 or 465
- Check network connectivity
- Try different port (587 vs 465)

**"Authentication failed"**
- Wrong username/password
- Gmail: Must use App Password, not account password
- SendGrid SMTP: Username must be `apikey` (literal string)

### Logging

Email service logs to `fantasyfolio.services.email` logger.

Enable debug logging:
```python
import logging
logging.getLogger('fantasyfolio.services.email').setLevel(logging.DEBUG)
```

Successful sends log at INFO level:
```
[INFO] Email sent via SMTP to user@example.com
```

Errors log at ERROR level with details.
