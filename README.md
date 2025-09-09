# DoorWay - Rental Application Management System

A comprehensive Django-based rental application management platform designed to streamline the apartment rental process for brokers, property managers, and applicants.

## Features

### For Applicants
- 📝 Progressive profile creation system
- 🏠 Smart apartment matching based on preferences
- 📄 Multi-step application process
- 📱 Mobile-responsive design
- 🔐 Secure document upload

### For Brokers & Admins
- 👥 Complete CRM system with activity tracking
- 🧠 AI-powered Smart Insights for applicant evaluation
- 📊 Comprehensive applicant overview dashboards
- 📧 Automated email/SMS communication
- 🔍 Advanced apartment matching algorithms
- 📈 Real-time activity monitoring

## Tech Stack

- **Backend**: Django 4.2+
- **Database**: PostgreSQL
- **Storage**: Cloudinary
- **Email**: SendGrid
- **SMS**: Twilio
- **Containerization**: Docker & Docker Compose
- **Frontend**: Bootstrap 5, Font Awesome

## Key Components

### Applications System
- Multi-section application flow
- Document analysis capabilities
- Broker pre-fill functionality
- Application status tracking

### Applicants Management
- Progressive profile building
- Smart Insights (AI-powered analysis)
- Activity tracking
- CRM integration

### Apartment Matching
- Preference-based matching
- Amenity filtering
- Location preferences
- Budget optimization

## Setup & Installation

### Prerequisites
- Docker & Docker Compose
- Cloudinary account
- SendGrid account (for emails)
- Twilio account (for SMS)

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/door-way.git
cd door-way
```

2. Create `.env` file with required environment variables:
```bash
SECRET_KEY=your-secret-key
DATABASE_NAME=doorway_db
DATABASE_USER=doorway_user
DATABASE_PASSWORD=doorway_pass
CLOUDINARY_CLOUD_NAME=your-cloudinary-name
CLOUDINARY_API_KEY=your-cloudinary-key
CLOUDINARY_API_SECRET=your-cloudinary-secret
SENDGRID_API_KEY=your-sendgrid-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_FROM_PHONE=your-twilio-phone
```

3. Build and run with Docker:
```bash
docker-compose build
docker-compose up
```

4. Run migrations:
```bash
docker-compose exec web python manage.py migrate
```

5. Create a superuser:
```bash
docker-compose exec web python manage.py createsuperuser
```

6. Access the application:
- Main site: http://localhost:8847
- Admin panel: http://localhost:8847/admin

## Architecture

### User Roles
- **Applicants**: Create profiles, browse apartments, submit applications
- **Brokers**: Manage applicants, create applications, track activities
- **Super Admins**: Full system access, view all activities, manage settings

### Security Features
- Role-based access control
- Secure document handling
- Privacy-first Smart Insights (no PII sent to external services)
- Encrypted sensitive data

## Deployment

The application is Docker-ready and can be deployed to:
- Railway (recommended)
- AWS ECS
- Google Cloud Run
- Heroku
- Any Docker-compatible hosting service

## Contributing

This is a private project. Please contact the repository owner for contribution guidelines.

## License

Proprietary - All rights reserved

## Support

For support, please contact the development team.

---

Built with ❤️ using Django and Docker