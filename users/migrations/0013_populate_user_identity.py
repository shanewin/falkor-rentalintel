from django.db import migrations

def populate_user_identity(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Applicant = apps.get_model('applicants', 'Applicant')
    BrokerProfile = apps.get_model('users', 'BrokerProfile')
    OwnerProfile = apps.get_model('users', 'OwnerProfile')
    StaffProfile = apps.get_model('users', 'StaffProfile')
    AdminProfile = apps.get_model('users', 'AdminProfile')

    # 1. Applicants
    for applicant in Applicant.objects.all():
        user = applicant.user
        changed = False
        if not user.first_name and applicant._first_name:
            user.first_name = applicant._first_name
            changed = True
        if not user.last_name and applicant._last_name:
            user.last_name = applicant._last_name
            changed = True
        if not user.phone_number and applicant._phone_number:
            user.phone_number = applicant._phone_number
            changed = True
        
        if changed:
            user.save()

    # 2. Brokers
    for broker in BrokerProfile.objects.all():
        user = broker.user
        changed = False
        if not user.first_name and broker._first_name:
            user.first_name = broker._first_name
            changed = True
        if not user.last_name and broker._last_name:
            user.last_name = broker._last_name
            changed = True
        
        # Check _phone_number (renamed) or mobile_phone
        phone = getattr(broker, '_phone_number', None)
        if not phone and hasattr(broker, 'mobile_phone'):
            phone = broker.mobile_phone
            
        if not user.phone_number and phone:
            user.phone_number = phone
            changed = True
            
        if changed:
            user.save()

    # 3. Owners
    for owner in OwnerProfile.objects.all():
        user = owner.user
        changed = False
        if not user.first_name and owner._first_name:
            user.first_name = owner._first_name
            changed = True
        if not user.last_name and owner._last_name:
            user.last_name = owner._last_name
            changed = True
            
        # Check _primary_phone
        phone = getattr(owner, '_primary_phone', None)
        if not user.phone_number and phone:
            user.phone_number = phone
            changed = True
            
        if changed:
            user.save()

    # 4. Staff
    for staff in StaffProfile.objects.all():
        user = staff.user
        changed = False
        if not user.first_name and staff._first_name:
            user.first_name = staff._first_name
            changed = True
        if not user.last_name and staff._last_name:
            user.last_name = staff._last_name
            changed = True
            
        # Staff uses mobile_phone or office_phone
        phone = staff.mobile_phone if staff.mobile_phone else staff.office_phone
        if not user.phone_number and phone:
            user.phone_number = phone
            changed = True
            
        if changed:
            user.save()

    # 5. Admin
    for admin in AdminProfile.objects.all():
        user = admin.user
        changed = False
        if not user.first_name and admin._first_name:
            user.first_name = admin._first_name
            changed = True
        if not user.last_name and admin._last_name:
            user.last_name = admin._last_name
            changed = True
            
        if not user.phone_number and admin._phone_number:
            user.phone_number = admin._phone_number
            changed = True
            
        if changed:
            user.save()

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_alter_staffprofile_options_and_more'),
        ('applicants', '0028_alter_applicant_first_name_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_user_identity, migrations.RunPython.noop),
    ]
