# Use official Python image as base
FROM python:3.11

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the entire project
COPY . .

# Set dummy environment variables for build time only
# These will be overridden by Railway's actual environment variables at runtime
ENV SECRET_KEY=dummy-secret-key-for-build \
    DEBUG=False \
    DATABASE_URL=postgresql://user:pass@localhost/db \
    CLOUDINARY_CLOUD_NAME=dummy \
    CLOUDINARY_API_KEY=dummy \
    CLOUDINARY_API_SECRET=dummy \
    SENDGRID_API_KEY=dummy \
    TWILIO_ACCOUNT_SID=dummy \
    TWILIO_AUTH_TOKEN=dummy \
    TWILIO_FROM_PHONE=dummy \
    FIELD_ENCRYPTION_KEY=dummy-encryption-key

# Collect static files (with dummy env vars)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Use gunicorn for production instead of runserver
CMD ["sh", "-c", "python manage.py migrate && gunicorn realestate.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
