from django.core.management.base import BaseCommand
from django.db import connection, ProgrammingError


class Command(BaseCommand):
    help = "Ensure pgvector extension is enabled and report status."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check if extension exists
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');")
            exists = cursor.fetchone()[0]

            if exists:
                self.stdout.write(self.style.SUCCESS("pgvector extension is already enabled."))
            else:
                self.stdout.write("pgvector extension not found; attempting to create it...")
                try:
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    self.stdout.write(self.style.SUCCESS("pgvector extension created."))
                except ProgrammingError as e:
                    self.stderr.write(self.style.ERROR(f"Failed to create pgvector extension: {e}"))
                    return

            # Show regtype check
            try:
                cursor.execute("SELECT 'vector'::regtype::text;")
                regtype = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f"Vector type available: {regtype}"))
            except ProgrammingError as e:
                self.stderr.write(self.style.ERROR(f"Vector type check failed: {e}"))
                return

            # Table/column sanity check (best effort)
            cursor.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'doc_analysis_documentembedding'
                  AND column_name = 'embedding';
                """
            )
            col_info = cursor.fetchone()
            if col_info:
                self.stdout.write(self.style.SUCCESS(f"Embedding column present: {col_info}"))
            else:
                self.stdout.write("Embedding column not found (migrations may be pending).")

