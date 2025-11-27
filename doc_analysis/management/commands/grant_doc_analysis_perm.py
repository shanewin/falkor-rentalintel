from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from doc_analysis.models import DocumentEmbedding


class Command(BaseCommand):
    help = "Grant doc_analysis.can_analyze_documents to brokers and a 'Brokers' group if present."

    def handle(self, *args, **options):
        User = get_user_model()

        # Fetch permission
        try:
            ct = ContentType.objects.get_for_model(DocumentEmbedding)
            perm = Permission.objects.get(content_type=ct, codename="can_analyze_documents")
        except Permission.DoesNotExist:
            self.stderr.write(self.style.ERROR("Permission doc_analysis.can_analyze_documents not found. Run migrations first."))
            return

        # Assign to Brokers group if it exists
        try:
            brokers_group = Group.objects.get(name__iexact="Brokers")
            if perm not in brokers_group.permissions.all():
                brokers_group.permissions.add(perm)
                self.stdout.write(self.style.SUCCESS("Added permission to 'Brokers' group."))
            else:
                self.stdout.write("Permission already on 'Brokers' group.")
        except Group.DoesNotExist:
            self.stdout.write("No 'Brokers' group found; skipping group assignment.")

        # Assign to broker users (flag)
        brokers = User.objects.filter(is_broker=True)
        count = 0
        for user in brokers:
            if not user.has_perm("doc_analysis.can_analyze_documents"):
                user.user_permissions.add(perm)
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Granted permission to {count} broker user(s)."))

        # Superusers already have all permissions; no action needed.
