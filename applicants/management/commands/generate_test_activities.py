"""
Generate Test Activity Data
===========================

Management command to generate sample activity data for testing the dashboard.
Usage: python manage.py generate_test_activities
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from applicants.models import Applicant, ApplicantActivity


class Command(BaseCommand):
    help = 'Generate test activity data for dashboard demonstration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of data to generate'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing activities before generating'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        
        if options['clear']:
            self.stdout.write('Clearing existing activities...')
            ApplicantActivity.objects.all().delete()
        
        # Get applicants or create a test one
        applicants = list(Applicant.objects.all()[:10])
        if not applicants:
            self.stdout.write(self.style.WARNING('No applicants found. Please create at least one applicant.'))
            return
        
        activity_types = [
            'profile_viewed', 'apartment_viewed', 'application_updated',
            'document_uploaded', 'email_sent', 'login', 'property_search'
        ]
        
        # Generate activities
        activities_created = 0
        now = timezone.now()
        
        for day in range(days, -1, -1):
            current_date = now - timedelta(days=day)
            
            # Vary activity by day of week (more on weekdays)
            if current_date.weekday() < 5:  # Monday-Friday
                daily_activities = random.randint(5, 20)
            else:  # Weekend
                daily_activities = random.randint(2, 10)
            
            for _ in range(daily_activities):
                # Peak hours: 9-11am, 2-4pm, 7-9pm
                hour_weights = [0.1] * 7 + [0.3] * 3 + [0.5] * 2 + [0.3] * 2 + \
                              [0.5] * 3 + [0.3] * 2 + [0.5] * 3 + [0.2] * 2
                hour = random.choices(range(24), weights=hour_weights)[0]
                minute = random.randint(0, 59)
                
                activity_time = current_date.replace(
                    hour=hour,
                    minute=minute,
                    second=random.randint(0, 59)
                )
                
                applicant = random.choice(applicants)
                activity_type = random.choice(activity_types)
                
                # Generate appropriate description
                descriptions = {
                    'profile_viewed': f'Viewed profile details',
                    'apartment_viewed': f'Viewed apartment #{random.randint(100, 999)}',
                    'application_updated': f'Updated application information',
                    'document_uploaded': f'Uploaded {random.choice(["ID", "Income proof", "Reference letter"])}',
                    'email_sent': f'Email sent to applicant',
                    'login': f'Logged into the system',
                    'property_search': f'Searched for properties in {random.choice(["Manhattan", "Brooklyn", "Queens"])}'
                }
                
                ApplicantActivity.objects.create(
                    applicant=applicant,
                    activity_type=activity_type,
                    description=descriptions.get(activity_type, 'Activity performed'),
                    created_at=activity_time,
                    metadata={
                        'generated': True,
                        'test_data': True
                    }
                )
                activities_created += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated {activities_created} test activities over {days} days')
        )