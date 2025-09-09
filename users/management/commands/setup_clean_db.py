from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from applicants.models import Applicant
from applications.models import Application, ApplicationActivity, UploadedFile
from buildings.models import Building
from apartments.models import Apartment

User = get_user_model()

class Command(BaseCommand):
    help = 'Clean database and create example accounts for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete data',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This command will delete data! Use --confirm to proceed.'
                )
            )
            return

        try:
            with transaction.atomic():
                # Step 1: Show current counts
                self.stdout.write(self.style.SUCCESS('\n=== CURRENT STATE ==='))
                self.show_counts()

                # Step 2: Delete selective data
                self.stdout.write(self.style.SUCCESS('\n=== CLEANING DATABASE ==='))
                self.clean_database()

                # Step 3: Create example accounts
                self.stdout.write(self.style.SUCCESS('\n=== CREATING EXAMPLE ACCOUNTS ==='))
                self.create_example_accounts()

                # Step 4: Show final counts
                self.stdout.write(self.style.SUCCESS('\n=== FINAL STATE ==='))
                self.show_counts()

                self.stdout.write(
                    self.style.SUCCESS('\n✅ Database cleanup and setup completed successfully!')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during database setup: {str(e)}')
            )
            raise CommandError(f'Database setup failed: {str(e)}')

    def show_counts(self):
        """Display current database counts"""
        user_count = User.objects.count()
        applicant_count = Applicant.objects.count()
        application_count = Application.objects.count()
        building_count = Building.objects.count()
        apartment_count = Apartment.objects.count()

        # User type breakdown
        superuser_count = User.objects.filter(is_superuser=True).count()
        staff_count = User.objects.filter(is_staff=True, is_superuser=False).count()
        broker_count = User.objects.filter(is_broker=True).count()
        applicant_user_count = User.objects.filter(is_applicant=True).count()
        owner_count = User.objects.filter(is_owner=True).count()

        self.stdout.write(f'  Users: {user_count}')
        self.stdout.write(f'    - Superusers: {superuser_count}')
        self.stdout.write(f'    - Staff: {staff_count}')
        self.stdout.write(f'    - Brokers: {broker_count}')
        self.stdout.write(f'    - Applicant Users: {applicant_user_count}')
        self.stdout.write(f'    - Owners: {owner_count}')
        self.stdout.write(f'  Applicants: {applicant_count}')
        self.stdout.write(f'  Applications: {application_count}')
        self.stdout.write(f'  Buildings: {building_count}')
        self.stdout.write(f'  Apartments: {apartment_count}')

    def clean_database(self):
        """Delete selective data from database"""
        
        # Delete all applicant records
        applicant_count = Applicant.objects.count()
        if applicant_count > 0:
            Applicant.objects.all().delete()
            self.stdout.write(f'  ✅ Deleted {applicant_count} applicant records')
        else:
            self.stdout.write('  ℹ️  No applicant records to delete')

        # Delete all application records (including related data)
        application_count = Application.objects.count()
        if application_count > 0:
            # Delete related data first
            UploadedFile.objects.all().delete()
            ApplicationActivity.objects.all().delete()
            Application.objects.all().delete()
            self.stdout.write(f'  ✅ Deleted {application_count} application records and related data')
        else:
            self.stdout.write('  ℹ️  No application records to delete')

        # Delete all user accounts EXCEPT doorway@gmail.com superuser
        excluded_users = User.objects.filter(email='doorway@gmail.com', is_superuser=True)
        if excluded_users.exists():
            superuser_email = excluded_users.first().email
            other_users = User.objects.exclude(email='doorway@gmail.com')
            other_user_count = other_users.count()
            if other_user_count > 0:
                other_users.delete()
                self.stdout.write(f'  ✅ Deleted {other_user_count} user accounts (kept {superuser_email})')
            else:
                self.stdout.write(f'  ℹ️  No other user accounts to delete (kept {superuser_email})')
        else:
            self.stdout.write('  ⚠️  Warning: doorway@gmail.com superuser not found!')

    def create_example_accounts(self):
        """Create example accounts for testing"""
        
        # Create broker account
        broker_user = User.objects.create_user(
            email='broker@example.com',
            password='password123',
            is_broker=True
        )
        self.stdout.write(f'  ✅ Created broker account: {broker_user.email}')

        # Create staff account
        staff_user = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            is_staff=True
        )
        self.stdout.write(f'  ✅ Created staff account: {staff_user.email}')

        # Create owner account
        owner_user = User.objects.create_user(
            email='owner@example.com',
            password='password123',
            is_owner=True
        )
        self.stdout.write(f'  ✅ Created owner account: {owner_user.email}')

        self.stdout.write('  📝 All example accounts use password: password123')