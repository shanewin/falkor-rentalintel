# CSS Architecture & Design System

## 1. File Structure (1-File-Per-App)
We follow a strict **1-File-Per-App** consolidation strategy to maintain modularity while ensuring global consistency.

| App | CSS File Path | Purpose |
| :--- | :--- | :--- |
| **Global Theme** | `static/css/doorway-theme.css` | **Source of Truth**. Defines `:root` variables, reset, and global utilities. |
| **Shared Utility** | `static/css/photo-upload.css` | Cloudinary widget styling. |
| **Users** | `users/static/users/css/users.css` | Login, Registration, Role Selection, Profile settings. |
| **Apartments** | `apartments/static/apartments/css/apartments.css` | Apartment listings, details, and map views. |
| **Applications** | `applications/static/applications/css/applications.css` | Application forms, status tracking, and management. |
| **Applicants** | `applicants/static/applicants/css/applicants.css` | Applicant profile, dashboard, and preferences. |
| **Buildings** | `buildings/static/buildings/css/buildings.css` | Building management, overview, and stats. |

## 2. Design System & Variables
All application styling **MUST** consume variables from `doorway-theme.css`. Hardcoded hex values (e.g., `#ffd60a`) are strictly forbidden in app-specific files.

### Core Variables (`:root`)
These are defined in `doorway-theme.css`:

```css
:root {
    /* Brand Colors */
    --brand-yellow: #ffd60a;       /* Primary Accent (Action) */
    --brand-black: #000814;        /* Primary Dark (Backgrounds/Text) */
    --brand-dark-gray: #1a1a1a;    /* Secondary Dark */
    --brand-light-gray: #f8f9fa;   /* Background Light */
    --brand-white: #ffffff;
    --brand-orange: #fd7e14;       /* Priority/Important Status */

    /* Functional Colors */
    --text-dark: #2c3e50;
    --text-muted: #6c757d;
    --border-color: #dee2e6;
    --success: #28a745;
    --danger: #dc3545;
    --warning: #ffc107;
    --info: #17a2b8;
    
    /* Links */
    --link-color: #007bff;
    --link-hover-color: #0056b3;

    /* Layout & Effects */
    --border-radius: 8px;
    --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.1);
    --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.15);
    --transition: all 0.2s ease;
}
```

### Usage Example
**Do NOT do this:**
```css
.btn-primary {
    background-color: #ffd60a; /* BAD: Hardcoded */
    color: #000000;
}
```

**DO this:**
```css
.btn-primary {
    background-color: var(--brand-yellow); /* GOOD: Uses token */
    color: var(--brand-black);
}
```

## 3. Django Configuration
The static files configuration in `realestate/settings.py` controls how these files are served.

- **STATIC_URL**: `/static/`
- **App Directories**: Django's `staticfiles` finder automatically looks for `static/` directories within installed apps (e.g., `users/static`).
- **STATICFILES_DIRS**:
  The project explicitly adds specific app static subdirectories to `STATICFILES_DIRS`. This allows direct access to assets without the app namespace in some contexts, though using the namespace (e.g., `{% static 'users/css/...' %}`) is recommended for clarity.

  ```python
  STATICFILES_DIRS = [
      BASE_DIR / 'staticfiles',
      BASE_DIR / 'static',       # Global static assets
      BASE_DIR / 'apartments/static/apartments',
      BASE_DIR / 'applicants/static/applicants',
      BASE_DIR / 'buildings/static/buildings',
      BASE_DIR / 'applications/static/applications',
      BASE_DIR / 'users/static/users',
  ]
  ```
  *Note: All app static directories are explicitly listed to allow flattened access if needed, though namespaced access is preferred.*
