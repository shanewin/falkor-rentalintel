# AGENT.md - DoorWay/Falkor Rental Platform

## Project Overview
DoorWay/Falkor is a Django-based rental platform that connects brokers, applicants, and property owners through smart matching and streamlined application workflows.

## Tech Stack
- **Backend**: Django 5.1.6, Python 3.11
- **Database**: PostgreSQL with pgvector extension
- **Cache/Queue**: Redis, Celery
- **Frontend**: Bootstrap 5, Chart.js
- **Deployment**: Docker Compose
- **AI/ML**: OpenAI/Anthropic APIs for document analysis
- **Storage**: Cloudinary for images
- **Communication**: Twilio (SMS), Django email

## Key User Roles

### 1. **Admin/Superuser**
- Full system access via Django admin (/admin/)
- Assigns brokers to buildings and applicants
- Creates broker/staff accounts
- Monitors system-wide metrics

### 2. **Broker**
- Manages assigned applicants and buildings
- Creates applications on behalf of applicants
- Views smart matches between applicants and apartments
- Tracks application progress and documents

### 3. **Applicant**
- Completes multi-step profile
- Receives smart apartment matches
- Submits documents for verification
- Tracks application status

### 4. **Owner**
- Lists properties and buildings
- Reviews applications
- Manages rental terms

## Core Apps Structure

### `applicants/` ✅ PRODUCTION-READY
- **models.py**: Applicant profile with 50+ fields
- **activity_tracker.py**: Comprehensive activity logging
- **apartment_matching.py**: Smart matching algorithm (score-based)
- **smart_insights.py**: AI-powered applicant insights
- **signals.py**: Automated workflows on data changes
- **forms.py**: Multi-step profile forms

### `applications/`
- **models.py**: Application, documents, payments
- **views.py**: 4-step broker creation, applicant interface
- **services.py**: Business logic layer
- **payment_utils.py**: Payment processing

### `apartments/`
- **models.py**: Apartment, amenities, pricing
- **search_api.py**: Advanced search functionality
- **models_extended.py**: Availability, tours, utilities

