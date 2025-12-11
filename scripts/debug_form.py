#!/usr/bin/env python3

import os
import sys
import django
from django.conf import settings

# Add the project directory to the path
project_dir = '/Users/shanewinter/Desktop/door-way'
sys.path.append(project_dir)
os.chdir(project_dir)

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate_project.settings')
django.setup()

from users.profile_forms import AdminProfileForm
from users.profiles_models import AdminProfile

# Create a form instance
form = AdminProfileForm()

# Print the rendered form HTML to see the actual structure
print("=== ACTUAL FORM HTML OUTPUT ===")
print(form.as_p())

print("\n=== CRISPY FORM HELPER LAYOUT ===")
if hasattr(form, 'helper') and form.helper.layout:
    print("Form helper exists with layout")
    print("Layout fields:", form.helper.layout.fields)
else:
    print("No form helper or layout found")

print("\n=== FORM FIELD LABELS ===")
for field_name, field in form.fields.items():
    print(f"{field_name}: label='{field.label}', widget={type(field.widget).__name__}")