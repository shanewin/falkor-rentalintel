# Production Checklist

## Configuration
- [ ] **Static Files**: 
    - Verify `STATICFILES_STORAGE` in `settings.py`. 
    - Currently set to `StaticFilesStorage` for `DEBUG=True`.
    - For Production (`DEBUG=False`), it is configured to use `cloudinary_storage.storage.StaticHashedCloudinaryStorage`.
    - Ensure `collectstatic` runs successfully in the production environment (note: local environment had dependency issues with `typing_extensions`).

## Media & Images
- [ ] **Replace Random Placeholders**:
    - Currently, `apartment_extras.py` generates "nice" random Unsplash images.
    - **Action**: Replace logic with a static, branded "Image Coming Soon" placeholder.
    - **Reason**: Avoid misleading users with fake "luxury" photos.
- [ ] **Cloudinary Configuration**:
    - Ensure `CLOUDINARY_URL` env var is set in production.

## Code Cleanup
- [ ] **Review `apartment_extras.py`**:
    - Decide if random logic stays for "demo mode" or is removed for static fallback.

## Template Logic
- [ ] **Smart Match Card**:
    - Verify "New" and "Special" badges are driven by real database fields (`is_new`, `has_special`) populated by admin tools.
