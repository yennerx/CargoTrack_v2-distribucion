from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("orders", "0001_initial")]

    operations = [
        migrations.RenameIndex(
            model_name="order",
            old_name="orders_orde_status_0f98f8_idx",
            new_name="orders_orde_status__ea94e1_idx",
        ),
        migrations.RenameIndex(
            model_name="order",
            old_name="orders_orde_custome_3bc7a6_idx",
            new_name="orders_orde_custome_242823_idx",
        ),
    ]
