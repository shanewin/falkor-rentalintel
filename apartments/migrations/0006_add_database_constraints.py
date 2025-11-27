# Generated manually for database-level constraints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apartments', '0005_add_validation_constraints'),
    ]

    operations = [
        # Add database-level CHECK constraints for business rules
        migrations.RunSQL(
            sql=[
                # Ensure rent_price is positive
                "ALTER TABLE apartments_apartment ADD CONSTRAINT rent_price_positive CHECK (rent_price > 0);",
                
                # Ensure net_price doesn't exceed rent_price
                "ALTER TABLE apartments_apartment ADD CONSTRAINT net_price_not_greater CHECK (net_price IS NULL OR net_price <= rent_price);",
                
                # Ensure deposit is reasonable (max 3x rent)
                "ALTER TABLE apartments_apartment ADD CONSTRAINT deposit_reasonable CHECK (deposit_price IS NULL OR deposit_price <= rent_price * 3);",
                
                # Ensure bedrooms and bathrooms are non-negative
                "ALTER TABLE apartments_apartment ADD CONSTRAINT bedrooms_non_negative CHECK (bedrooms IS NULL OR bedrooms >= 0);",
                "ALTER TABLE apartments_apartment ADD CONSTRAINT bathrooms_non_negative CHECK (bathrooms IS NULL OR bathrooms >= 0);",
                
                # Ensure square_feet is reasonable
                "ALTER TABLE apartments_apartment ADD CONSTRAINT square_feet_range CHECK (square_feet IS NULL OR (square_feet >= 100 AND square_feet <= 10000));",
            ],
            reverse_sql=[
                "ALTER TABLE apartments_apartment DROP CONSTRAINT IF EXISTS rent_price_positive;",
                "ALTER TABLE apartments_apartment DROP CONSTRAINT IF EXISTS net_price_not_greater;",
                "ALTER TABLE apartments_apartment DROP CONSTRAINT IF EXISTS deposit_reasonable;",
                "ALTER TABLE apartments_apartment DROP CONSTRAINT IF EXISTS bedrooms_non_negative;",
                "ALTER TABLE apartments_apartment DROP CONSTRAINT IF EXISTS bathrooms_non_negative;",
                "ALTER TABLE apartments_apartment DROP CONSTRAINT IF EXISTS square_feet_range;",
            ]
        ),
        
        # Add database indexes for commonly queried fields
        migrations.AddIndex(
            model_name='apartment',
            index=models.Index(fields=['status', 'rent_price'], name='apt_status_price_idx'),
        ),
        migrations.AddIndex(
            model_name='apartment',
            index=models.Index(fields=['bedrooms', 'bathrooms'], name='apt_beds_baths_idx'),
        ),
        migrations.AddIndex(
            model_name='apartment',
            index=models.Index(fields=['building', 'status'], name='apt_building_status_idx'),
        ),
    ]