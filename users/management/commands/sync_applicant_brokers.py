from django.core.management.base import BaseCommand
from applications.models import Application
from applicants.models import Applicant

class Command(BaseCommand):
    help = 'Syncs Applicant assigned_broker based on their Applications'

    def handle(self, *args, **options):
        self.stdout.write('Starting Applicant-Broker sync...')
        
        # Find applications with a broker and an applicant
        applications = Application.objects.filter(
            broker__isnull=False,
            applicant__isnull=False
        ).select_related('broker', 'applicant')
        
        updated_count = 0
        
        for app in applications:
            applicant = app.applicant
            broker = app.broker
            
            # If applicant has no assigned broker, or it's different (optional policy: latest app wins?)
            # For now, let's just set it if it's None, or update it to ensure they are linked.
            # The requirement says: "For every Application owned by a Broker, ensure the linked Applicant.assigned_broker is set to that same Broker."
            
            if applicant.assigned_broker != broker:
                old_broker = applicant.assigned_broker
                applicant.assigned_broker = broker
                applicant.save(update_fields=['assigned_broker'])
                updated_count += 1
                self.stdout.write(f'Updated Applicant {applicant.id} ({applicant}): {old_broker} -> {broker}')
                
        self.stdout.write(self.style.SUCCESS(f'Successfully synced {updated_count} applicants.'))
