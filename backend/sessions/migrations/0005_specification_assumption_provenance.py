from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prompt_sessions", "0004_alter_promptsession_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="specification",
            name="assumption_provenance",
            field=models.JSONField(default=list),
        ),
    ]
