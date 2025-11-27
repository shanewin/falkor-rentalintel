from django.db import migrations
import pgvector.django.vector


class Migration(migrations.Migration):

    dependencies = [
        ("doc_analysis", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentembedding",
            name="embedding",
            field=pgvector.django.vector.VectorField(dimensions=1536),
        ),
    ]
