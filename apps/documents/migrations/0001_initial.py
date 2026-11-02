import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("carriers", "0002_carrier_related_timestamps"),
        ("catalogs", "0006_seed_order_closing_statuses"),
        ("orders", "0003_orderstatushistory"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttachmentSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_number", models.PositiveBigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("related_event", models.CharField(blank=True, max_length=150)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("carrier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="carriers.carrier")),
                ("carrier_document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="carriers.carrierdocument")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_documents", to=settings.AUTH_USER_MODEL)),
                ("document_type", models.ForeignKey(limit_choices_to={"catalog_type": "document_type"}, on_delete=django.db.models.deletion.PROTECT, related_name="documents", to="catalogs.catalogentry")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="documents", to="orders.order")),
                ("stage", models.ForeignKey(blank=True, limit_choices_to={"catalog_type": "order_status"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stage_documents", to="catalogs.catalogentry")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="DocumentVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("file", models.FileField(upload_to="apps.documents.models.document_upload_to", validators=[])),
                ("stored_name", models.CharField(max_length=120, unique=True)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=100)),
                ("size", models.PositiveBigIntegerField()),
                ("is_current", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_document_versions", to=settings.AUTH_USER_MODEL)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="documents.document")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uploaded_document_versions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-version",)},
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(
                condition=(models.Q(("order__isnull", False), ("carrier__isnull", True)) | models.Q(("order__isnull", True), ("carrier__isnull", False))),
                name="document_exactly_one_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentversion",
            constraint=models.UniqueConstraint(fields=("document", "version"), name="unique_document_version"),
        ),
        migrations.AddConstraint(
            model_name="documentversion",
            constraint=models.UniqueConstraint(condition=models.Q(("is_current", True), ("is_deleted", False)), fields=("document",), name="one_current_document_version"),
        ),
    ]
