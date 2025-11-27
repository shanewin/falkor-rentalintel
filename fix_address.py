#!/usr/bin/env python3
"""Fix address field in template"""

# Read current template
with open('apartments/templates/apartments/apartments_list.html', 'r') as f:
    content = f.read()

# Replace apartment.building.address with apartment.building.street_address_1
content = content.replace('{{ apartment.building.address }}', '{{ apartment.building.street_address_1 }}')

# Write back
with open('apartments/templates/apartments/apartments_list.html', 'w') as f:
    f.write(content)

print("Fixed address field in template")
