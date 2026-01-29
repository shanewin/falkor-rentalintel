# Email and SMS Integration Documentation

This document outlines how **SendGrid** (Email) and **Twilio** (SMS) are integrated into the Falkor application.

## 📧 Email Integration (SendGrid)

### Core Components
- **Backend Class**: `SendGridBackend` located in `applications/email_backends.py`.
- **Factory Function**: `get_email_backend()` in `applications/email_backends.py` dynamically selects the backend based on the `EMAIL_SERVICE` setting.

### Key Workflows
1. **User Verification (OTP)**:
   - **Service**: `EmailVerificationService` in `users/email_verification.py`.
   - **Triggers**: Registration, password reset, and email changes.
   - **Templates**: `users/templates/users/emails/email_verification.html`.
   - **Logic**: Generates a 6-digit code, stores it in the Django cache with an expiry, and sends it via `send_mail`.

2. **Application Notifications**: 
   - **Utilities**: `applications/email_utils.py`.
   - **Triggers**: 
      - `send_application_link_email`: Sends initial application links.
      - `send_application_reminder_email`: Automated reminders for incomplete apps.
   - **Templates**: `applications/templates/applications/emails/application_link_email.html`.

3. **Broker & Inquiry Notifications**:
   - **File**: `apartments/services.py`.
   - **Function**: `handle_broker_contact`.
   - **Trigger**: When a user fills out the "Contact Broker" form on an apartment page.

4. **Manual Nudges**:
   - **File**: `applications/views.py` & `applications/nudge_service.py`.
   - **Function**: `nudge_applicant`.
   - **Trigger**: When a broker manually clicks "Nudge" in the dashboard.

### Configuration (Environment Variables)
- `EMAIL_SERVICE`: Set to `sendgrid` to enable.
- `SENDGRID_API_KEY`: Your SendGrid API key.
- `SENDGRID_FROM_EMAIL`: The verified sender (e.g., `info@rentfalkor.com`).
- `DEFAULT_FROM_EMAIL`: The default address for Django's `send_mail`.
- `REPLY_TO_EMAIL`: The address used for the "Reply-To" header.

---

## 📱 SMS Integration (Twilio)

### Core Components
- **Backend Class**: `SMSBackend` in `applications/sms_utils.py`.
- **Validation**: `validate_phone_number` in `applications/sms_utils.py` ensures E.164 format and US defaults.

### Key Workflows
1. **Phone Verification**:
   - **Service**: `PhoneVerificationService` in `users/sms_verification.py`.
   - **Triggers**: Identity verification during registration or profile updates.
   - **Views**: `phone_verification_view` and `sms_preferences_view` in `users/sms_views.py`.
   - **Models**: `SMSPreferences` and `SMSVerificationLog` in `users/sms_models.py`.

2. **Application Links & Nudges**:
   - **Utility**: `send_application_link_sms` in `applications/sms_utils.py`.
   - **Nudge**: `_send_sms_nudge` in `applications/nudge_service.py`.
   - **Trigger**: Notifying applicants or sending reminders via text.

3. **Status Webhooks**:
   - **Endpoint**: `twilio_webhook` in `users/sms_views.py` (handles delivery status and opt-outs like STOP/CANCEL).

### Configuration (Environment Variables)
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
- `TWILIO_FROM_PHONE`: Your Twilio-provided phone number.

---

## 🏷️ Branding Transition: "DoorWay" to "Falkor"

During the research, it was identified that the string **"DoorWay"** is heavily hardcoded across Email and SMS communications. To complete the transition to **Falkor**, the following areas need attention:

### Hardcoded Locations
- **Email Subjects**: Found in `users/email_verification.py` and `templates/registration/password_reset_subject.txt`.
- **SMS Messages**: Found in `users/sms_verification.py`, `applications/sms_utils.py`, and `applications/nudge_service.py`.
- **Email Footers**: Found in `users/templates/users/emails/email_verification.html`.
- **UI Labels**: Found in `users/sms_forms.py` (TCPA consent).

### Recommended Fix
Update these locations to use the `settings.SITE_NAME` variable instead of the hardcoded string. Ensure your `.env` has:
```text
SITE_NAME=Falkor
```

---

## 🔍 Configuration Audit

Based on the latest `.env` changes, here are the potential "obviously errors" or areas for verification:

1. **`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`**: Corrected in `.env`. Line 47 was renamed to `GOOGLE_CLIENT_SECRET`.
2. **`DEFAULT_FROM_EMAIL`**: Currently set to `Falkor <info@rentfalkor.com>`. This is correct for branding, but ensure `info@rentfalkor.com` is exactly matching your verified SendGrid Sender.
3. **`REPLY_TO_EMAIL`**: Ensure this is set to a mailbox you actively monitor.
4. **Celery Redis URL**: Currently `redis://redis:6379/0`. This is correct for **local Docker**, but for **Railway production**, it must be updated to use the dynamic `REDIS_URL`.
5. **Twilio Phone Format**: `TWILIO_FROM_PHONE` must be in E.164 format (e.g., `+1234567890`).

---

## 🛠️ Verification and Testing

### Testing Emails locally
1. Set `EMAIL_SERVICE=console` in `.env` to see email content in the terminal.
2. Set `EMAIL_SERVICE=sendgrid` with valid keys to test real delivery.

### Testing SMS locally
1. Ensure `DEBUG=True` to allow local redirect URIs.
2. Use the `send_test_sms` utility in `applications/sms_utils.py` to verify configuration.

---

## ⚠️ Known Issues and Considerations
- **Rate Limiting**: Both email and SMS verification services have built-in hourly and daily limits (handled via Django cache).
- **Template Paths**: Templates follow the standard Django structure and are located within their respective app `templates/` folders.
