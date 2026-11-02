import apps.documents.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="documentversion",
            name="file",
            field=models.FileField(
                upload_to=apps.documents.models.document_upload_to,
                validators=[],
            ),
        ),
    ]
