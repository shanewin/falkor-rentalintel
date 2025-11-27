# Generated migration for adding latitude and longitude fields to Building model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('buildings', '0002_add_brokers_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='building',
            name='latitude',
            field=models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True, help_text='Latitude coordinate for map display'),
        ),
        migrations.AddField(
            model_name='building',
            name='longitude',
            field=models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True, help_text='Longitude coordinate for map display'),
        ),
    ]