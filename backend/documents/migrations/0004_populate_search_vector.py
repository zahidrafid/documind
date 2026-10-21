from django.contrib.postgres.search import SearchVector
from django.db import migrations


def populate_search_vector(apps, schema_editor):
    Chunk = apps.get_model("documents", "Chunk")
    Chunk.objects.update(search_vector=SearchVector("text", config="english"))


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_chunk_search_vector_chunk_chunk_search_vector_gin"),
    ]

    operations = [
        migrations.RunPython(populate_search_vector, migrations.RunPython.noop),
    ]
