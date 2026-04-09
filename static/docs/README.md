# Legal Document PDFs

Place the following required PDF documents in this directory:

1. `ny_discrimination_disclosure.pdf` — NY State Housing & Anti-Discrimination Disclosure Form
2. `ny_landlord_tenant_disclosure.pdf` — NY State Disclosure Form for Landlord and Tenant

## Connecting the PDFs

Once the PDFs are placed here, update the Section 3 view in `applications/views.py` 
(around line 2559) to add these URLs to the context:

```python
context = {
    ...
    'discrimination_pdf_url': static('docs/ny_discrimination_disclosure.pdf'),
    'brokers_pdf_url': static('docs/ny_landlord_tenant_disclosure.pdf'),
    ...
}
```

Then run `python manage.py collectstatic` to make them available.
