# Use official Python image as base
FROM python:3.11

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client


COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt


COPY . .


RUN python manage.py collectstatic --noinput


EXPOSE 8000


ENV TESSERACT_CMD="/usr/bin/tesseract"


CMD ["sh", "-c", "until pg_isready -h $DATABASE_HOST -p $DATABASE_PORT; do sleep 2; done && python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
