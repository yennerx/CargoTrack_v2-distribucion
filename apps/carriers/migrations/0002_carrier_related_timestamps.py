from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("carriers", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="carrierdocument",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="carrierdocument",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="carrierunit",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="carrierunit",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="carrierdocument",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="carrierunit",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
