"""
Management command to rebuild apartment search index.
Business Context: Maintains search accuracy and performance.
Should be run after bulk imports or major data changes.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apartments.models import Apartment
from apartments.search_models import ApartmentSearchIndex
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rebuild the full-text search index for all apartments'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing index before rebuilding',
        )
        parser.add_argument(
            '--building-id',
            type=int,
            help='Only rebuild index for apartments in specific building',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of apartments to process in each batch',
        )
    
    def handle(self, *args, **options):
        """Execute the command"""
        clear_existing = options['clear']
        building_id = options.get('building_id')
        batch_size = options['batch_size']
        
        # Clear existing index if requested
        if clear_existing:
            self.stdout.write('Clearing existing search index...')
            ApartmentSearchIndex.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Index cleared'))
        
        # Get apartments to index
        apartments = Apartment.objects.all()
        if building_id:
            apartments = apartments.filter(building_id=building_id)
            self.stdout.write(f'Filtering to building ID {building_id}')
        
        total_count = apartments.count()
        self.stdout.write(f'Found {total_count} apartments to index')
        
        # Process in batches for better performance
        processed = 0
        errors = 0
        
        for apartment in apartments.iterator(chunk_size=batch_size):
            try:
                with transaction.atomic():
                    # Get or create search index
                    search_index, created = ApartmentSearchIndex.objects.get_or_create(
                        apartment=apartment
                    )
                    
                    # Rebuild the index
                    search_index.rebuild_index()
                    
                    processed += 1
                    
                    # Progress update
                    if processed % batch_size == 0:
                        self.stdout.write(
                            f'Processed {processed}/{total_count} apartments '
                            f'({processed * 100 // total_count}%)'
                        )
                        
            except Exception as e:
                errors += 1
                logger.error(f"Error indexing apartment {apartment.id}: {e}")
                self.stdout.write(
                    self.style.ERROR(f'Error indexing apartment {apartment.id}: {e}')
                )
        
        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nIndexing complete! '
                f'Successfully indexed {processed - errors} apartments. '
                f'Errors: {errors}'
            )
        )
        
        # Update statistics
        self._update_search_statistics()
    
    def _update_search_statistics(self):
        """Update search-related statistics"""
        from django.db.models import Count
        
        # Count indexed apartments
        indexed_count = ApartmentSearchIndex.objects.count()
        available_count = Apartment.objects.filter(status='available').count()
        
        self.stdout.write(
            f'\nStatistics:\n'
            f'- Total indexed: {indexed_count}\n'
            f'- Available apartments: {available_count}\n'
        )