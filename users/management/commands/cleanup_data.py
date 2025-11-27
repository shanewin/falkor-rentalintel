from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from buildings.models import Building, BuildingImage, BuildingAccess, BuildingSpecial
from apartments.models import Apartment, ApartmentImage, ApartmentAmenity
from applicants.models import Applicant, ApplicantPhoto, Pet, PetPhoto, PreviousAddress, IdentificationDocument, ApplicantCRM
from applications.models import Application, UploadedFile, ApplicationSection, PersonalInfoData, IncomeData, LegalDocuments, ApplicationPayment

User = get_user_model()

class Command(BaseCommand):
    help = 'Cleans up all generated test data from the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting data cleanup...'))

        # 1. Delete Applications and related data
        self.stdout.write('Deleting Applications...')
        Application.objects.all().delete()
        
        # 2. Delete Applicants and related data
        self.stdout.write('Deleting Applicants...')
        Applicant.objects.all().delete()
        
        # 3. Delete Apartments and Buildings
        self.stdout.write('Deleting Apartments and Buildings...')
        Apartment.objects.all().delete()
        Building.objects.all().delete()
        
        # 4. Delete Users (Brokers and Applicants, keep Superusers if needed, but for now wipe all non-staff/superuser or just all generated ones)
        # Strategy: Delete all users except those that look like "real" admins or the one running the script?
        # For a true reset, we usually want to keep the main admin.
        # Let's delete all users that are NOT superusers for now, or maybe just delete everyone and let the seed script recreate the superusers.
        # The prompt asked for "Reliable Cleanup Script to reset the test database".
        # Let's delete all users except superusers to be safe, or maybe just delete all users.
        # Given the seed script creates superusers, let's delete all users to ensure a clean slate, 
        # BUT we must be careful not to delete the user's actual account if they are using it.
        # Safest bet: Delete all users where is_superuser=False, and maybe specific superusers created by seed.
        
        self.stdout.write('Deleting Users (excluding existing superusers)...')
        # We will delete all users that are NOT superusers. 
        # If we want to delete generated superusers too, we might need a way to identify them.
        # For now, let's wipe all brokers and applicants.
        User.objects.filter(is_superuser=False).delete()
        
        # Also delete superusers that match our seed pattern if we want to be thorough,
        # but for safety let's just print a message.
        self.stdout.write(self.style.SUCCESS('Deleted all non-superuser accounts.'))
        
        # Optional: Delete superusers created by seed script if they exist?
        # seed_emails = ['admin1@doorway.com', 'admin2@doorway.com', 'admin3@doorway.com']
        # User.objects.filter(email__in=seed_emails).delete()
        
        self.stdout.write(self.style.SUCCESS('Data cleanup complete!'))