### `buildings/`
- **models.py**: Building with broker assignments (ManyToMany)
- **management/**: Data import commands

### `users/`
- **models.py**: Custom User with role flags (is_broker, is_applicant, etc.)
- **views.py**: Role-based dashboards and authentication
- **profiles_models.py**: BrokerProfile, AdminProfile
- **email_verification.py**: Email verification system
- **sms_verification.py**: Phone verification via Twilio

### `doc_analysis/`
- **views.py**: AI document analysis endpoint
- **utils.py**: PDF extraction and parsing
- **secure_api_client.py**: LLM integration (OpenAI/Anthropic)

## Critical Business Workflows

### 1. Broker Assignment Flow
```
Admin → Assigns Building → Broker
Admin → Assigns Applicants → Broker
Broker → Views Dashboard → Sees assigned applicants with completion %
Broker → Clicks Applicant → Sees smart matches if profile complete
Broker → Creates Application → Links applicant to apartment
```

### 2. Smart Matching Algorithm
Located in `applicants/apartment_matching.py`:
- Scores based on: budget fit, move date, bedrooms, location
- Returns sorted list with percentage scores
- Caches results for performance

### 3. Application Creation (Broker)
4-step progressive form:
1. Select property (existing or manual)
2. Select applicant (existing or new)
3. Set application parameters
4. Review and create

### 4. Document Analysis Pipeline
- Upload PDF → Extract text (PyPDF2)
- Analyze with LLM (bank statements, pay stubs, tax returns)
- Store embeddings in PostgreSQL (pgvector)
- Return structured analysis with confidence scores

## Database Relationships

```python
# Key Relationships
Building.brokers → ManyToMany → User (where is_broker=True)
Applicant.assigned_broker → ForeignKey → User
Application.broker → ForeignKey → User (creator)
Application.apartment → ForeignKey → Apartment
Application.applicant → ForeignKey → Applicant
Apartment.building → ForeignKey → Building
```

## Authentication & Permissions

### Role-based Redirects (`users/views.py:76`)
```python
if user.is_superuser: → admin_dashboard
elif user.is_broker: → broker_dashboard  
elif user.is_applicant: → applicant_dashboard
```

### Dashboard Access
- Broker dashboard requires: `is_broker=True`
- Admin features require: `is_superuser=True`
- Activity heatmap requires: `is_broker OR is_staff OR is_superuser`

## Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://user:pass@db:5432/dbname

# AI/ML
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Communication
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
EMAIL_HOST_PASSWORD=...

# Storage
CLOUDINARY_URL=cloudinary://...

# Security
SECRET_KEY=django-insecure-...
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Common Commands

### Development
```bash
# Start all services
docker-compose up

# Access Django shell
docker exec door-way-web-1 python manage.py shell

# Run migrations
docker exec door-way-web-1 python manage.py migrate

# Create superuser
docker exec door-way-web-1 python manage.py createsuperuser

# Check system
docker exec door-way-web-1 python manage.py check
```

### Testing
```bash
# Run tests
docker exec door-way-web-1 python manage.py test applicants

# Test specific matching
docker exec door-way-web-1 python manage.py test applicants.tests.test_apartment_matching
```

## URL Structure
- `/` - Home/landing
- `/users/login/` - Authentication
- `/users/dashboard/broker/` - Broker dashboard
- `/users/dashboard/applicant/` - Applicant dashboard
- `/admin/` - Django admin panel
- `/applicants/` - Applicant management
- `/applications/` - Application workflows
- `/apartments/` - Property listings
- `/buildings/` - Building management
- `/applicants/activity/dashboard/` - Activity heatmap

## Known Issues & Solutions

### 1. Field Name Mismatches
- Apartment: `rent_price` (not `rent_per_month`)
- Applicant: `min_bedrooms/max_bedrooms` (not `desired_bedrooms`)

### 2. Performance Optimizations
- Broker dashboard: Fixed O(N*M) to O(N) for smart matching
- Activity tracking: Uses Celery for async processing

### 3. Security Fixes Applied
- Open redirect vulnerability: Added `url_has_allowed_host_and_scheme`
- Commission validation: 0-100% constraints
- Broker authorization: Ownership checks on applications

## Business Logic Highlights

### Smart Insights (`applicants/smart_insights.py`)
- Calculates financial stability scores
- Identifies red flags and green flags
- Generates rental readiness assessment
- Provides match explanations

### Activity Tracking (`applicants/activity_tracker.py`)
- Logs all user actions
- Tracks document uploads/views
- Records status changes
- Generates activity heatmaps for brokers

### Commission Tracking
- BrokerProfile.standard_commission_rate (0-100%)
- Calculated on dashboard based on assigned apartments
- Potential commission = sum(apartment.rent_price * rate / 100)

## Testing Credentials

### Admin Account
- Email: doorway@gmail.com
- Password: admin123
- Access: Full system, Django admin

### Broker Account (Pure)
- Email: broker@example.com
- Password: broker123
- Access: Broker dashboard only

### Applicant Account
- Email: test@example.com
- Password: test123
- Access: Applicant dashboard

## Docker Architecture
```yaml
Services:
- web (Django app, port 8847)
- db (PostgreSQL with pgvector)
- redis (Cache and queue)
- celery (Async task worker)
- nginx (Static files, port 80)
```

## Key Files for Understanding

1. **Business Logic**: `applicants/apartment_matching.py`, `applicants/smart_insights.py`
2. **Workflows**: `applications/views.py` (broker creation), `users/views.py` (dashboards)
3. **Models**: `applicants/models.py`, `applications/models.py`
4. **AI Integration**: `doc_analysis/views.py`, `doc_analysis/utils.py`
5. **Frontend**: `templates/base.html`, dashboard templates in `users/templates/users/dashboards/`

## Deployment Considerations

1. **Production Settings**:
   - Set `DEBUG=False`
   - Configure proper `ALLOWED_HOSTS`
   - Use environment variables for secrets
   - Enable HTTPS

2. **Scaling**:
   - Database: Consider read replicas for heavy matching queries
   - Celery: Scale workers for document processing
   - Cache: Redis for session storage and results

3. **Monitoring**:
   - Activity tracking provides built-in analytics
   - Django admin for user management
   - Celery Flower for task monitoring

## Recent Improvements

1. ✅ Fixed broker dashboard O(N*M) performance issue
2. ✅ Added broker assignment validation
3. ✅ Implemented assigned applicants view with smart matches
4. ✅ Fixed authentication security vulnerabilities
5. ✅ Standardized dashboard styling across roles
6. ✅ Added profile completion tracking
7. ✅ Integrated activity heatmap for brokers

## Next Priority Features

1. **Document Status Tracking** - Show which documents are pending/approved
2. **Follow-up Reminders** - Automated alerts for stale applications
3. **Communication History** - Track all broker-applicant interactions
4. **Bulk Operations** - Assign multiple applicants/buildings at once
5. **Export/Reporting** - Generate reports for owners and management

---
*Last Updated: Nov 2025*
*Version: 1.0*