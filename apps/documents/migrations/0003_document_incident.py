import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0002_alter_documentversion_file"),
        ("incidents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="incident",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents",
                to="incidents.incident",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="document",
            name="document_exactly_one_target",
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(("order__isnull", False), ("carrier__isnull", True), ("incident__isnull", True)))
                    | (models.Q(("order__isnull", True), ("carrier__isnull", False), ("incident__isnull", True)))
                    | (models.Q(("order__isnull", True), ("carrier__isnull", True), ("incident__isnull", False)))
                ),
                name="document_exactly_one_target",
            ),
        ),
    ]
