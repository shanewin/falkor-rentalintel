# Generated migration for adding database indexes to ApplicantActivity model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applicants', '0021_alter_applicant_current_address_months_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='applicantactivity',
            index=models.Index(fields=['applicant', '-created_at'], name='applicants_applica_c5f8d9_idx'),
        ),
        migrations.AddIndex(
            model_name='applicantactivity',
            index=models.Index(fields=['activity_type', '-created_at'], name='applicants_activit_8b3e4f_idx'),
        ),
        migrations.AddIndex(
            model_name='applicantactivity',
            index=models.Index(fields=['applicant', 'activity_type', '-created_at'], name='applicants_applica_7a2c1e_idx'),
        ),
        migrations.AddIndex(
            model_name='applicantactivity',
            index=models.Index(fields=['-created_at'], name='applicants_created_9f5b2a_idx'),
        ),
    ]