from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0003_seed_approved_catalogs")]

    operations = [
        migrations.RenameIndex(
            model_name="catalogentry",
            new_name="catalogs_ca_catalog_506cbb_idx",
            old_name="catalogs_ca_catalog_8b8b16_idx",
        ),
    ]
