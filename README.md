![Falkor Banner](screenshots/homepage.png)

# Falkor - Intelligent Rental Management Platform

> **Build in Public Project**  
> A production-grade rental application management system built with Django, Docker, and HTMX principles. It streamlines the complex NYC rental process for applicants, brokers, and property managers through intelligent automation and privacy-first algorithms.

## 🚀 Key Features

### 🧠 Smart Matching Engine
Unlike standard filters, Falkor uses a weighted scoring algorithm to rank apartments based on nuanced applicant preferences. It considers "must-haves" vs "nice-to-haves," commute times, and lifestyle factors.
*   **See the code:** [`applicants/apartment_matching.py`](applicants/apartment_matching.py) - *Check out the `_calculate_match_percentage` method for the weighted logic.*

### 🛡️ Smart Insights & Analysis
An automated underwriting assistant that pre-screens applicants for affordability and risk factors **without** sending PII to external third-party APIs. It handles financial math safely (using `Decimal` for precision) and respects Fair Housing guidelines.
*   **See the code:** [`applicants/smart_insights.py`](applicants/smart_insights.py) - *Privacy-first, rule-based inference engine.*

### 📄 Document Analysis System
Integrated secure document pipeline that processes applicant uploads (paystubs, tax forms) for income verification, keeping sensitive data within the secure VPC boundary.

## 🛠️ Tech Stack

*   **Backend:** Python 3.9+, Django 4.2
*   **Database:** PostgreSQL
*   **Infrastructure:** Docker & Docker Compose
*   **Frontend:** Bootstrap 5, Vanilla JS (HTMX-style interactions)
*   **External Services:** Cloudinary (Media), SendGrid (Email), Twilio (SMS), Mapbox (Geo)

## 🏗️ Architecture Highlights

*   **Containerized Development:** Full dev environment spins up with a single `docker-compose up` command.
*   **Caching Strategy:** Heavy use of `select_related` and `prefetch_related` to minimize N+1 queries in the high-traffic matching engine.
*   **Security:** Environment variable management via `.env`, secure media handling, and role-based access control (RBAC) for Applicants vs Brokers.

## 💻 Local Setup

### Prerequisites
*   Docker Desktop installed
*   Git

### Steps

1.  **Clone the repository**
    ```bash
    git clone https://github.com/shanewin/falkor-rentalintel.git
    cd door-way
    ```

2.  **Environment Setup**
    Create a `.env` file in the root directory:
    ```bash
    cp .env.example .env
    # Edit .env with your local credentials if needed
    ```

3.  **Launch with Docker**
    ```bash
    docker-compose up --build
    ```
    The app will be available at `http://localhost:8847`.

4.  **Initialize Data** (first run only)
    ```bash
    # Open a new terminal tab
    docker-compose exec web python manage.py migrate
    docker-compose exec web python manage.py createsuperuser
    ```

## 📸 Screenshots

*(More screenshots to be added)*

---

*Built with ❤️ in NYC. This project is part of my public software engineering portfolio.*
