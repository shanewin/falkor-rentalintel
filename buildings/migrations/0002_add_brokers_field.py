# Generated manually for adding brokers ManyToMany relationship
from django.db import migrations, models
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('buildings', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='building',
            name='brokers',
            field=models.ManyToManyField(blank=True, limit_choices_to={'is_broker': True}, related_name='buildings', to=settings.AUTH_USER_MODEL),
        ),
    ]