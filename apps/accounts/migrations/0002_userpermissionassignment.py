import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_seed_roles"),
    ]
    operations = [
        migrations.CreateModel(
            name="UserPermissionAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="permission_assignment", to=settings.AUTH_USER_MODEL)),
                ("permissions", models.ManyToManyField(blank=True, related_name="user_assignments", to="auth.permission")),
            ],
        ),
    ]
