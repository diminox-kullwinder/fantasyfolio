"""
Email Settings API Blueprint.

Handles email configuration, testing, and status.
"""

import logging
from flask import Blueprint, jsonify, request

from fantasyfolio.core.database import set_setting, get_setting
from fantasyfolio.services.email import get_email_service

logger = logging.getLogger(__name__)
email_settings_bp = Blueprint('email_settings', __name__)


@email_settings_bp.route('/email/config', methods=['GET'])
def get_email_config():
    """Get current email configuration (without sensitive data)."""
    config = {
        'provider': get_setting('email_provider') or 'smtp',
        'from_address': get_setting('email_from_address') or '',
        'from_name': get_setting('email_from_name') or 'FantasyFolio',
        'smtp_host': get_setting('email_smtp_host') or '',
        'smtp_port': get_setting('email_smtp_port') or '587',
        'smtp_user': get_setting('email_smtp_user') or '',
        'smtp_use_tls': get_setting('email_smtp_use_tls') != 'false',
        'sendgrid_configured': bool(get_setting('email_sendgrid_api_key')),
        'ses_region': get_setting('email_ses_region') or '',
        'ses_configured': bool(get_setting('email_ses_access_key')),
    }
    
    # Check if configured
    email_service = get_email_service()
    config['is_configured'] = email_service.is_configured()
    
    return jsonify(config)


@email_settings_bp.route('/email/config', methods=['POST'])
def update_email_config():
    """Update email configuration."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Update provider
    if 'provider' in data:
        set_setting('email_provider', data['provider'])
    
    # Update common settings
    if 'from_address' in data:
        set_setting('email_from_address', data['from_address'])
    if 'from_name' in data:
        set_setting('email_from_name', data['from_name'])
    
    # Update SMTP settings
    if 'smtp_host' in data:
        set_setting('email_smtp_host', data['smtp_host'])
    if 'smtp_port' in data:
        set_setting('email_smtp_port', str(data['smtp_port']))
    if 'smtp_user' in data:
        set_setting('email_smtp_user', data['smtp_user'])
    if 'smtp_password' in data and data['smtp_password']:
        # TODO: Encrypt password before storing
        set_setting('email_smtp_password', data['smtp_password'])
    if 'smtp_use_tls' in data:
        set_setting('email_smtp_use_tls', 'true' if data['smtp_use_tls'] else 'false')
    
    # Update SendGrid settings
    if 'sendgrid_api_key' in data and data['sendgrid_api_key']:
        # TODO: Encrypt API key before storing
        set_setting('email_sendgrid_api_key', data['sendgrid_api_key'])
    
    # Update AWS SES settings
    if 'ses_region' in data:
        set_setting('email_ses_region', data['ses_region'])
    if 'ses_access_key' in data and data['ses_access_key']:
        # TODO: Encrypt keys before storing
        set_setting('email_ses_access_key', data['ses_access_key'])
    if 'ses_secret_key' in data and data['ses_secret_key']:
        set_setting('email_ses_secret_key', data['ses_secret_key'])
    
    return jsonify({'success': True, 'message': 'Email configuration updated'})


@email_settings_bp.route('/email/test', methods=['POST'])
def test_email():
    """Send a test email to verify configuration."""
    data = request.get_json(silent=True)
    if not data or 'to_address' not in data:
        return jsonify({'error': 'Recipient email address required'}), 400
    
    to_address = data['to_address']
    
    # Validate email format (basic check)
    if '@' not in to_address or '.' not in to_address.split('@')[1]:
        return jsonify({'error': 'Invalid email address format'}), 400
    
    email_service = get_email_service()
    
    if not email_service.is_configured():
        return jsonify({'error': 'Email service is not configured'}), 400
    
    try:
        success = email_service.send_test_email(to_address)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Test email sent to {to_address}'
            })
        else:
            return jsonify({
                'error': 'Failed to send test email. Check server logs for details.'
            }), 500
    
    except Exception as e:
        logger.error(f"Test email error: {e}")
        return jsonify({'error': str(e)}), 500


@email_settings_bp.route('/email/status', methods=['GET'])
def email_status():
    """Get email service status."""
    email_service = get_email_service()
    
    return jsonify({
        'configured': email_service.is_configured(),
        'provider': email_service.provider,
        'from_address': email_service.from_address,
        'from_name': email_service.from_name
    })
